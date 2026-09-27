# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

p2-11 is a PDP-11 emulator for the Parallax Propeller 2 (P2), written in OctoGo. Its purposes, in order:

1. To be an idiomatic example of a non-trivial OctoGo application. OctoGo is pre-release and this is the first real program written in it, so how the code reads outranks how clever it is.
2. To find what OctoGo is missing or gets wrong. What was found is in `OCTOGO.md`.
3. Fun.

**Status, 2026-09-27.** The processor and the console exist, and a program on the board says what it is, sizes memory by trapping, and echoes what is typed with the receiver interrupting. The processor agrees with SimH's 11/40 on every one of 15,876 cases. There is no memory management, no clock and no disk yet, so no operating system boots. Keep this file in step as code lands, and delete what stops being true.

## OctoGo

OctoGo (`ogo`) is a Go-like language for the P2. Its compiler emits C and compiles that to a P2 binary with an embedded copy of the flexspin C backend. The user is its author. The checkout is `../ogo`; read there before writing OctoGo:

- `README.md`: what works and what does not. Its Status section is the inventory.
- `specs.go`: the package doc comment is the language specification.
- `_examples/`: the style reference. `protocol` is a reader cog feeding a ring buffer, `pinselect` a select whose default arm polls a pin, `life` a program that is also valid Go.
- `CLAUDE.md`: loader and board troubleshooting, and the backend's known faults.

Do not edit `../ogo`. Another agent works there.

What differs from Go and shapes this project:

- There is no `package` clause. A directory is a package, named by the directory. Sources end `.ogo`, tests `_test.ogo`.
- There is no heap: no `new`, no maps, no closure that captures its scope, no run-time string concatenation, and `make` only for a slice of constant capacity. Storage is declared, mostly at package scope. A reference that could outlive its referent is a compile error.
- `go` starts a physical cog. There are eight, `main` runs on one, and nothing schedules them.
- A channel is an unbuffered rendezvous guarded by a hardware lock. Its declaration creates it (`var c chan T`); `make(chan T)` is refused. A blocked cog spins.
- `int` and `uint` are 32 bits. `float64` has the precision of `float32`.
- `printf` and `println` are builtins. There is no `fmt`.
- The standard library is `p2`, `strings`, `bytes`, `math` and `testing`. `p2` wraps about thirty intrinsics: pins, smart pins, timing, the serial line and the hardware locks. It has no SPI, no video and no USB.
- Locals are cog registers from a pool of 480 longs. Running out fails the build with `fit 480 failed`, which names assembly rather than source. What spends them is a string or a slice passed at many call sites of one function; `../ogo/CLAUDE.md` says more under "A TEMPORARY IS A COG REGISTER".
- A goroutine's stack is 256 longs unless `--gostack` changes it, for every goroutine at once.

### Which compiler

`ogo` on PATH is installed from `../ogo` and lags it. On 2026-09-27 it was `v0.42.1-0.20260923071228-086cf7f98feb`, three days behind the tree, and the two differ in ways that matter here: see the last section of `OCTOGO.md`. The repository builds and passes its tests with both. Do not install over the user's `ogo`. To use the tree's compiler, build it somewhere of your own, which reads `../ogo` and changes nothing there:

```sh
(cd ../ogo && go build -o "$SCRATCH/ogo-head" .)
```

A compiler that is given a program to find a fault with is run under a cap, as `../ogo`'s own sweeps are: `ulimit -v 4000000` and `timeout -s KILL`. The tree's compiler of 2026-09-26 allocates without end on a shape this project wrote (`OCTOGO.md`, 1), and an uncapped run took the machine's memory.

## Commands

```sh
ogo version                        # record it with every measurement
ogo fmt -l -w .                    # format in place, list what changed
ogo build                          # -> p2-11.binary and p2-11.p2asm
ogo build --unchecked --clock 200MHz   # the fastest the compiler will make it
ogo run                            # build, load, terminal at 230400 baud; Ctrl-] leaves
ogo test ./...                     # every package, one board run each, about 20 s
ogo test -run TestDemo ./dl11      # only the tests whose name matches
ogo test -c ./pdp11                # build the tests only, no board needed
scripts/twin.sh                    # the same tests under Go, on this machine, 1 s
scripts/twin.sh -run Vectors ./pdp11
```

