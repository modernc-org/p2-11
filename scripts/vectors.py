#!/usr/bin/env python3
# Copyright 2026 The p2-11 Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""vectors.py makes the processor's test vectors by asking SimH.

A vector is a machine before an instruction and the same machine after it: the
registers, the status word, the memory the instruction could reach, and the
registers of the memory management it changes. This script thinks up the
instructions and what they operate on, has SimH's PDP-11/40 execute each, and
writes down what SimH made of it as an OctoGo table that pdp11/vector_test.ogo
runs the processor against.

SimH is the reference for behaviour and nothing of it is in the repository.
scripts/tools.sh fetches and builds it, into tools/.

Usage: scripts/vectors.py [-n CASES] [-scale N] [-seed SEED] [-simh PDP11] [-o FILE]

	-n CASES     how many random cases to add to the systematic ones (default 300)
	-scale N     how many times over the systematic ones are made (default 1)
	-seed SEED   the seed of the random choices (default 1)
	-simh PDP11  the SimH binary (default $SIMH, or tools/simh/BIN/pdp11)
	-o FILE      where to write the table (default pdp11/vectors_test.ogo)

What the table holds is a function of the arguments and of SimH's version, which
the table's header records. The defaults make the table that is in the
repository, which is sized to be loaded onto a board with the tests; a sweep on
this machine takes a larger one, written elsewhere and run under the Go twin.
"""

import argparse
import os
import random
import re
import subprocess
import sys
import tempfile

# A case's memory is laid out in the first REGION bytes, which is where an
# instruction is meant to stay. The harness has the same map, in
# pdp11/vector_test.ogo. One that leaves it all the same finds the rest of
# memory, MEMORY bytes in all, holding nothing.
REGION = 0o4000
MEMORY = 0o160000
CODE = 0o1000  # the instruction
KSTACK = 0o700  # the kernel's stack, growing down towards the limit at 0o400
USTACK = 0o1700  # the user's
DATA = 0o2000  # 0o2000-0o2776: operands
CELLS = 0o3000  # 0o3000-0o3376: the addresses deferred modes go through
HANDLERS = 0o3400  # a trap through the vector v goes to HANDLERS+v

VECTORS = (0o004, 0o010, 0o014, 0o020, 0o024, 0o030, 0o034)
NOP = 0o000240
NOWHERE = 0o160000  # an address nothing answers at
PSW = 0o177776

# The memory management: its registers, where a case's pages go, and what
# every case begins with, which is every page of both modes where its address
# says it is, the eighth on the I/O page, and the unit off. A case names the
# registers it sets, and the table holds those and the ones that changed.
SR0 = 0o177572
SR2 = 0o177576
KERNEL = 0
USER = 3
PAGE = 0o20000
KERNEL_PDR, KERNEL_PAR = 0o172300, 0o172340
USER_PDR, USER_PAR = 0o177600, 0o177640
ELSEWHERE = (0o1000, 0o1200, 0o1400)  # page addresses of 100000, 120000 and 140000
FULL = 0o77406  # a page descriptor: the whole page, read and write


def page_registers(mode, n):
    """The addresses of the page address and descriptor registers of the page
    n of a mode."""
    if mode == USER:
        return USER_PAR + 2 * n, USER_PDR + 2 * n
    return KERNEL_PAR + 2 * n, KERNEL_PDR + 2 * n


def register_name(a):
    """What SimH calls the register at the I/O address a."""
    if a == SR0:
        return 'mmr0'
    if a == SR2:
        return 'mmr2'
    mode = 'u' if a >= USER_PDR else 'k'
    kind = 'par' if a & 0o40 else 'pdr'
    return '%si%s%d' % (mode, kind, a >> 1 & 7)


def managed_background():
    out = {SR0: 0}
    for mode in (KERNEL, USER):
        for n in range(8):
            par, pdr = page_registers(mode, n)
            out[par] = n << 7 if n < 7 else 0o7600
            out[pdr] = FULL
    return out


MANAGED = managed_background()
SR0_READABLE = 0o160557

EDGES = (0, 1, 2, 0o77777, 0o100000, 0o100001, 0o177777, 0o177776, 0o377,
         0o400, 0o200, 0o177, 0o201, 0o125252, 0o052525, 0o177400, 0o000100)


def background(a):
    """What is at the address a before a case puts its own there."""
    if 0o4 <= a < 0o40:
        return HANDLERS + a if a & 2 == 0 else 0o340 + (a >> 2)
    if HANDLERS + 4 <= a < HANDLERS + 0o40:
        return NOP
    if a == 0o250:
        return HANDLERS + 0o250
    if a == 0o252:
        return 0o352
    if HANDLERS + 0o250 <= a < HANDLERS + 0o270:
        return NOP
    return 0


class Case:
    def __init__(self, rnd, ir, user=False):
        self.rnd = rnd
        self.ir = ir
        self.steps = 1
        self.r = [word(rnd) for _ in range(6)]
        self.ksp = KSTACK
        self.usp = USTACK
        self.pc = CODE
        self.psw = rnd.randrange(16) | rnd.randrange(8) << 5
        if user:
            self.psw |= 0o140000 | rnd.choice((0, 0o030000))
        self.mem = {CODE: ir}
        self.next = CODE + 2  # where the next word of the instruction goes
        self.io = {}  # the registers of the memory management the case sets

    def user(self):
        return self.psw & 0o140000 != 0

    def mode(self):
        return USER if self.user() else KERNEL

    def previous(self):
        return self.psw >> 12 & 3

    def manage(self):
        """Turn the memory management on, with the pages as they are."""
        self.io[SR0] = 1

    def page(self, mode, n, par=None, pdr=None):
        """Give the page n of a mode its address and its descriptor."""
        par_at, pdr_at = page_registers(mode, n)
        if par is not None:
            self.io[par_at] = par
        if pdr is not None:
            self.io[pdr_at] = pdr

    def register(self, a):
        return self.io.get(a, MANAGED[a])

    def phys(self, a, mode=None):
        """Where the address a of a mode's space is on the bus, if the page is
        there at all; the case's own mode unless one is given. A page that
        goes past the end of the bus goes on at its beginning, the carry out
        of 18 bits being lost."""
        if not self.io.get(SR0, 0) & 1:
            return a
        par_at, pdr_at = page_registers(self.mode() if mode is None else mode, a >> 13)
        if self.register(pdr_at) & 6 == 0:
            return None
        return ((self.register(par_at) << 6) + (a & 0o17777)) & 0o777777

    def sp(self):
        return self.usp if self.user() else self.ksp

    def set_sp(self, v):
        if self.user():
            self.usp = v
        else:
            self.ksp = v

    def poke(self, a, v, mode=None):
        a = self.phys(a, mode)
        if a is not None and a < MEMORY:
            self.mem[a & 0o177776] = v & 0o177777

    def poke_byte(self, a, v, mode=None):
        a = self.phys(a, mode)
        if a is None or a >= MEMORY:
            return
        w = self.mem.get(a & 0o177776, word(self.rnd))
        if a & 1:
            w = w & 0o377 | (v & 0o377) << 8
        else:
            w = w & 0o177400 | v & 0o377
        self.mem[a & 0o177776] = w

    def extend(self, v):
        """Put v where the instruction's next word goes and answer the
        address after it, which is what the program counter then holds."""
        self.poke(self.next, v)
        self.next += 2
        return self.next

    def operand(self, spec, value, size=2, at=None, space=None):
        """Arrange for the operand that the specifier spec addresses to be
        value, at the address at if one is given, in the space of the mode
        space if the instruction reaches into another mode's."""
        mode, r = spec >> 3, spec & 7
        if mode == 0:
            if r < 6:
                self.r[r] = value
            return
        step = 2 if r >= 6 or mode & 1 else size
        if at is None:
            if r == 6:
                at = self.sp() - 0o20 - 2 * self.rnd.randrange(8)
            else:
                at = DATA + 2 * self.rnd.randrange(0o400)
                if size == 1 and self.rnd.random() < 0.5:
                    at += 1
        cell = CELLS + 2 * self.rnd.randrange(0o200)
        if r == 6:
            cell = self.sp() - 0o60 - 2 * self.rnd.randrange(8)
        if size == 1:
            self.poke_byte(at, value, space)
        elif at & 1 == 0:
            self.poke(at, value, space)

        def point(v):
            if r == 6:
                self.set_sp(v & 0o177777)
            elif r < 6:
                self.r[r] = v & 0o177777

        if r == 7:
            if mode == 1:  # (PC): the word after the instruction
                if size == 1:
                    self.poke_byte(self.next, value)
                else:
                    self.poke(self.next, value)
            elif mode == 2:  # #n
                self.extend(value if size == 2 else self.rnd.randrange(256) << 8 | value & 0o377)
            elif mode == 3:  # @#a
                self.extend(at)
            elif mode == 6:  # a
                self.extend(at - (self.next + 2))
            elif mode == 7:  # @a
                self.poke(cell, at)
                self.extend(cell - (self.next + 2))
            return
        if mode == 1 or mode == 2:
            point(at)
        elif mode == 3:
            self.poke(cell, at)
            point(cell)
        elif mode == 4:
            point(at + step)
        elif mode == 5:
            self.poke(cell, at)
            point(cell + 2)
        elif mode == 6:
            x = word(self.rnd)
            self.extend(x)
            point(at - x)
        else:
            x = word(self.rnd)
            self.extend(x)
            self.poke(cell, at)
            point(cell - x)

    def destination(self, size=2):
        """Arrange the operand of an instruction that has one."""
        self.operand(self.ir & 0o77, value(self.rnd, size), size)

    def operands(self, size=2):
        """Arrange both operands of an instruction that has two, a register
        that is only a register first."""
        src, dst = self.ir >> 6 & 0o77, self.ir & 0o77
        if src >> 3 == 0:
            self.operand(src, value(self.rnd, size), size)
        if dst >> 3 == 0:
            self.operand(dst, value(self.rnd, size), size)
        if src >> 3 != 0:
            self.operand(src, value(self.rnd, size), size)
        if dst >> 3 != 0:
            self.operand(dst, value(self.rnd, size), size)


