# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

p2-11 is a PDP-11 emulator for the Parallax Propeller 2 (P2), written in OctoGo. Its purposes, in order:

1. To be an idiomatic example of a non-trivial OctoGo application. OctoGo is pre-release and this is the first real program written in it, so how the code reads outranks how clever it is.
2. To find what OctoGo is missing or gets wrong. What was found is in `OCTOGO.md`.
3. Fun.

**Status, 2026-10-06.** The processor, the console and the line clock exist. A program on the board says what it is, sizes memory by trapping, and echoes what is typed with the receiver interrupting; another waits for sixty interrupts of the clock, which take a second. The processor agrees with SimH's 11/40 on every one of the 2902 cases in the repository, of which 522 are the memory management's, and of the 15,685 of a sweep made before it had any. The disk controller exists, with files on the SD card for its packs, and does on the board what SimH's does with a program of 35 steps. The machine begins with RT-11 V4 on a pack, on the board as under the twin, and says in a talk of nine commands what SimH says, and leaves the pack as SimH leaves it. The KT11-D memory management exists since 2026-09-29, with 248 KB of memory, and costs a tenth of the speed with the unit off and an eighth more with it on. Unix V6 runs since the same day: it begins from the root pack of SimH's kit, on the board as under the twin, logs in, compiles a C program with its own compiler and runs it, and says in a talk of fourteen lines what SimH says. The second phase, a screen of the board's own, is begun the same evening: `vt100` is a VT100's screen, what a host's characters and sequences do to it, tested under the twin and on the board; `vga` shows such a screen with Eric Smith's tile driver on a cog of its own, which sends its frames on the board to the microsecond, measured with no monitor; and the hardware with a VGA socket has come, on 2026-10-05, and waits to be tried. The processor is a quarter faster since 2026-10-02: it finds its instructions in `Run` and an immediate operand where it stands, after a profile of what each shape of instruction costs, which `prof/` measures, and the compiler of that evening acted on two things the profile found; what it found of the backend is in `OCTOGO.md`, 3. Since 2026-10-03 a core in PASM, `core`, executes on a cog of its own what it can of the instructions, and the machine's code the rest: the machine is five times as fast as with its own code alone, and about one and a half times an 11/40 on the benchmark; the talk with V6 takes 27 s where the machine's code alone takes 84, RT-11's 14 where 38, and both say what SimH says. The core agrees with the machine's code on random instructions and with SimH on the 2902 vectors. Keep this file and DESIGN.md in step as code lands, and delete what stops being true.

How the program is made and why, the machine, the architecture, the tests and what it costs, is in `DESIGN.md`, which is written for whoever reads the code, and which this file takes in: @DESIGN.md

## OctoGo

OctoGo (`ogo`) is a Go-like language for the P2. Its compiler emits C and compiles that to a P2 binary with an embedded copy of the flexspin C backend. The user is its author. The checkout is `../ogo`; read there before writing OctoGo:

- `README.md`: what works and what does not. Its Status section is the inventory.
- `specs.go`: the package doc comment is the language specification.
- `_examples/`: the style reference. `protocol` is a reader cog feeding a ring buffer, `pinselect` a select whose default arm polls a pin, `life` a program that is also valid Go.
- `CLAUDE.md`: loader and board troubleshooting, and the backend's known faults.

Do not edit `../ogo`. Another agent works there.

What differs from Go and shapes this project is in DESIGN.md, "Written in OctoGo".

### Which compiler

The repository needs `ogo` v0.47.0 or a later one: the core, `core`, is a Spin2 object, and `pdp11` makes numbers of the addresses of its fields with `unsafe.Pointer`, which v0.47.0 was the first to have; v0.46.0 refuses the import of `unsafe`. The numbers are v0.50.0's, of 2026-10-08, `go install modernc.org/ogo@v0.50.0`, and within half a percent of those of 2026-10-03, which were v0.48.0's; v0.48.0 is the latest with binaries for Linux, macOS and Windows among its releases on 2026-10-08. Built with v0.47.0, the core ran as fast and the machine alone 7% slower. v0.48.1 builds every program and test binary of the repository byte for byte as v0.48.0 does. With v0.50.0 a program ends when `main` returns, every cog with it, which is why `main` waits for the console to have sent what it has; and a goroutine's stack is sized from the listing, which DESIGN.md tells of. It is formatted as that formatter formats, which is as gofmt does. `ogo` on PATH is installed from `../ogo` by the user and the agent there, and may lag the tree or be ahead of what this file knows. Do not install over it. To try the tree's compiler, build it somewhere of your own, which reads `../ogo` and changes nothing there:

