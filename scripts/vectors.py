#!/usr/bin/env python3
# Copyright 2026 The p2-11 Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""vectors.py makes the processor's test vectors by asking SimH.

A vector is a machine before an instruction and the same machine after it: the
registers, the status word, and the memory the instruction could reach. This
script thinks up the instructions and what they operate on, has SimH's PDP-11/40
execute each, and writes down what SimH made of it as an OctoGo table that
pdp11/vector_test.ogo runs the processor against.

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

EDGES = (0, 1, 2, 0o77777, 0o100000, 0o100001, 0o177777, 0o177776, 0o377,
         0o400, 0o200, 0o177, 0o201, 0o125252, 0o052525, 0o177400, 0o000100)


def background(a):
    """What is at the address a before a case puts its own there."""
    if 0o4 <= a < 0o40:
        return HANDLERS + a if a & 2 == 0 else 0o340 + (a >> 2)
    if HANDLERS + 4 <= a < HANDLERS + 0o40:
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

    def user(self):
        return self.psw & 0o140000 != 0

    def sp(self):
        return self.usp if self.user() else self.ksp

    def set_sp(self, v):
        if self.user():
            self.usp = v
        else:
            self.ksp = v

    def poke(self, a, v):
        if a < MEMORY:
            self.mem[a & 0o177776] = v & 0o177777

    def poke_byte(self, a, v):
        if a >= MEMORY:
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
        self.mem[self.next] = v & 0o177777
        self.next += 2
        return self.next

    def operand(self, spec, value, size=2, at=None):
        """Arrange for the operand that the specifier spec addresses to be
        value, at the address at if one is given."""
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
            self.poke_byte(at, value)
        elif at & 1 == 0:
            self.poke(at, value)

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
    when it stopped, the registers, and the words of memory that are not zero."""
    lines = [
        'set cpu 11/40', 'set cpu nommu', 'set cpu 56K',
    ]
    for dev in 'rha ptr ptp lpt dz rk rl hk rx rp rq tm tq rom'.split():
        lines.append('set %s disabled' % dev)
    # SimH keeps its clock and its console whatever it is told. The machine
    # under test has neither, so a case that touches one is stopped there,
    # which leaves it out.
    for there in ('177546-177547', '177560-177567'):
        lines.append('break -r %s' % there)
        lines.append('break -w %s' % there)
    lines.append('echo #START')
    for i, c in enumerate(cases):
        lines.append('reset all')
        lines.append('deposit 0-%o 0' % (MEMORY - 2))
        for a in range(0, REGION, 2):
            if background(a):
                lines.append('deposit %o %o' % (a, background(a)))
        for a, v in sorted(c.mem.items()):
            lines.append('deposit %o %o' % (a, v))
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
        lines.append('echo #MEMORY')
        lines.append('examine !=0 0-%o' % (MEMORY - 2))
    lines.append('echo #END')
    lines.append('exit')

    with tempfile.NamedTemporaryFile('w', suffix='.ini', delete=False) as f:
        f.write('\n'.join(lines) + '\n')
    try:
        out = subprocess.run([simh, f.name], capture_output=True, text=True, errors='replace').stdout
    finally:
        os.unlink(f.name)

    version = re.search(r'^PDP-11 simulator (.*)$', out, re.M).group(1)
    version = re.sub(r'\s+', ' ', version).strip()
    body = out.split('#START\n', 1)[1].split('#END', 1)[0]
    chunks = body.split('#CASE ')[1:]
    if len(chunks) != len(cases):
        sys.exit('vectors.py: SimH answered %d cases of %d' % (len(chunks), len(cases)))
    for c, chunk in zip(cases, chunks):
        head, rest = chunk.split('#STATE\n', 1)
        state, memory = rest.split('#MEMORY\n', 1)
        head = [l.strip() for l in head.split('\n')[1:] if l.strip()]
        c.text = '?'
        for l in head:
            if re.match(r'^[0-7]+:\t', l):
                c.text = l.split('\t', 1)[1]
        c.stop = head[-1]
        c.after = [int(l.split('\t')[1], 8) for l in state.strip().split('\n')]
        c.final = {}
        for l in memory.strip().split('\n'):
            if not re.match(r'^[0-7]+:\t[0-7]+', l):
                if os.environ.get('VECTORS_DEBUG'):
                    print('%06o %s: %r' % (c.ir, c.text, l), file=sys.stderr)
                continue
            a, v = l.split(':\t')
            c.final[int(a, 8)] = int(v.split()[0], 8)
        if len(c.after) != 11:
            sys.exit('vectors.py: cannot read what SimH said of case %s' % c.text)
    return version


def usable(c):
    """Whether SimH stopped for a reason the processor has too."""
    return c.stop.startswith('Step expired') or c.stop.startswith('HALT instruction')


def octal(v):
    return '0o%06o' % v


# PART is how many numbers go into one array. The C compiler behind OctoGo
# reads an array's initializer as one line and gives up beyond 65,535
# characters of it.
PART = 4000


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
        '//',
        '// A case is how many steps it takes and how many words of memory it names,',
        '// the machine before and the machine after -- R0 to R5, the stack pointer,',
        '// the kernel\'s, the user\'s, the program counter and the status word -- and',
        '// the words: for each its address, what it holds before and what after.',
        '// The cases come in parts, none of them larger than the C compiler behind',
        '// OctoGo takes in one array.',
        '',
    ]
    parts = [[]]
    size = 0
    for i, c in enumerate(cases):
        before = c.r + [c.sp(), c.ksp, c.usp, c.pc, c.psw]
        words = []
        for a in sorted(set(range(0, REGION, 2)) | set(c.mem) | set(c.final)):
            was = c.mem.get(a, background(a))
            now = c.final.get(a, 0)
            if a in c.mem or now != was:
                words += [a, was, now]
        nums = [c.steps, len(words) // 3] + before + c.after + words
        if size + len(nums) > PART:
            parts.append([])
            size = 0
        size += len(nums)
        parts[-1].append('\t// %d: %06o %s' % (i, c.ir, c.text))
        parts[-1].append('\t' + ', '.join(octal(v) if j > 1 else str(v) for j, v in enumerate(nums)) + ',')

    out += ['// vectors answers the ith part of the cases, and nothing after the last.',
            'func vectors(i int) []uint16 {', '\tswitch i {']
    for i in range(len(parts)):
        out += ['\tcase %d:' % i, '\t\treturn vectors%d[:]' % i]
    out += ['\t}', '\treturn nil', '}']
    for i, part in enumerate(parts):
        out += ['', 'var vectors%d = [...]uint16{' % i] + part + ['}']
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
    cases = systematic(rnd, args.scale) + scattered(rnd, args.n)
    version = run(args.simh, cases)
    kept = [c for c in cases if usable(c)]
    with open(args.o, 'w') as f:
        f.write(table(kept, version, args))
    subprocess.run(['ogo', 'fmt', '-w', args.o], check=True)
    print('%d cases, %d of them left out: SimH stopped at them for a reason of its own' %
          (len(kept), len(cases) - len(kept)), file=sys.stderr)
    for c in cases:
        if not usable(c):
            print('\t%06o %s: %s' % (c.ir, c.text, c.stop), file=sys.stderr)


if __name__ == '__main__':
    main()