def word(rnd):
    if rnd.random() < 0.4:
        return rnd.choice(EDGES)
    return rnd.randrange(0o200000)


def value(rnd, size):
    v = word(rnd)
    return v if size == 2 else v & 0o377


def spec(rnd):
    """An operand specifier, the modes evenly and the program counter and the
    stack pointer more rarely than the others."""
    r = rnd.choice((0, 1, 2, 3, 4, 5, 0, 1, 2, 3, 4, 5, 6, 7))
    return rnd.randrange(8) << 3 | r


def systematic(rnd, scale):
    """The cases that go through the instructions one by one."""
    cases = []

    def add(c, steps=1):
        c.steps = steps
        cases.append(c)
        return c

    # Two operands, every one of them through every pair of modes.
    for op in (0o01, 0o02, 0o03, 0o04, 0o05, 0o06, 0o16, 0o11, 0o12, 0o13, 0o14, 0o15):
        size = 1 if 0o11 <= op <= 0o15 else 2
        for sm in range(8):
            for dm in range(8):
                for _ in range(scale):
                    ir = op << 12 | sm << 9 | rnd.randrange(6) << 6 | dm << 3 | rnd.randrange(6)
                    add(Case(rnd, ir)).operands(size)
        for _ in range(6 * scale):  # and through the program counter and the stack pointer
            ir = op << 12 | spec(rnd) << 6 | spec(rnd)
            add(Case(rnd, ir, user=rnd.random() < 0.2)).operands(size)

    # One operand.
    for size, top in ((2, 0), (1, 0o100000)):
        for op in range(0o50, 0o64):
            for dm in range(8):
                for _ in range(scale):
                    add(Case(rnd, top | op << 6 | dm << 3 | rnd.randrange(6))).destination(size)
            for _ in range(3 * scale):
                add(Case(rnd, top | op << 6 | spec(rnd))).destination(size)
    for op in (0o0003, 0o0067, 0o0065, 0o0066, 0o1065, 0o1066):  # SWAB SXT MFPI MTPI MFPD MTPD
        for _ in range(12 * scale):
            c = add(Case(rnd, op << 6 | spec(rnd), user=rnd.random() < 0.4))
            c.destination()
            c.poke(c.sp(), word(rnd))

    # The extended instruction set and XOR.
    for op in (0o070, 0o071, 0o072, 0o073, 0o074):
        for _ in range(40 * scale):
            c = add(Case(rnd, op << 9 | rnd.randrange(8) << 6 | spec(rnd)))
            v = word(rnd)
            if op in (0o072, 0o073):
                v = v & 0o177700 | rnd.randrange(64)
            if op == 0o071 and rnd.random() < 0.5:
                # A dividend that the divisor goes into.
                d = rnd.choice((1, 2, 3, 7, 10, 0o177777, 0o177776, 0o100, 0o77777))
                sd = d - 0o200000 if d & 0o100000 else d
                n = sd * rnd.randrange(-0o100000, 0o100000) + rnd.randrange(abs(sd))
                r = c.ir >> 6 & 7
                if r < 6:
                    c.r[r] = n >> 16 & 0o177777
                    c.r[r | 1] = n & 0o177777
                v = d
            c.operand(c.ir & 0o77, v)

    # Branches, each both ways.
    for top in (0o000400, 0o001000, 0o001400, 0o002000, 0o002400, 0o003000, 0o003400,
                0o100000, 0o100400, 0o101000, 0o101400, 0o102000, 0o102400, 0o103000, 0o103400):
        for cc in range(16):
            c = add(Case(rnd, top | rnd.randrange(256)))
            c.psw = c.psw & ~0o17 | cc
    for _ in range(20 * scale):
        c = add(Case(rnd, 0o077000 | rnd.randrange(6) << 6 | rnd.randrange(64)))  # SOB
        c.r[c.ir >> 6 & 7] = rnd.choice((0, 1, 2, 0o177777, word(rnd)))

    # Jumps and returns.
    for op in (0o0001, 0o0040, 0o0041, 0o0042, 0o0043, 0o0044, 0o0045, 0o0046, 0o0047):
        for _ in range(8 * scale):
            add(Case(rnd, op << 6 | spec(rnd), user=rnd.random() < 0.2)).destination()
    for r in range(8):
        for _ in range(2 * scale):
            c = add(Case(rnd, 0o000200 | r, user=rnd.random() < 0.2))
            c.poke(c.sp(), word(rnd))
    for _ in range(12 * scale):
        c = add(Case(rnd, 0o006400 | rnd.randrange(64)))  # MARK
        c.poke(CODE + 2 + 2 * (c.ir & 0o77), word(rnd))
    for ir in (0o000002, 0o000006):  # RTI RTT
        for _ in range(20 * scale):
            c = add(Case(rnd, ir, user=rnd.random() < 0.4), steps=2)
            psw = word(rnd) & 0o140377
            if psw & 0o140000 not in (0, 0o140000):
                psw &= 0o037777
            c.poke(c.sp(), DATA + 2 * rnd.randrange(0o400))
            c.poke(c.sp() + 2, psw)
            c.poke(c.mem[c.sp()], NOP)

    # Condition codes.
    for ir in range(0o000240, 0o000300):
        add(Case(rnd, ir))

    # Traps: the instructions that are traps, the ones that are not there, and
    # the ones this machine has no business executing.
    for ir in (0o000003, 0o000004, 0o104000, 0o104377, 0o104400, 0o104777, 0o104123, 0o104456):
        for _ in range(2 * scale):
            add(Case(rnd, ir, user=rnd.random() < 0.3), steps=2)
    for ir in (0o000007, 0o000010, 0o000077, 0o000210, 0o000227, 0o000230, 0o000237,
               0o007000, 0o007777, 0o075000, 0o075037, 0o076000, 0o076777, 0o106400,
               0o106700, 0o107000, 0o107777, 0o170000, 0o177777, 0o170011):
        add(Case(rnd, ir), steps=2)
        add(Case(rnd, ir, user=True), steps=2)
    for ir in (0o000100, 0o000105, 0o004000, 0o004707, 0o004103):  # a jump to a register
        add(Case(rnd, ir), steps=2)
    for ir in (0o000000, 0o000005):  # HALT RESET
        add(Case(rnd, ir), steps=2)
        add(Case(rnd, ir, user=True), steps=2)

    # The trace bit, on everything that treats it in a way of its own.
    for ir in (NOP, 0o000002, 0o000006, 0o104000, 0o000003, 0o005000, 0o000777, 0o010001):
        for _ in range(3 * scale):
            c = add(Case(rnd, ir), steps=2)
            c.psw |= 0o20
            if ir >> 12:
                c.operands()
            else:
                c.destination()
            if ir in (2, 6):
                c.poke(c.sp(), CODE + 0o40)
                c.poke(c.sp() + 2, rnd.choice((0o20, 0o0, 0o357, 0o37)))
                c.poke(CODE + 0o40, NOP)

    # Accesses that fail: a word at an odd address, and nothing at the address.
    for ir in (0o005037, 0o005737, 0o012737, 0o013700, 0o105037, 0o105737, 0o000137, 0o004737,
               0o062737, 0o005237, 0o070037):
        for at in (DATA + 1, DATA + 0o177, NOWHERE, NOWHERE + 0o1234, 0o157776, 0o157777):
            c = add(Case(rnd, ir), steps=2)
            src, dst = ir >> 6 & 0o77, ir & 0o77
            if src == 0o27:
                c.operand(src, word(rnd))
            if src == 0o37:
                c.operand(src, word(rnd), at=at)
            if dst == 0o37:
                c.operand(dst, word(rnd), at=at)
    for ir, through in ((0o005011, 0o11), (0o005711, 0o11), (0o005021, 0o21), (0o005041, 0o41),
                        (0o005031, 0o31), (0o005051, 0o51), (0o005061, 0o61), (0o005071, 0o71),
                        (0o011100, 0o11), (0o010011, 0o11), (0o111100, 0o11), (0o016100, 0o61)):
        for at in (DATA + 1, NOWHERE, 0o157776):
            c = add(Case(rnd, ir), steps=2)
            if ir >> 12:
                c.operands()
            c.operand(through, word(rnd), at=at)
    for pc in (CODE + 1, NOWHERE, 0o157776):  # the instruction itself
        c = add(Case(rnd, NOP), steps=2)
        c.pc = pc

    # The status word at its address, and the switch register.
    for ir in (0o012737, 0o112737, 0o052737, 0o042737, 0o152737, 0o142737, 0o005037,
               0o105037, 0o005137, 0o005237, 0o013700, 0o113700, 0o005737, 0o006037):
        for at in (PSW, PSW + 1, 0o177570, 0o177571):
            if at & 1 and ir & 0o100000 == 0:
                continue
            for _ in range(scale):
                c = add(Case(rnd, ir, user=rnd.random() < 0.2), steps=2)
                src, dst = ir >> 6 & 0o77, ir & 0o77
                if src == 0o27:
                    v = word(rnd) & 0o140377
                    if v & 0o140000 not in (0, 0o140000):
                        v &= 0o037777
                    c.operand(src, v, 1 if ir & 0o100000 else 2)
                if src == 0o37:
                    c.operand(src, 0, at=at)
                if dst == 0o37:
                    c.operand(dst, 0, at=at)

    # The stack limit: pushes that end below it.
    for ir in (0o010046, 0o005046, 0o004737, 0o104000, 0o000003, 0o010056, 0o005746, 0o110046):
        for ksp in (0o400, 0o402, 0o376, 0o404, 0o410):
            c = add(Case(rnd, ir), steps=2)
            if ir == 0o004737:
                c.operand(0o37, NOP, at=DATA + 0o100)
            if ir == 0o010056:
                c.poke(ksp - 2, DATA + 0o100)
            c.ksp = ksp
    return cases