With the compiler on PATH of 2026-09-27 the nine tests of `pdp11` do not fit one binary. Until it is newer they run in two goes: `ogo test -run 'Test[ACDIWRF]' ./pdp11` and `ogo test -run TestVectors ./pdp11`.

`build` and `run` take `--unchecked` (no runtime checks), `--release` (reboot on a panic instead of halting the cog), `--clock 200MHz` (the default is 160 MHz, and 201 MHz is the most the compiler will ask for) and `--gostack N`. `test` takes `--clock`, `--gostack` and `-p port`.

A test is `func TestX(t *testing.T)`; it reports with `printf` or `println` and `t.Fail()`, there being no `Errorf`.

To run a binary and capture what it prints without a terminal session:

```sh
fuser -s /dev/ttyUSB0 && { echo "port busy"; exit 1; }
(sleep 6; printf 'Hello\r'; sleep 1; printf '\004'; sleep 1; printf '\x1d') |
	timeout 60 ogo loadp2 -t -NOEOF -p /dev/ttyUSB0 -b 230400 p2-11.binary 2>&1 |
	tr -d '\r' | grep -a -v 'Entering terminal mode' | grep -a -v '^( '
```

Bytes written into that pipe before the `\x1d` reach the program as console input, unchanged: a carriage return arrives as one. The program runs a benchmark of about three seconds before it says anything.

`*.p2asm` is the assembly the backend wrote. Reading it is how generated code is judged.

### What is generated, and by what

| File | Made by | From |
| --- | --- | --- |
| `pdp11/vectors_test.ogo` | `scripts/vectors.py` | SimH, about two minutes |
| `mac/demo.ogo`, `mac/bench.ogo` | `scripts/mac.py mac/demo.mac` | the MACRO-11 source beside it |

`scripts/tools.sh` fetches and builds SimH and the macro11 assembler into `tools/`, which git ignores. Nothing needs them but these two scripts.

## The board

One P2-EC Edge module (512 KB hub RAM, no PSRAM) behind a Parallax PropPlug on `/dev/ttyUSB0`. The user has allowed its use.

It is shared with the agent working in `../ogo`, and two loaders on one port corrupt both runs. Run `fuser -s /dev/ttyUSB0` before every load. If the port is busy, say so and wait; never kill the other side's process, and never leave a loader holding the port.

| Pins | Function |
| --- | --- |
| P62, P63 | serial out and in: the loader, `println`, and the PDP-11 console in phase 1 |
| P56, P57 | LEDs |
| P58 | microSD and flash data out |
| P59 | microSD and flash data in |
| P60 | microSD chip select, flash clock |
| P61 | microSD clock, flash chip select |

The microSD slot was empty on 2026-09-27. The card agreed with the user is an SDHC of 4 to 32 GB, MBR with one FAT32 partition, holding image files with upper-case 8.3 names, each copied once onto the fresh filesystem so that it is contiguous. `TEST.DSK` on it is 4872 blocks of 512 bytes, each block filled with its own number as a little-endian 32-bit value.

## Architecture

| Package | What it is | Imports `p2` |
| --- | --- | --- |
| the root | the program: the cogs, the serial line, what is loaded and run | yes |
| `pdp11` | the machine: processor, memory, bus, traps and interrupts | no |
| `dl11` | the DL11 serial line unit, which is the console | no |
| `mac` | the PDP-11 programs the emulator carries, source and assembled | no |

Only the root knows the Propeller 2. The others are Go once they have a package clause, which is what `scripts/twin.sh` relies on.

**Three cogs.** `main` steps the machine with `Machine.Run`. `receive` does nothing but read the serial line, since nothing is buffered behind `p2.ReadByte` and a byte arriving while the cog is elsewhere is lost. `transmit` writes it.

**Between cogs there is no lock and no channel.** Every variable two cogs share is written by one of them only: `dl11.Line` has a ring whose head the receiving cog writes and whose tail the machine's cog writes, and a count of bytes written by the program beside a count of bytes sent by the transmitting cog. A channel's rendezvous would stall the cog that reads the line.

**A device** implements `pdp11.Device` and is attached at an address range and a priority. The machine reads and writes its registers through `Read` and `Write(a, v, mask)`, the mask saying which bits a byte write touches. It learns of interrupts by asking: `Request` answers the vector the device wants, `Granted` that it was taken. The devices are asked from the highest priority down, every `pollEvery` instructions and as soon as the program has touched a device or the status word. What a device's other cogs have done is brought into its registers when the machine next calls it.