```sh
(cd ../ogo && go build -o "$SCRATCH/ogo-head" .)
```

Before a fault is reported, it is looked for with the tree's compiler: twice on 2026-09-27 what `ogo` on PATH did was already fixed there. And a compiler that is given a program to find a fault with is run under a cap, as `../ogo`'s own sweeps are, `ulimit -v 4000000` and `timeout -s KILL`: the tree's compiler of 2026-09-26 allocated without end on a shape this project wrote, and an uncapped run took the machine's memory.

The tests want more: `ogo` v0.47.1, of 2026-10-01. `vga` calls a Spin2 object and fills the driver's parameters through `unsafe.Pointer`, which v0.47.0 was the first to have, and names them `params`, as `vt100` names a constant, which v0.47.1 was the first to keep apart; and `vt100` sends ESC 7 in one string, which the compilers before v0.47.0 made another character of (`OCTOGO.md`). v0.47.1 has no binaries of its own: `go install modernc.org/ogo@v0.47.1`.

A build of this repository says nothing. One that warns has found something: the unsigned number compared as a signed one, which `OCTOGO.md` has among what is closed, was a wrong answer that came with a warning.

## Commands

```sh
ogo version                        # record it with every measurement
ogo fmt -l -w .                    # format in place, list what changed
ogo build                          # -> p2-11.binary and p2-11.p2asm
ogo build --unchecked --clock 200MHz   # the fastest the compiler will make it
ogo run                            # build, load, terminal at 230400 baud; Ctrl-] leaves
ogo test ./...                     # every package, one board run each, about a minute
ogo test -run TestDemo ./dl11      # only the tests whose name matches
ogo test -c ./pdp11                # build the tests only, no board needed
scripts/twin.sh                    # the tests of the packages under Go, on this machine, 1 s
scripts/twin.sh -run Vectors ./pdp11
scripts/twin.sh -v -run RT11 ./rk11 # the talk with RT-11, if guest/RK0.DSK and SimH are there
scripts/talk.py                    # the same talk on the board and in SimH, half a minute
scripts/talk.py -talk v6           # the talk with Unix V6, its pack being on the card, a minute and a half
scripts/record.py                  # a session with V6 on the board, as v6-demo.cast for the README's GIF, a minute
scripts/card.py put guest/RK0.DSK RK0.DSK   # the pack onto the card through the board, two minutes
scripts/card.py put guest/UNIX0.DSK RK0.DSK # the root pack of Unix V6 there instead
scripts/card.py sum RK0.DSK guest/RK0.DSK   # which blocks of the pack on the card differ from the file, 15 s
ogo build --unchecked -o /tmp/prof.binary ./prof   # the profiler, run as below with 40 s of sleep: what each shape of instruction costs
```

`build` and `run` take `--unchecked` (no runtime checks), `--release` (reboot on a panic instead of halting the cog), `--clock 200MHz` (the default is 160 MHz, and 201 MHz is the most the compiler will ask for), `--gostack N`, and since v0.46.0 `--no-inline` (inline no more than the C backend does by itself, as v0.45.0 did). `test` takes `--clock`, `--gostack` and `-p port`.

A test is `func TestX(t *testing.T)`; it reports with `printf` or `println` and `t.Fail()`, there being no `Errorf`.

To run a binary and capture what it prints without a terminal session:

```sh
fuser -s /dev/ttyUSB0 && { echo "port busy"; exit 1; }
(sleep 8; printf 'Hello\r'; sleep 1; printf '\004'; sleep 1; printf '\x1d') |
	timeout 60 ogo loadp2 -t -NOEOF -p /dev/ttyUSB0 -b 230400 p2-11.binary 2>&1 |
	tr -d '\r' | grep -a -v 'Entering terminal mode' | grep -a -v '^( '
```