def managed(rnd, scale):
    """The cases of the memory management: pages elsewhere than their
    addresses say, every abort there is, in both modes and in the previous
    mode's space, and the registers themselves."""
    cases = []

    def add(c, steps=1):
        c.steps = steps
        cases.append(c)
        return c

    def within(page, size=2):
        """An address in the page, a word's if size is 2."""
        return page * PAGE + 2 * rnd.randrange(0o4000) + (rnd.randrange(2) if size == 1 else 0)

    # Pages elsewhere: operands in pages 1 to 3, which are at 100000, 120000
    # and 140000, through every mode, in both modes of the processor.
    ops = (0o01, 0o02, 0o03, 0o04, 0o05, 0o06, 0o16, 0o11, 0o12, 0o13, 0o14, 0o15)
    singles = (0o0050, 0o0052, 0o0053, 0o0057, 0o0060, 0o0063, 0o1050, 0o1052, 0o1057, 0o1063, 0o0003, 0o0067, 0o0074)
    for _ in range(scale):
        for op in ops:
            size = 1 if 0o11 <= op <= 0o15 else 2
            for dm in range(1, 8):
                sm = rnd.randrange(1, 8)
                ir = op << 12 | sm << 9 | rnd.randrange(6) << 6 | dm << 3 | rnd.randrange(6)
                c = add(Case(rnd, ir, user=rnd.random() < 0.3))
                c.manage()
                for mode in (KERNEL, USER):
                    for n in (1, 2, 3):
                        c.page(mode, n, ELSEWHERE[n - 1])
                c.operand(ir >> 6 & 0o77, value(rnd, size), size, at=within(rnd.randrange(1, 4), size))
                c.operand(ir & 0o77, value(rnd, size), size, at=within(rnd.randrange(1, 4), size))
        for op in singles:
            size = 1 if op & 0o1000 else 2
            ir = (op & 0o777) << 6 | (op & 0o1000) << 6 | rnd.randrange(1, 8) << 3 | rnd.randrange(6)
            if op == 0o0074:
                ir = 0o074000 | rnd.randrange(6) << 6 | rnd.randrange(1, 8) << 3 | rnd.randrange(6)
            c = add(Case(rnd, ir, user=rnd.random() < 0.3))
            c.manage()
            for mode in (KERNEL, USER):
                for n in (1, 2, 3):
                    c.page(mode, n, ELSEWHERE[n - 1])
            c.operand(ir & 0o77, value(rnd, size), size, at=within(rnd.randrange(1, 4), size))

    # Aborts: a page that is not there, one that is read-only, one that is
    # shorter than the address, growing either way, and each on a read, a
    # write, and a read that would be written back; and the trap they end in,
    # from which the second step sees the registers frozen.
    reads = (0o013700, 0o113700, 0o005737, 0o105737, 0o023700, 0o033700)
    writes = (0o005037, 0o105037, 0o012737, 0o112737, 0o006737)
    modifies = (0o005237, 0o105237, 0o062737, 0o042737, 0o052737, 0o000337, 0o074037, 0o106337, 0o005337)
    pdrs = (0, 0o77404, 0o77402, 0o1406, 0o1416, 0o402, 0o1400, 0o402 | 0o10, 0o10)
    for _ in range(scale):
        for pdr in pdrs:
            for ir in reads + writes + modifies:
                c = add(Case(rnd, ir, user=rnd.random() < 0.4), steps=rnd.choice((1, 2)))
                c.manage()
                for mode in (KERNEL, USER):
                    c.page(mode, 1, ELSEWHERE[0], pdr)
                size = 1 if ir & 0o100000 else 2
                src, dst = ir >> 6 & 0o77, ir & 0o77
                if src == 0o27:
                    c.operand(src, value(rnd, size), size)
                elif src == 0o37:
                    c.operand(src, value(rnd, size), size, at=within(1, size))
                elif src < 8:
                    c.operand(src, value(rnd, size), size)
                at = within(1, size)
                if rnd.random() < 0.5:  # near the length, either side of it
                    at = PAGE + rnd.choice((0o374, 0o376, 0o400, 0o402, 0o276, 0o300, 0o302, 0o17776))
                c.operand(dst, value(rnd, size), size, at=at)

    # The instruction itself, and the word after it, in a page that is not
    # there or too short for it.
    for pdr in (0, 0o1406, 0o77402):
        for ir in (NOP, 0o013700, 0o012737, 0o005037, 0o000167):
            c = add(Case(rnd, ir), steps=2)
            c.manage()
            c.page(KERNEL, 1, ELSEWHERE[0], pdr)
            c.pc = PAGE + rnd.choice((0, 0o400, 0o1000))
            c.mem = {}
            c.next = c.pc + 2
            c.poke(c.pc, ir)
            if ir >> 12:
                c.operands()
            elif ir != NOP:
                c.destination()
        for ir in (0o013700, 0o012737, 0o005037, 0o016700, 0o005067):
            c = add(Case(rnd, ir), steps=2)
            c.manage()
            c.page(KERNEL, 1, ELSEWHERE[0], pdr)
            c.pc = PAGE - 2 if ir != 0o012737 else PAGE - 4
            c.mem = {c.pc: ir}
            c.next = c.pc + 2
            if ir >> 12:
                c.operands()
            else:
                c.destination()

    # The previous mode's space: what MFPI reads and MTPI writes is the other
    # mode's page 1, which is elsewhere than this mode's, or not there.
    for ir in (0o006537, 0o006637, 0o106537, 0o106637, 0o006517, 0o006617, 0o006567, 0o006667):
        for pdr in (FULL, FULL, 0, 0o77402):
            c = add(Case(rnd, ir, user=rnd.random() < 0.5), steps=2 if pdr != FULL else 1)
            if rnd.random() < 0.7:
                c.psw = c.psw & ~0o030000 | (0 if c.user() else 0o030000)
            c.manage()
            c.page(c.mode(), 1, ELSEWHERE[0])
            c.page(c.previous(), 1, ELSEWHERE[1], pdr)
            c.operand(ir & 0o77, word(rnd), at=within(1), space=c.previous())
            c.poke(c.sp(), word(rnd))

    # The registers: read and written, in words and in bytes, with every
    # bit, the unit on and off, and a write to a page's register forgetting
    # that the page was written to.
    regs = [SR0, SR2] + [a for a in MANAGED if a not in (SR0, SR2)]
    for _ in range(scale):
        for a in regs:
            for ir in rnd.sample((0o013700, 0o113700, 0o012737, 0o112737, 0o052737, 0o042737, 0o005237, 0o105237, 0o005037), 2):
                for on in (False, True):
                    c = add(Case(rnd, ir, user=rnd.random() < 0.2))
                    if on:
                        c.manage()
                    src, dst = ir >> 6 & 0o77, ir & 0o77
                    v = rnd.choice((0o177777, 0o000001, 0o160401, 0o77416, 0o7777, 0o125252, 0o052525, word(rnd)))
                    if src == 0o27:
                        c.operand(src, v, 1 if ir & 0o100000 else 2)
                    at = a + (1 if ir & 0o100000 and rnd.random() < 0.5 else 0)
                    if src == 0o37:
                        c.operand(src, 0, at=at)
                    if dst == 0o37:
                        c.operand(dst, 0, at=at)
    for a in (SR0, SR2):  # the status registers, read by the trap's handler
        c = add(Case(rnd, 0o013700), steps=2)
        c.manage()
        c.page(KERNEL, 1, ELSEWHERE[0], 0)
        c.mem = {CODE: 0o013700, CODE + 2: PAGE}
        c.next = CODE + 4
        c.mem[HANDLERS + 0o250] = 0o013702
        c.mem[HANDLERS + 0o252] = a
    for _ in range(4 * scale):  # frozen: an abort's record stays, and SR2 with it
        c = add(Case(rnd, 0o005037), steps=rnd.choice((1, 2)))
        c.manage()
        c.io[SR0] = rnd.choice((0o100001, 0o040001, 0o020001, 0o140001))
        c.page(KERNEL, 1, ELSEWHERE[0], rnd.choice((0, 0o77402, FULL)))
        c.operand(0o37, 0, at=within(1))
    for _ in range(4 * scale):  # a page written to, then its register written
        c = add(Case(rnd, 0o005037), steps=2)
        c.manage()
        c.page(KERNEL, 1, ELSEWHERE[0])
        c.operand(0o37, word(rnd), at=within(1))
        par, pdr = page_registers(KERNEL, 1)
        c.mem[c.next] = 0o012737
        c.mem[c.next + 2] = rnd.choice((ELSEWHERE[0], FULL))
        c.mem[c.next + 4] = rnd.choice((par, pdr))
    return cases