**Traps** are bits in `Machine.traps`, the most urgent lowest. An access that fails requests one and reads as zero, there being nothing to unwind with, and the instruction asks `m.traps&aborts != 0` before it changes anything. `attention` is a bit among them that is no trap: whatever needs the instructions to stop following one another for a moment sets it, so that the loop in `Run` tests one word.

**The order of things inside an instruction is the 11/40's**, down to what is left behind when an access fails halfway, and that is what the vectors hold the code to. SimH's `pdp11_cpu.c` was the reference for behaviour; nothing of it is copied.

**The code is shaped by what a call costs** (`OCTOGO.md`, 3). `Run` fetches where it stands, `execute` finds the instruction's function, an operand in a register is dealt with where it is met, and `read`, `write` and `address` are called for operands in memory only. There are no helpers that only test something. Do not "tidy" that into small methods without measuring: the first version was written that way and ran a fifth as fast.

## Tests

- **The vectors**, `pdp11/vector_test.ogo` over `pdp11/vectors_test.ogo`: 2380 cases of a machine before and after one or two steps, the after being what SimH's 11/40 made of it. They go through every instruction and addressing mode, the traps, the status word at its address, the stack limit, and 300 cases of whatever sixteen bits came up.
- **By hand**: `pdp11/machine_test.ogo` for the bus, interrupts and the console's switches, with a device of its own; `dl11/dl11_test.ogo` for the line by itself and for the line as console of a machine that runs `mac/demo.mac`, whose output is compared with what it says in SimH.
- **A sweep** is a larger table made elsewhere and run under the twin only. `scripts/vectors.py -n 12000 -o FILE` takes twelve minutes; put FILE in place of the twin's `pdp11/vectors_test.go`, under a package clause, in a twin kept with `scripts/twin.sh -k DIR`.

The twin is for a fast answer about the emulator's logic and for test sets too large for a board. It is not a verdict on what the board does; the board is. `ogo help test` states OctoGo's position.

A case the generator makes must not depend on what SimH has and the machine under test has not. SimH keeps its console and its clock whatever it is told, so the generator sets breakpoints on their registers and drops a case that hits one; and it clears all of memory before each case and lists every word that is not zero after it.

## What it costs, measured

P2-EC, `mac/bench.mac`: 303,004 instructions, of which a third each are `ADD R2,(R1)+`, `INC R3` and `SOB`.

| Build | Instructions a second |
| --- | --- |
| checked, 160 MHz | 111,316 |
| `--unchecked`, 160 MHz | 124,847 |
| `--unchecked --clock 200MHz` | 156,026 |

The two compilers agree to within 1%.

In clocks at 160 MHz, `--unchecked`: a call and its return about 90 to 140; a field of the machine read and tested, 24; a `switch`, about 6 for every case it passes. A function with a branch in it is never inlined, and neither is one that names a constant. The measurements and their programs are in `OCTOGO.md`. Measure again after an `ogo` upgrade before relying on any of it.

Guest RAM as `[N]uint16` makes a word access one `rdword` or `wrword`. A 248 KB array at package scope builds and runs; it is part of the binary image, which is then 263 KB to load.

## The emulated machine

Decided, 2026-09-27:

- Written from scratch for several cogs, not ported from a single-threaded emulator. Devices are goroutines, so their work stays out of the processor's loop. The processor itself is sequential; more cogs do not make it faster.
- Phase 1: the console is the serial line, so the user's terminal is the PDP-11's terminal. Phase 2: investigate a keyboard and a monitor attached to the board, which needs video support OctoGo does not have.
- A PDP-11/40-class processor, the base instruction set with EIS. No memory management until RT-11 boots, since RT-11 SJ and FB need none; then the KT11-D unit, which Unix V6 requires.
- Devices: DL11 console, KW11-L line clock, RK11 disk controller with RK05 images on the SD card.
- First guest: RT-11. Unix V6 afterwards, if it can be done.
- The main package at the module root, beside an `ogo.mod` saying `module modernc.org/p2-11`, so that a visitor runs `ogo run` right after cloning.

What there is of it:

| | State |
| --- | --- |
| KD11-A instructions, KE11-E (MUL, DIV, ASH, ASHC) | done |
| traps, the trace bit, the fixed stack limit at 400 | done |
| kernel and user mode with a stack pointer each, MFPI and MTPI | done, as far as they go without memory management |
| the status word at 177776, the switch register at 177570 | done |
| DL11 console | done |
| KW11-L line clock | not started |
| an SD card driver, and RK11 over it | not started |
| KT11-D memory management, 248 KB | not started |
| FIS, the floating point processor | not planned: their instructions trap as on a machine without them |

What the 11/40 does in its own way, all of it in the vectors: a register source is read after the destination is decoded, so `MOV R0,(R0)+` stores the stepped value; `JMP` and `JSR` to a register trap through 4, not 10; a program cannot write the trace bit at 177776; `HALT` in user mode traps through 10; the stack limit is fixed and only ever a trap after the instruction.

Reference facts. Addresses are 16-bit and octal; both `0o177560` and `0177560` compile.

| Device | Registers | Vector | Priority |
| --- | --- | --- | --- |
| DL11 console | RCSR 177560, RBUF 177562, XCSR 177564, XBUF 177566 | 060 in, 064 out | 4 |
| KW11-L clock | LKS 177546 | 100 | 6 |
| RK11 disk | RKDS 177400, RKER 177402, RKCS 177404, RKWC 177406, RKBA 177410, RKDA 177412, RKDB 177416 | 220 | 5 |

The I/O page is the top 8 KB of the address space, 160000 to 177777. Without memory management that leaves 56 KB of RAM; with the 18-bit KT11-D, 248 KB. An RK05 pack is 203 cylinders of 2 surfaces of 12 sectors of 256 words: 4872 blocks, 2,494,464 bytes. The PDP-11 and the P2 are both little-endian.

## Guest software never enters the repository

No disk image, ROM dump or other guest software is committed, whatever its license. History cannot be cleaned afterwards. `guest/` is the place to keep it on this machine; `.gitignore` excludes that directory and, as a second net, the usual image and archive extensions.

- DEC software (RT-11, RSX-11, RSTS/E, the diagnostics) is not redistributable. The Mentec hobbyist license grants use "solely for personal, non-commercial uses in conjunction with the EMULATOR" and defines that emulator as "software owned by Digital Equipment Corporation", so by its letter it does not cover this one. Do not download DEC software unasked; whether and which kit to use is the user's decision.
- Research Unix V1 to V7 is under the Caldera license, a 4-clause BSD license with an advertising clause. It may be fetched, and redistributed with its notice.

The programs in `mac/` are the project's own.

## Working rules

- An OctoGo gap or fault is a result, not an obstacle. Report it to the user with a minimal reproducer and measured numbers, write it into `OCTOGO.md`, and use the idiomatic workaround meanwhile. Check it against the tree's compiler first: twice on 2026-09-27 what the compiler on PATH did was already fixed there.
- Code of general use, such as an SPI or SD driver and later video, is written as a package with no dependency on the emulator, so that it can move into OctoGo's standard library.
- What a binary does is measured on the board before it is written down, with the `ogo version` and the clock it was measured at.
- A test that fails is first suspected of being wrong itself. Of the differences from SimH met so far, one was the machine's, which counted an instruction it could not fetch as a step, and the rest were the test's: a generator that let a case reach SimH's console, a stale word of memory, an expectation miscounted.
- The repository is private, and the user has delegated the timing of making it public. Say so when all of these hold: LICENSE, AUTHORS and a README stating the status exist; the history holds no guest software and no personal data; the project builds with a tagged `ogo` release; and a stranger with a board can clone, `ogo run`, and watch a recognisable PDP-11 program at the terminal.

## License

BSD-3-Clause: the text of `../ogo/LICENSE` under "The p2-11 Authors", who are listed in AUTHORS. Every source file, script and Makefile begins with the header OctoGo's own sources carry, in the file's comment syntax:

```
// Copyright 2026 The p2-11 Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.
```

Code taken from elsewhere keeps its own notice, and is recorded before it is committed. The preference is to write from the DEC handbooks and to use other emulators as a reference for behaviour only.

## Open decisions

- Whether the program is built `--unchecked` by those who run it. It is 12% faster.
- A lock shared with `../ogo` around board access, offered and not yet answered.