That is for a card with no `RK0.DSK`, with which the program runs `mac/demo.mac`. With one it is the system on that pack that is typed to, and `scripts/talk.py` is the way to do that. RT-11 says `.` when it is ready. Unix V6 begins with `@`, which is its bootstrap asking for a file of `/` to load and start: `rkunix.40`, the kernel for the 11/40, and after it `root` to `login:`, with no password. A name that is no such file is asked for again.

`prof/` is run the same way, with 40 s of sleep and nothing typed: it prints the benchmark and then a line a shape, fifty of them, built checked or `--unchecked` and at the clock the measurement is of.

Bytes written into that pipe before the `\x1d` reach the program as console input, unchanged: a carriage return arrives as one. The program runs a benchmark of about three seconds before it says anything, and waits a second by the line clock before the program that reads the console is started; what is typed earlier is lost to the reset that starts it.

`*.p2asm` is the assembly the backend wrote. Reading it is how generated code is judged.

## The board

One P2-EC Edge module (512 KB hub RAM, no PSRAM) behind a Parallax PropPlug on `/dev/ttyUSB0`, which is the name the port had on the machine the project began on. The user has allowed its use.

It is shared with the agent working in `../ogo`, and two loaders on one port corrupt both runs. Since 2026-10-03 every use of the port, `ogo test`, `ogo run`, `ogo loadp2`, `scripts/talk.py`, `scripts/card.py`, goes through a lock both sessions take, `flock -w 900 /tmp/p2-board.lock` before the command: `flock -w 900 /tmp/p2-board.lock ogo test ./...`. flock lets go when the command ends, however it ends. The ogo session's `make board` holds it for a quarter of an hour, and its on-board suite for longer, so a wait that times out is likely that and not a fault. Run `fuser -s /dev/ttyUSB0` as well, for a loader the user started by hand. If the port is busy, say so and wait; never kill the other side's process, and never leave a loader holding the port.

| Pins | Function |
| --- | --- |
| P62, P63 | serial out and in: the loader, `println`, and the PDP-11 console in phase 1 |
| P56, P57 | LEDs |
| P58 | microSD and flash data out |
| P59 | microSD and flash data in |
| P60 | microSD chip select, flash clock |
| P61 | microSD clock, flash chip select |

The microSD slot has a card since 2026-09-28: an SDHC of 32 GB, 62,333,952 blocks, which the program is loaded with in place as it was without. The card agreed with the user is an SDHC of 4 to 32 GB, MBR with one FAT32 partition, holding image files with upper-case 8.3 names, each copied once onto the fresh filesystem so that it is contiguous. `TEST.DSK` on it is 4872 blocks of 512 bytes, each block filled with its own number as a little-endian 32-bit value. On this card the partition begins at block 8192 and `TEST.DSK` at block 38720. The tests write to blocks of `TEST.DSK` and to no others, and put back what was there. The pack of drive 0 is the file `RK0.DSK`, and so on to `RK7.DSK`. `RK0.DSK` is on the card since 2026-09-28, from block 43616. It held RT-11 V4 until 2026-09-29, as `guest/RK0.DSK` has it but for what the talks have written, which is what SimH writes to its copy; it holds since the root pack of Unix V6, `guest/UNIX0.DSK` but for what the talks with it have written. `RK1.DSK`, `RK2.DSK` and `RK3.DSK` are on it since the evening of 2026-09-29, the other three packs of V6, which the user copied with the card out, each in one piece. A file goes onto the card without the card coming out: `scripts/card.py put guest/RK0.DSK RK0.DSK`, which is how the pack was put back on 2026-09-28 after an editor's output file, left on it by hand, had the talk on the board disagree with SimH; "A new machine" tells of it.

One load of about 130 on that day ended with the loader's `sendAddressSize: timeout`, and the twenty after it went well. Whether the card in the slot has to do with it is not known.