def ends(rnd, scale):
    """The cases of a page that goes past the end of the bus. They have
    random choices of their own, which leaves the others as they were."""
    cases = []

    def add(c, steps=1):
        c.steps = steps
        cases.append(c)
        return c

    # Page 1 of the processor's mode at 777700: its first 100 bytes are the
    # top of the I/O page, the status word among them, and the rest is the
    # beginning of memory. Operands read, written and written back, words
    # and bytes, either side of the end; and instructions fetched from past
    # it, with what follows them.
    wrapped = PAGE + 0o100  # at 0 on the bus
    reads = (0o013700, 0o113700, 0o011001, 0o111001)
    writes = (0o005037, 0o105037, 0o012737, 0o112737, 0o010110, 0o110110)
    modifies = (0o005237, 0o105237)
    for _ in range(scale):
        for ir in reads + writes + modifies:
            for _ in range(2):
                c = add(Case(rnd, ir, user=rnd.random() < 0.3))
                c.manage()
                c.page(c.mode(), 1, 0o7777)
                size = 1 if ir & 0o100000 else 2
                at = wrapped + DATA + 2 * rnd.randrange(0o400) + (rnd.randrange(2) if size == 1 else 0)
                if ir in reads and rnd.random() < 0.3:
                    at = PAGE + (0o77 if size == 1 else 0o76)  # the status word, before the end
                src, dst = ir >> 6 & 0o77, ir & 0o77
                if ir >> 12 & 7:  # two operands, one of them a register or the word after
                    if src >> 3 == 0 or src == 0o27:
                        c.operand(src, value(rnd, size), size)
                        c.operand(dst, value(rnd, size), size, at=at)
                    else:
                        c.operand(dst, value(rnd, size), size)
                        c.operand(src, value(rnd, size), size, at=at)
                else:
                    c.operand(dst, value(rnd, size), size, at=at)
        for ir in (NOP, 0o012700, 0o013700, 0o005037):
            c = add(Case(rnd, ir, user=rnd.random() < 0.3), steps=rnd.choice((1, 2)))
            c.manage()
            c.page(c.mode(), 1, 0o7777)
            c.pc = wrapped + CODE  # which is where the instruction is on the bus
            c.next = c.pc + 2
            if ir == 0o012700:
                c.operand(0o27, word(rnd))
            elif ir != NOP:  # its operand @#a, a source or a destination
                c.operand(0o37, word(rnd), at=wrapped + DATA + 2 * rnd.randrange(0o400))

    return cases


