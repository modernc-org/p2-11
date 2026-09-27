# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

p2-11 is a PDP-11 emulator for the Parallax Propeller 2 (P2), written in OctoGo. Its purposes, in order:

1. To be an idiomatic example of a non-trivial OctoGo application. OctoGo is pre-release and this is the first real program written in it, so how the code reads outranks how clever it is.
2. To find what OctoGo is missing or gets wrong.
3. Fun.

**Status, 2026-09-27: no emulator code exists yet.** The decisions below are taken and nothing is built on them so far. Keep this file in step as code lands, and delete what stops being true.

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
- Locals are cog registers from a pool of 480 longs. A function too big for it fails the build with `fit 480 failed`, which names assembly rather than source; the fix is to split the function.
- A goroutine's stack is 256 longs unless `--gostack` changes it, for every goroutine at once.

## Commands

`ogo` is on PATH, installed from `../ogo`, and may change between sessions. Nothing else is needed to build.

No packages exist yet, so `./cpu` below stands for any library package. Every form was verified on a skeleton with the main package at the module root.

```sh
ogo version                # record it with every measurement
ogo fmt -l -w .            # format in place, list what changed
ogo build                  # the main package here -> p2-11.binary and p2-11.p2asm
ogo build ./cpu            # a package with no func main is checked, nothing is written
ogo run                    # build, load, terminal at 230400 baud; Ctrl-] leaves
ogo test ./...             # every package, one board run each
ogo test -run SetNZ ./cpu  # only the tests whose name matches
ogo test -c ./cpu          # build the tests only, no board needed
```

`build` and `run` take `--unchecked` (no runtime checks), `--release` (reboot on a panic instead of halting the cog), `--clock 200MHz` (the default is 160 MHz) and `--gostack N`. `test` takes `--clock`, `--gostack` and `-p port`.

Tests run on the board and nowhere else. A test is `func TestX(t *testing.T)`; it reports with `println` and `t.Fail()`, there being no `Errorf`.

To run a binary and capture what it prints without a terminal session:

```sh
fuser -s /dev/ttyUSB0 && { echo "port busy"; exit 1; }
(sleep 5; printf '\x1d') |
	timeout 60 ogo loadp2 -t -NOEOF -p /dev/ttyUSB0 -b 230400 p2-11.binary 2>&1 |
	tr -d '\r' | grep -a -v 'Entering terminal mode' | grep -a -v '^( '
```

Bytes written into that pipe before the `\x1d` reach the program as console input, unchanged: a carriage return arrives as one.

`*.p2asm` is the assembly the backend wrote. Reading it is how generated code is judged.

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

## The same source under Go

A package that does not import `p2` compiles as Go once it is given a package clause, with `printf` spelled `fmt.Printf`. Verified on a two-package skeleton with tests: `go test` on the twin and `ogo test` on the board passed the same tests, and the main program printed the same bytes in both.

The recipe: copy each `.ogo` file to a `.go` file in a mirror directory, prepend `package main` at the module root and `package <directory>` elsewhere, add a `go.mod` carrying the module path of `ogo.mod`, and run with `GOARCH=386` so that `int` is 32 bits as on the target. No script does this yet.

Decided: the twin is for fast feedback on the emulator's logic against large test sets, and for nothing else. It is not a verdict on what the board does; the board is. `ogo help test` states OctoGo's position.

## What code costs, measured

P2-EC at 160 MHz, `ogo v0.42.1-0.20260923071228-086cf7f98feb`. The loop writes one word of guest memory and reads it back, through two one-line accessor functions over a package-level `[126976]uint16`.

| Build | Clocks per iteration |
| --- | --- |
| `--unchecked`, loop bound written as a literal | 60.5 |
| `--unchecked`, loop bound a named constant | 71.0 |
| runtime checks on | 422 |

- A named constant is emitted as a `static const` object and read from hub RAM at every use, which costs about 10 clocks.
- A bounds check calls the panic helper. The accessor is then no longer inlined, each call saves and restores registers on the hub stack, and a loop containing calls is not copied into cog RAM (FCACHE) and runs from hub RAM.