On 2026-09-29, with `ogo` v0.46.0, whose loader is v0.44.0's, 4 loads of 40 ended with the loader's `Error writing port`: three in `ogo test ./...`, which then says of the package `[the board produced no result]`, and one in `ogo run`. Each went well when it was done again, and so did ten loads of one package in a row. The loader takes a write that comes back short for that error, and does not say why. On 2026-09-30 one load of nine ended so, again in `ogo test ./...`. On 2026-10-01, with v0.47.0, one of eleven, in `ogo test ./...` again, of `pdp11`, which passed when it was loaded again; with v0.47.1 the eleven after went well. The same day one load of `vga`'s test at 160 MHz ended with the loader's `ERROR: timeout waiting for checksum at end: got -1`, which was not met before, and the three after it went well.

## A new machine

The work moved to another machine on 2026-09-28. What the repository does not hold, and a machine needs that is to go on with it:

| What | Where it comes from |
| --- | --- |
| `ogo` v0.47.0 or later | the user installs it from `../ogo`, or `go install modernc.org/ogo@v0.50.0` |
| Go, for `ogo` and the twin, which is built for 386 | the system; go1.27.1 was what there was |
| python3, gcc, make and git, for the scripts and what they build; `fuser`, of psmisc; Pillow and numpy, for `scripts/poster.py` | the system |
| `tools/`, SimH and the assembler | `scripts/tools.sh`, which fetches and builds them |
| `guest/`, the kits of RT-11 and Unix V6, `RK0.DSK`, and `UNIX0.DSK` to `UNIX3.DSK` | the user carries it; the repository must not |
| the port of the board | `/dev/ttyUSB0` where the project began, with the user in the group `dialout` |
| what the assistant remembers | `~/.claude/projects/`, in the directory named after the path of the repository with dashes for slashes, `memory/`; the user carries it. What is needed of it is in this file. |

`guest/RK0.DSK` is made of the kit so, and `guest/UNIX1.DSK` to `guest/UNIX3.DSK` of V6's; `guest/UNIX0.DSK` is mended in SimH as "Guest software never enters the repository" says:

```sh
mkdir -p guest/rt11v4 && gzip -dc guest/rt11swre.tar.Z | tar -xf - -C guest/rt11v4
cp guest/rt11v4/Disks/rtv4_rk.dsk guest/RK0.DSK && chmod 644 guest/RK0.DSK
truncate -s 2494464 guest/RK0.DSK
mkdir -p guest/unixv6 && unzip -q -d guest/unixv6 guest/uv6swre.zip
for n in 1 2 3; do cp guest/unixv6/unix${n}_v6_rk.dsk guest/UNIX$n.DSK && truncate -s 2494464 guest/UNIX$n.DSK; done
```

That all is there is seen in this order, each of which says nothing or `ok`:

```sh
ogo version && ogo fmt -l . && ogo build
scripts/twin.sh                    # with guest/ and tools/ there, the talk with RT-11 among it
ogo test ./...                     # the card in the slot
scripts/card.py put guest/RK0.DSK RK0.DSK && scripts/talk.py            # RT-11 on the board and in SimH
scripts/card.py put guest/UNIX0.DSK RK0.DSK && scripts/talk.py -talk v6  # and Unix V6
```

On the new machine, 2026-09-28, with go1.27.0 and `ogo` v0.44.0, all of that said `ok` but `scripts/talk.py`, and the three generators made the repository's files again as they are. The tests read `TEST.DSK` in 9572 ms, a block of the card in 1605 µs, and wrote one in 2464 µs, as with the compiler of the day before. The talk found the pack on the card changed: its last free area, one entry of 1533 blocks in `guest/RK0.DSK`, is on the card two entries of 766 and 767, the first named `DEMOED.TXT` and without a date, which is what an editor's output file leaves that was entered and never closed. The talk does no such thing, and SimH begun with a pack split the same way says what the board says, byte for byte. `scripts/card.py` was written that evening to put a file onto the card through the board, the card staying in its slot, and put `guest/RK0.DSK` there again; the talk then said what SimH says, 1558 bytes in 36 s. The sixteen bytes `sd` reads a card's size from are a local of `size` again since the same evening, which they could not be before `ogo` c888892, an error not being returnable from a call given a local buffer; the card's tests pass so.