def scattered(rnd, n):
    """Cases that are whatever sixteen bits come up."""
    cases = []
    while len(cases) < n:
        ir = rnd.randrange(0o200000)
        if ir == 1:  # WAIT waits
            continue
        c = Case(rnd, ir, user=rnd.random() < 0.1)
        size = 1 if ir & 0o100000 and ir >> 12 != 0o16 else 2
        if ir >> 12 in (0, 0o07, 0o10, 0o17):
            c.destination(size)
        else:
            c.operands(size)
        if rnd.random() < 0.2:
            c.steps = 2
        cases.append(c)
    return cases


def run(simh, cases):
    """Have SimH execute the cases, and give each its outcome: what SimH said
    when it stopped, the registers, the words of memory that are not zero,
    and the registers of the memory management."""
    lines = [
        'set cpu 11/40', 'set cpu 56K',
    ]
    for dev in 'rha ptr ptp lpt dz rk rl hk rx rp rq tm tq rom'.split():
        lines.append('set %s disabled' % dev)
    # SimH keeps its clock and its console whatever it is told, and its 11/40
    # has an SR1 at 177574 that no 11/40 had. The machine under test has none
    # of them, so a case that touches one is stopped there, which leaves it
    # out.
    for there in ('177546-177547', '177560-177567', '177574-177575'):
        lines.append('break -r %s' % there)
        lines.append('break -w %s' % there)
    managed_names = [register_name(a) for a in sorted(MANAGED) if a != SR0] + ['mmr2']
    lines.append('echo #START')
    for i, c in enumerate(cases):
        lines.append('reset all')
        lines.append('deposit 0-%o 0' % (MEMORY - 2))
        for a in range(0, REGION, 2):
            if background(a):
                lines.append('deposit %o %o' % (a, background(a)))
        for a, v in sorted(c.mem.items()):
            lines.append('deposit %o %o' % (a, v))
        for a in sorted(MANAGED):
            if a != SR0:
                lines.append('deposit %s %o' % (register_name(a), c.register(a)))
        lines.append('deposit mmr0 %o' % c.register(SR0))  # last: the unit may go on
        for j, v in enumerate(c.r):
            lines.append('deposit r%d %o' % (j, v))
        lines.append('deposit ksp %o' % c.ksp)
        lines.append('deposit usp %o' % c.usp)
        lines.append('deposit psw %o' % c.psw)
        lines.append('deposit pc %o' % c.pc)
        lines.append('echo #CASE %d' % i)
        lines.append('examine -m %o' % c.pc)
        lines.append('step %d' % c.steps)
        lines.append('echo #STATE')
        lines.append('examine r0,r1,r2,r3,r4,r5,sp,ksp,usp,pc,psw')
        lines.append('echo #MANAGED')
        lines.append('examine mmr0,' + ','.join(managed_names))
        lines.append('echo #MEMORY')
        lines.append('examine !=0 0-%o' % (MEMORY - 2))
    lines.append('echo #END')
    lines.append('exit')

    with tempfile.NamedTemporaryFile('w', suffix='.ini', delete=False) as f:
        f.write('\n'.join(lines) + '\n')
    try:
        # A case takes SimH a twentieth of a second. One that waits for what
        # never comes would take it for ever.
        r = subprocess.run([simh, f.name], capture_output=True, text=True, errors='replace',
                           timeout=120 + len(cases))
    except subprocess.TimeoutExpired:
        sys.exit('vectors.py: SimH did not come to an end')
    except OSError as e:
        sys.exit('vectors.py: %s: %s; scripts/tools.sh builds it' % (simh, e.strerror))
    finally:
        os.unlink(f.name)
    out = r.stdout
    version = re.search(r'^PDP-11 simulator (.*)$', out, re.M)
    if r.returncode != 0 or not version or '#START\n' not in out or '#END' not in out:
        sys.exit('vectors.py: SimH exited with %d and said\n%s%s' %
                 (r.returncode, out[-2000:], r.stderr[-2000:]))
    version = re.sub(r'\s+', ' ', version.group(1)).strip()
    body = out.split('#START\n', 1)[1].split('#END', 1)[0]
    chunks = body.split('#CASE ')[1:]
    if len(chunks) != len(cases):
        sys.exit('vectors.py: SimH answered %d cases of %d' % (len(chunks), len(cases)))
    for c, chunk in zip(cases, chunks):
        head, rest = chunk.split('#STATE\n', 1)
        state, rest = rest.split('#MANAGED\n', 1)
        registers, memory = rest.split('#MEMORY\n', 1)
        head = [l.strip() for l in head.split('\n')[1:] if l.strip()]
        c.text = '?'
        for l in head:
            if re.match(r'^[0-7]+:\t', l):
                c.text = l.split('\t', 1)[1]
        c.stop = head[-1]
        c.after = [int(l.split('\t')[1], 8) for l in state.strip().split('\n')]
        c.managed = {}
        for l in registers.strip().split('\n'):
            name, v = l.split(':\t')
            v = int(v.split()[0], 8)
            if name.lower() == 'mmr0':
                v &= SR0_READABLE  # what a program sees of it
            c.managed[name.lower()] = v
        c.final = {}
        for l in memory.strip().split('\n'):
            if not re.match(r'^[0-7]+:\t[0-7]+', l):
                if os.environ.get('VECTORS_DEBUG'):
                    print('%06o %s: %r' % (c.ir, c.text, l), file=sys.stderr)
                continue
            a, v = l.split(':\t')
            c.final[int(a, 8)] = int(v.split()[0], 8)
        if len(c.after) != 11 or len(c.managed) != 34:
            sys.exit('vectors.py: cannot read what SimH said of case %s' % c.text)
    return version