So calls that do not inline and execution from hub RAM dominate, not arithmetic. Both findings were reported to the user on 2026-09-27. Measure again after an `ogo` upgrade before relying on either.

Guest RAM as `[N]uint16` makes a word access one `rdword` or `wrword`. A 248 KB array at package scope builds and runs; it is part of the binary image, which is then 263 KB to load.

`../ogo/CLAUDE.md`, under "A TEMPORARY IS A COG REGISTER", says what spends the 480 registers and how to count them.

## The emulated machine

Decided, 2026-09-27:

- Written from scratch for several cogs, not ported from a single-threaded emulator. Devices are goroutines, so their work stays out of the processor's loop. The processor itself is sequential; more cogs do not make it faster.
- Phase 1: the console is the serial line, so the user's terminal is the PDP-11's terminal. Phase 2: investigate a keyboard and a monitor attached to the board, which needs video support OctoGo does not have.
- A PDP-11/40-class processor, the base instruction set with EIS. No memory management until RT-11 boots, since RT-11 SJ and FB need none; then the KT11-D unit, which Unix V6 requires.
- Devices: DL11 console, KW11-L line clock, RK11 disk controller with RK05 images on the SD card.
- First guest: RT-11. Unix V6 afterwards, if it can be done.
- The main package at the module root, beside an `ogo.mod` saying `module modernc.org/p2-11`, so that a visitor runs `ogo run` right after cloning. The processor and the device models in packages that do not import `p2`; the cogs and the pins in the main package.

Where the design of the cogs' communication starts, from what `_examples/protocol` measured: a byte stream goes through a single-producer, single-consumer ring, because a channel's rendezvous stalls the producer and nothing is buffered behind `p2.ReadByte`. A command suits a channel. How a device cog raises an interrupt to the processor is not designed yet.

Reference facts. Addresses are 16-bit and octal; both `0o177560` and `0177560` compile.

| Device | Registers | Vector | Priority |
| --- | --- | --- | --- |
| DL11 console | RCSR 177560, RBUF 177562, XCSR 177564, XBUF 177566 | 060 in, 064 out | 4 |
| KW11-L clock | LKS 177546 | 100 | 6 |
| RK11 disk | RKDS 177400, RKER 177402, RKCS 177404, RKWC 177406, RKBA 177410, RKDA 177412, RKDB 177416 | 220 | 5 |

The I/O page is the top 8 KB of the address space, 160000 to 177777. Without memory management that leaves 56 KB of RAM; with the 18-bit KT11-D, 248 KB. The processor status word is at 177776. An RK05 pack is 203 cylinders of 2 surfaces of 12 sectors of 256 words: 4872 blocks, 2,494,464 bytes. The PDP-11 and the P2 are both little-endian.

## Guest software never enters the repository

No disk image, ROM dump or other guest software is committed, whatever its license. History cannot be cleaned afterwards. `guest/` is the place to keep it on this machine; `.gitignore` excludes that directory and, as a second net, the usual image and archive extensions.

- DEC software (RT-11, RSX-11, RSTS/E, the diagnostics) is not redistributable. The Mentec hobbyist license grants use "solely for personal, non-commercial uses in conjunction with the EMULATOR" and defines that emulator as "software owned by Digital Equipment Corporation", so by its letter it does not cover this one. Do not download DEC software unasked; whether and which kit to use is the user's decision.
- Research Unix V1 to V7 is under the Caldera license, a 4-clause BSD license with an advertising clause. It may be fetched, and redistributed with its notice.

## Working rules

- An OctoGo gap or fault is a result, not an obstacle. Report it to the user with a minimal reproducer and measured numbers, and use the idiomatic workaround meanwhile.
- Code of general use, such as an SPI or SD driver and later video, is written as a package with no dependency on the emulator, so that it can move into OctoGo's standard library.
- What a binary does is measured on the board before it is written down, with the `ogo version` and the clock it was measured at.
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

- Whether the processor core ships with runtime checks, given the measurement above.
- How a device cog raises an interrupt to the processor.
- A lock shared with `../ogo` around board access, offered and not yet answered.