## Guest software never enters the repository

No disk image, ROM dump or other guest software is committed, whatever its license. History cannot be cleaned afterwards. `guest/` is the place to keep it on this machine; `.gitignore` excludes that directory and, as a second net, the usual image and archive extensions.

- DEC software (RT-11, RSX-11, RSTS/E, the diagnostics) is not redistributable. The Mentec hobbyist license grants use "solely for personal, non-commercial uses in conjunction with the EMULATOR" and defines that emulator as "software owned by Digital Equipment Corporation", so by its letter it does not cover this one. Do not download DEC software unasked; whether and which kit to use is the user's decision.
- Research Unix V1 to V7 is under the Caldera license, a 4-clause BSD license with an advertising clause. It may be fetched, and redistributed with its notice.

What is in `guest/` since 2026-09-28, put there by the user: `rt11swre.tar.Z`, RT-11 V4 on RK05 from SimH's software kits, with the license quoted above. `guest/rt11v4/` is the kit unpacked, whose `rtv4_rk.dsk` is of 3267 blocks, and `guest/RK0.DSK` that pack made a whole one, 2,494,464 bytes, which is what goes to the card. SimH begins with it as an 11/40 with 248 KB: RT-11SJ V04.00C.

And since 2026-09-29, fetched at the user's word: `uv6swre.zip`, Unix V6 on four RK05 packs from the same kits, under the Caldera license of 2002 that is in it, unpacked in `guest/unixv6/`. `unix0_v6_rk.dsk` is the root pack, 4058 blocks, whose `rkunix.40` is a kernel built for the 11/40; `rkunix` and `unix` there are the 11/45's, and halt on an 11/40. `guest/UNIX0.DSK` is that pack made a whole one and mended: its free list held block 654 three times, which `icheck` says, so that two files made got the same block and the C compiler's second pass read what its first had not written; and its `/tmp/ctm0a` was a temporary file of the compiler's left by a user of 1994, unreadable, that the compiler's naming counts up from. Made so in SimH, as an 11/40 with 248 KB, the pack padded and attached as rk0, booted, `rkunix.40` given to the prompt, `root` to the login, and then `icheck -s /dev/rk0`, `rm -f /tmp/ctm0a`, `sync`, `sync`, and SimH left at the prompt after: `icheck` then finds nothing wrong, and cc compiles. Made again so in SimH on 2026-09-29, the pack came out as `guest/UNIX0.DSK` is, byte for byte. The order matters. Block 654 is `/etc/mtab`'s, which the kit's `/etc/rc` removes at every boot, so that the kernel frees it a fourth time; and after `icheck -s` the kernel still has the old list in memory, as V6's `icheck(8)` warns: a file written after `icheck -s` put that list back at the next `sync`, in SimH. The order above works, what follows `icheck -s` in it taking no block and freeing none, `ctm0a` being empty. The README gives `rm -f /tmp/ctm0a`, `sync`, `icheck -s /dev/rk0` and nothing after, as `icheck(8)` asks, which leaves in SimH the same file system but for the swap area. Both orders were tried on the board that day, with the kit's pack put on the card by `scripts/card.py`: each left a pack that differs from `guest/UNIX0.DSK` only in the times, `/etc/utmp` and the swap area, in which `icheck` finds nothing wrong, and on the first the talk said what SimH says; the card then had `guest/UNIX0.DSK` put back. cc compiles with `ctm0a` left there. The other three packs are sound, no block of them used or free twice, but their file systems are of 4872 blocks where the files are of 4767, so they are made whole as `guest/UNIX1.DSK` to `guest/UNIX3.DSK`, with `cp` and `truncate` as `guest/RK0.DSK` is; on the card they are `RK1.DSK` to `RK3.DSK`. The kit's `/etc/rc` mounts them at boot, rk1 on `/usr`, rk2 on `/usr/source` and rk3 on `/mnt`, on the board as in SimH; without them `/usr` is an empty directory. The talk wants the root pack alone, and SimH is given it alone. The manual is nroff source under `/mnt/man`, and the kit has no `man` to print it with: `nroff /mnt/man/man0/naa /mnt/man/man1/ls.1 | tr -d '\010_'` prints a page. `nroff` underlines a word by writing it, as many backspaces and as many underscores, which a terminal of today shows as the underscores alone, and the `tr` takes them out; in double quotes the shell of V6 hands `tr` a backslash more, and every 0 and 1 of the page goes as well.