def usable(c):
    """Whether SimH stopped for a reason the processor has too."""
    return c.stop.startswith('Step expired') or halted(c)


def halted(c):
    return c.stop.startswith('HALT instruction')


def octal(v):
    return '0o%06o' % v


def table(cases, version, args):
    out = [
        '// Copyright 2026 The p2-11 Authors. All rights reserved.',
        '// Use of this source code is governed by a BSD-style',
        '// license that can be found in the LICENSE file.',
        '',
        '// Code generated by scripts/vectors.py -n %d -scale %d -seed %d; DO NOT EDIT.' %
        (args.n, args.scale, args.seed),
        '//',
        '// The reference is the 11/40 of SimH, %s.' % version,
        '',
        '// vectors is the cases, one after another. A case is how many steps it',
        '// takes, whether the last of them is a HALT and how many words it names;',
        '// the machine before and the machine after -- R0 to R5, the stack',
        '// pointer, the kernel\'s, the user\'s, the program counter and the status',
        '// word -- and the words: for each its address, what it holds before and',
        '// what after. A word in the I/O page is a register of the memory',
        '// management, which the harness sets and reads as the console does.',
        'var vectors = [...]uint16{',
    ]
    for i, c in enumerate(cases):
        before = c.r + [c.sp(), c.ksp, c.usp, c.pc, c.psw]
        words = []
        for a in sorted(set(range(0, REGION, 2)) | set(c.mem) | set(c.final)):
            was = c.mem.get(a, background(a))
            now = c.final.get(a, 0)
            if a in c.mem or now != was:
                words += [a, was, now]
        for a in sorted(MANAGED):
            was = c.register(a)
            now = c.managed[register_name(a)]
            if a in c.io or now != was:
                words += [a, was, now]
        a, was, now = SR2, 0, c.managed['mmr2']
        if now != was:
            words += [a, was, now]
        nums = [c.steps, int(halted(c)), len(words) // 3] + before + c.after + words
        out.append('\t// %d: %06o %s' % (i, c.ir, c.text))
        out.append('\t' + ', '.join(octal(v) if j > 2 else str(v) for j, v in enumerate(nums)) + ',')
    out.append('}')
    return '\n'.join(out) + '\n'


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('-n', type=int, default=300)
    p.add_argument('-scale', type=int, default=1)
    p.add_argument('-seed', type=int, default=1)
    p.add_argument('-simh', default=os.environ.get('SIMH', 'tools/simh/BIN/pdp11'))
    p.add_argument('-o', default='pdp11/vectors_test.ogo')
    p.add_argument('-h', '--help', action='store_true')
    args = p.parse_args()
    if args.help:
        print(__doc__)
        return

    rnd = random.Random(args.seed)
    cases = systematic(rnd, args.scale) + managed(rnd, args.scale) + scattered(rnd, args.n)
    # And one case in eight of the others with the unit on, its pages where
    # their addresses say.
    for c in cases:
        if not c.io and rnd.random() < 0.125:
            c.manage()
    cases += ends(random.Random('ends %d' % args.seed), args.scale)
    version = run(args.simh, cases)
    kept = [c for c in cases if usable(c)]
    new = args.o + '.new.ogo'
    try:
        with open(new, 'w') as f:
            f.write(table(kept, version, args))
        subprocess.run(['ogo', 'fmt', '-w', new], check=True)
        os.replace(new, args.o)
    finally:
        if os.path.exists(new):
            os.unlink(new)
    print('%d cases, %d of them left out: SimH stopped at them for a reason of its own' %
          (len(kept), len(cases) - len(kept)), file=sys.stderr)
    for c in cases:
        if not usable(c):
            print('\t%06o %s: %s' % (c.ir, c.text, c.stop), file=sys.stderr)


if __name__ == '__main__':
    main()