The programs in `mac/` are the project's own.

## Working rules

- An OctoGo gap or fault is a result, not an obstacle. Report it to the user with a minimal reproducer and measured numbers, write it into `OCTOGO.md`, and use the idiomatic workaround meanwhile. When `ogo` has it fixed, take the workaround out and the entry with it.
- What another agent's review says is reproduced before it is acted on, as a test that fails, and the test stays.
- Code of general use, such as an SPI or SD driver and later video, is written as a package with no dependency on the emulator, so that it can move into OctoGo's standard library.
- What a binary does is measured on the board before it is written down, with the `ogo version` and the clock it was measured at.
- A test that fails is first suspected of being wrong itself. Of the differences from SimH met so far, one was the machine's, which counted an instruction it could not fetch as a step, and the rest were the test's: a generator that let a case reach SimH's console, a stale word of memory, an expectation miscounted.
- The repository is public since the evening of 2026-09-28, at https://gitlab.com/cznic/p2-11. It was made so, without announcement, when all of these held: LICENSE, AUTHORS and a README stating the status exist; the history holds no guest software and no personal data; the project builds with a tagged `ogo` release; and a stranger with a board can clone, `ogo run`, and watch a recognisable PDP-11 program at the terminal. The history has the review of 2026-09-27 with the paths of the machine it was written on, which the user knows of and keeps. Whatever is pushed is seen at once. Since 2026-09-30 GitLab mirrors it to https://github.com/modernc-org/p2-11, beside ogo's mirror there, with a push mirror whose token is a classic one of `public_repo` only: what is pushed to GitLab is on GitHub a moment later, and nothing is pushed to GitHub itself, which the next mirroring would overwrite. It is announced since 2026-09-30, by the user's blog post of that evening, http://modern-c.blogspot.com/2026/09/writing-something-real-in-octogo-pdp.html, and in a thread on the Parallax forums, https://forums.parallax.com/discussion/178200/p2-11-a-pdp-11-40-on-the-p2-edge-that-runs-unix-v6-and-rt-11-written-in-octogo.
- A commit is made when the user asks for one, and so is a push. The work is committed on a branch, in commits of one thing each, every one of which builds and passes the tests under the twin; `master` is fast-forwarded to the branch and pushed, and the branch deleted. Before anything is added, what would be added is looked at for guest software, for personal data and for the paths of this machine.

## License

BSD-3-Clause: the text of `../ogo/LICENSE` under "The p2-11 Authors", who are listed in AUTHORS. Every source file, script and Makefile begins with the header OctoGo's own sources carry, in the file's comment syntax:

```
// Copyright 2026 The p2-11 Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.
```

Code taken from elsewhere keeps its own notice, and is recorded before it is committed. `vga/vga_tile_driver.spin2` is Eric Smith's, of Total Spectrum Software, MIT, from github.com/totalspectrum/p2_vga_text at b50cec6 of 2023-02-12, unchanged, with that repository's COPYING beside it as `vga/LICENSE-p2_vga_text`, which gives the MIT license and the fonts'. The glyphs of `vga/font.ogo` are Unscii's, by Viznut, in the public domain, but for seven the script draws; `unscii-16-full`, which is GPL, is not used. The preference is to write from the DEC handbooks and to use other emulators as a reference for behaviour only.

The logo, `logo.svg`, is the project's own drawing, which `scripts/logo.py` makes of strokes: no typeface is in it, and nothing of DEC's or Parallax's marks, so that there is nothing in it to be too like what is someone's. The user said on 2026-09-28 that a logo matters little, and that being safe so is all that matters about one.

## Open decisions

- Whether the program is built `--unchecked` by those who run it. It is 13% faster.
