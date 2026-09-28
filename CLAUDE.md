# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

p2-11 is a PDP-11 emulator for the Parallax Propeller 2 (P2), written in OctoGo. Its purposes, in order:

1. To be an idiomatic example of a non-trivial OctoGo application. OctoGo is pre-release and this is the first real program written in it, so how the code reads outranks how clever it is.
2. To find what OctoGo is missing or gets wrong. What was found is in `OCTOGO.md`.
3. Fun.

**Status, 2026-09-28.** The processor, the console and the line clock exist. A program on the board says what it is, sizes memory by trapping, and echoes what is typed with the receiver interrupting; another waits for sixty interrupts of the clock, which take a second. The processor agrees with SimH's 11/40 on every one of the 2380 cases in the repository and of the 15,685 of a sweep. The disk controller exists, with files on the SD card for its packs, and does on the board what SimH's does with a program of 35 steps. The machine begins with RT-11 V4 on a pack, on the board as under the twin, and says in a talk of nine commands what SimH says, and leaves the pack as SimH leaves it. There is no memory management, so nothing that wants it runs: Unix is next after it. Keep this file in step as code lands, and delete what stops being true.

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

The repository needs `ogo` v0.44.0, of 2026-09-28, or a later one: `go install modernc.org/ogo@v0.44.0`. It is formatted as that formatter formats, which is as gofmt does. `ogo` on PATH is installed from `../ogo` by the user and the agent there, and may lag the tree or be ahead of what this file knows. Do not install over it. To try the tree's compiler, build it somewhere of your own, which reads `../ogo` and changes nothing there:

```sh
(cd ../ogo && go build -o "$SCRATCH/ogo-head" .)
```

Before a fault is reported, it is looked for with the tree's compiler: twice on 2026-09-27 what `ogo` on PATH did was already fixed there. And a compiler that is given a program to find a fault with is run under a cap, as `../ogo`'s own sweeps are, `ulimit -v 4000000` and `timeout -s KILL`: the tree's compiler of 2026-09-26 allocated without end on a shape this project wrote, and an uncapped run took the machine's memory.

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
```

`build` and `run` take `--unchecked` (no runtime checks), `--release` (reboot on a panic instead of halting the cog), `--clock 200MHz` (the default is 160 MHz, and 201 MHz is the most the compiler will ask for) and `--gostack N`. `test` takes `--clock`, `--gostack` and `-p port`.

A test is `func TestX(t *testing.T)`; it reports with `printf` or `println` and `t.Fail()`, there being no `Errorf`.

To run a binary and capture what it prints without a terminal session:

```sh
fuser -s /dev/ttyUSB0 && { echo "port busy"; exit 1; }
(sleep 8; printf 'Hello\r'; sleep 1; printf '\004'; sleep 1; printf '\x1d') |
	timeout 60 ogo loadp2 -t -NOEOF -p /dev/ttyUSB0 -b 230400 p2-11.binary 2>&1 |
	tr -d '\r' | grep -a -v 'Entering terminal mode' | grep -a -v '^( '
```

That is for a card with no `RK0.DSK`, with which the program runs `mac/demo.mac`. With one it is RT-11 that is typed to, and `scripts/talk.py` is the way to do that.

Bytes written into that pipe before the `\x1d` reach the program as console input, unchanged: a carriage return arrives as one. The program runs a benchmark of about three seconds before it says anything, and waits a second by the line clock before the program that reads the console is started; what is typed earlier is lost to the reset that starts it.

`*.p2asm` is the assembly the backend wrote. Reading it is how generated code is judged.

### What is generated, and by what

| File | Made by | From |
| --- | --- | --- |
| `pdp11/vectors_test.ogo` | `scripts/vectors.py` | SimH, about two minutes |
| `mac/demo.ogo`, and so on for every `.mac` | `scripts/mac.py mac/demo.mac` | the MACRO-11 source beside it |
| `mac/disk_table.ogo` | `scripts/rk.py` | SimH running `mac/disk.mac` with two packs the script makes, a second |

`scripts/tools.sh` fetches and builds SimH and the macro11 assembler into `tools/`, which git ignores, each at the revision the repository's files were made with. Nothing needs them but these three scripts. Made again with the same tools and arguments, the files come out as they are.

## The board

One P2-EC Edge module (512 KB hub RAM, no PSRAM) behind a Parallax PropPlug on `/dev/ttyUSB0`, which is the name the port had on the machine the project began on. The user has allowed its use.

It is shared with the agent working in `../ogo`, and two loaders on one port corrupt both runs. Run `fuser -s /dev/ttyUSB0` before every load. If the port is busy, say so and wait; never kill the other side's process, and never leave a loader holding the port.

| Pins | Function |
| --- | --- |
| P62, P63 | serial out and in: the loader, `println`, and the PDP-11 console in phase 1 |
| P56, P57 | LEDs |
| P58 | microSD and flash data out |
| P59 | microSD and flash data in |
| P60 | microSD chip select, flash clock |
| P61 | microSD clock, flash chip select |

The microSD slot has a card since 2026-09-28: an SDHC of 32 GB, 62,333,952 blocks, which the program is loaded with in place as it was without. The card agreed with the user is an SDHC of 4 to 32 GB, MBR with one FAT32 partition, holding image files with upper-case 8.3 names, each copied once onto the fresh filesystem so that it is contiguous. `TEST.DSK` on it is 4872 blocks of 512 bytes, each block filled with its own number as a little-endian 32-bit value. On this card the partition begins at block 8192 and `TEST.DSK` at block 38720. The tests write to blocks of `TEST.DSK` and to no others, and put back what was there. The pack of drive 0 is the file `RK0.DSK`, and so on to `RK7.DSK`. `RK0.DSK` is on the card since 2026-09-28, from block 43616: RT-11 V4, as `guest/RK0.DSK` has it but for what the talks have written, which is what SimH writes to its copy.

One load of about 130 on that day ended with the loader's `sendAddressSize: timeout`, and the twenty after it went well. Whether the card in the slot has to do with it is not known.

## A new machine

The work moved to another machine on 2026-09-28. What the repository does not hold, and a machine needs that is to go on with it:

| What | Where it comes from |
| --- | --- |
| `ogo` v0.44.0 or later | the user installs it from `../ogo`, or `go install modernc.org/ogo@v0.44.0` |
| Go, for `ogo` and the twin, which is built for 386 | the system; go1.27.1 was what there was |
| python3, gcc, make and git, for the scripts and what they build; `fuser`, of psmisc | the system |
| `tools/`, SimH and the assembler | `scripts/tools.sh`, which fetches and builds them |
| `guest/`, the kit of RT-11 and `RK0.DSK` | the user carries it; the repository must not |
| the port of the board | `/dev/ttyUSB0` where the project began, with the user in the group `dialout` |
| what the assistant remembers | `~/.claude/projects/`, in the directory named after the path of the repository with dashes for slashes, `memory/`; the user carries it. What is needed of it is in this file. |

`guest/RK0.DSK` is made of the kit so:

```sh
mkdir -p guest/rt11v4 && gzip -dc guest/rt11swre.tar.Z | tar -xf - -C guest/rt11v4
cp guest/rt11v4/Disks/rtv4_rk.dsk guest/RK0.DSK && chmod 644 guest/RK0.DSK
truncate -s 2494464 guest/RK0.DSK
```

That all is there is seen in this order, each of which says nothing or `ok`:

```sh
ogo version && ogo fmt -l . && ogo build
scripts/twin.sh                    # with guest/ and tools/ there, the talk with RT-11 among it
ogo test ./...                     # the card in the slot
scripts/talk.py                    # RT-11 on the board and in SimH
```

What was left for where the card is: `ogo` v0.44.0 was measured without the card, so the tests of the card and of the disk with it, the talk on the board, and what a block of the card takes have not run with it. And `sd` still keeps the sixteen bytes it reads a card's size from in the `Card`, which it did because an error could not be returned that came of a call given a local buffer. It can since `ogo` c888892, and the bytes can be a local of `size` again, once there is a card to test that with.

## Architecture

| Package | What it is | Imports `p2` |
| --- | --- | --- |
| the root | the program: the cogs, the serial line, what is loaded and run | yes |
| `pdp11` | the machine: processor, memory, bus, traps and interrupts | no |
| `dl11` | the DL11 serial line unit, which is the console | no |
| `kw11` | the KW11-L line clock | no |
| `rk11` | the RK11 disk controller and its RK05 drives | no |
| `sd` | an SD card's blocks, read and written over SPI | yes |
| `fat` | where on a disk a file of its FAT32 volume is | no |
| `mac` | the PDP-11 programs the emulator carries, source and assembled | no |

Only the root and `sd` know the Propeller 2. The others are Go once they have a package clause, which is what `scripts/twin.sh` relies on. `sd` and `fat` know nothing of the emulator, and are written to be of use without it.

**The card** is driven by the code, pin by pin, with no smart pin and no cog of its own. What is read is checked against the card's checksum and what is written is checked by the card, which is how a loop that read too early was found: the compiler had made it faster. The time between the card's clock falling and its bit being read is in the source since, `settle` in `sd/sd.ogo`, and what it was measured to have to be. `fat` does not read files: a file written once to an empty volume is one run of blocks, `fat` says where it begins and refuses one that is in pieces, and what uses the image reads and writes the card's blocks.

**The disk** does a transfer on the cog of `Serve`, or on the machine's where no cog serves, which is how the tests of `rk11` run under the twin. A seek takes no time and ends when the controller has been looked at twice, the controller being ready before the drive as it is with an arm to move. A pack that cannot be read is the checksum error of the RK11, which a program tries again, and one that cannot be written its drive error. `mac/boot.mac` is the bootstrap, the project's own: it leaves in the registers what the bootstraps of a PDP-11 leave there for what a pack begins with.

**Five cogs.** `main` steps the machine with `Machine.Run`. `receive` does nothing but read the serial line, since nothing is buffered behind `p2.ReadByte` and a byte arriving while the cog is elsewhere is lost. `transmit` writes it. `line` counts the cycles of the power line for the clock, `hz` of them a second, which is 60. It times each from when its second began, so that what one is late by is not added to the next, and in microseconds, which is good to one and forgives a cycle that is late. `turn` opens the card, puts the packs it finds in their drives, and then moves blocks between the card and memory as the controller orders.

**Between cogs there is no lock and no channel.** Every variable two cogs share is written by one of them only: `dl11.Line` has a ring whose head the receiving cog writes and whose tail the machine's cog writes, and a count of bytes written by the program beside a count of bytes sent by the transmitting cog; `kw11.Clock` has a count of cycles the counting cog writes beside the count of them the register knows of; `rk11.Controller` has an order with its number, which the machine's cog writes, and a report with the number of the order it is of, which the cog of the disk writes. Memory is the exception, as it is on a bus that a device can take: the cog of the disk reads and writes words of it through `Machine.Fetch` and `Machine.Store`, while the program runs. A channel's rendezvous would stall the cog that reads the line.

**A device** implements `pdp11.Device` and is attached at an address range and a priority. The machine reads and writes its registers through `Read` and `Write(a, v, mask)`, the mask saying which bits a byte write touches. It learns of interrupts by asking: `Request` answers the vector the device wants, `Granted` that it was taken. The devices are asked from the highest priority down, every `pollEvery` instructions and as soon as the program has touched a device or the status word, and again after every interrupt taken, until none is due that the status word lets in. What a device's other cogs have done is brought into its registers when the machine next calls it.

**What is handed to another cog is not called back.** A device's `Reset` runs on the machine's cog and may not write what another cog owns. So the console's does not cancel a byte that is on its way: the transmitter is ready when the byte has left. There is one byte on its way at most, and a program that writes while the transmitter is busy overwrites it, as in a UART. The disk's does not leave a transfer to go on into memory that is the program's again: it says which order is abandoned, which the other cog looks at between two blocks, and waits.

**A pin is the cog's that drives it.** What the cogs drive is ORed, so a pin one cog holds high is not another's to pull low. The card is opened by the cog that uses it, `turn`, and a test that uses the card on its own cog closes it, which lets go of the pins.

**Time is counted in instructions** where a device has none of its own. `Machine.Now` says how far the machine has come, a machine that waits coming as far as one that runs, and the console hands the program what has arrived no closer together than `apart` instructions, 1000 as in SimH. Without that RT-11 took a line that was sent at once the wrong way round: its receiver's interrupt goes on at priority 0 after ten instructions, and counts on the next character taking a character's time. A terminal at 230400 baud leaves it five instructions.

**Traps** are bits in `Machine.traps`, the most urgent lowest. An access that fails requests one and reads as zero, there being nothing to unwind with, and what follows asks `m.traps&aborts != 0` before it does anything else: before the instruction changes anything, and before the next access of a sequence, a trap's two pushes among them. `attention` is a bit among the traps that is no trap: whatever needs the instructions to stop following one another for a moment sets it, so that the loop in `Run` tests one word.

**The order of things inside an instruction is the 11/40's**, down to what is left behind when an access fails halfway, and that is what the vectors hold the code to. SimH's `pdp11_cpu.c` was the reference for behaviour; nothing of it is copied.

**The code is shaped by what a call costs** (`OCTOGO.md`, 1). `Run` fetches where it stands, `execute` finds the instruction's function, an operand in a register is dealt with where it is met, and `read`, `write` and `address` are called for operands in memory only. There are no helpers that only test something. Do not "tidy" that into small methods without measuring: the first version was written that way and ran a fifth as fast.

## Tests

- **The vectors**, `pdp11/vector_test.ogo` over `pdp11/vectors_test.ogo`: 2380 cases of a machine before and after one or two steps, the after being what SimH's 11/40 made of it, with whether it halted. They go through every instruction and addressing mode, the traps, the status word at its address, the stack limit, and 300 cases of whatever sixteen bits came up.
- **By hand**: `pdp11/machine_test.ogo` for the bus, interrupts, the console's switches, what `Run` answers and that a program run ends where the same program stepped ends, with a device of its own; `dl11/dl11_test.ogo` for the line by itself and for the line as console of a machine that runs `mac/demo.mac`, whose output is compared with what it says in SimH; `kw11/kw11_test.ogo` for the clock by itself and for the clock on a machine, which runs `mac/ticks.mac` to where it ends in SimH, and keeps the cycles that pass while the processor's priority holds them back for one interrupt, as SimH does.
- **The card**: `fat/fat_test.ogo` finds files on a disk that is made up block by block as it is read, with a directory in two clusters that are not neighbours and files in one piece and in several, under the twin and on the board. `sd/sd_test.ogo` reads the card in the slot and writes nothing. `card_test.ogo` in the root reads all of `TEST.DSK` and compares it, and writes seventeen blocks of it, reads them and puts back what they had. The last two run on the board only, and pass on a board with no card, or no such file, saying that nothing was tested.
- **The disk**: `mac/disk.mac` has the controller do 35 things, among them every function, every error a program can cause, interrupts, and registers written a byte at a time, and writes the registers after each into a table. `scripts/rk.py` has SimH make that table, and `rk11/rk11_test.ogo` compares: with the controller doing the transfers itself, and with the test as the cog of the disk after every 1, 7, 49 and 343 instructions. What the program cannot ask is tested by hand: a pack that fails, a drive that is busy, a pack taken out, and the bootstrap, which leaves in SimH what it leaves here. `disk_test.ogo` in the root runs the program with the cog of the disk and `TEST.DSK` on the card, on the board only.
- **A system**: `rk11/host_test.go` is Go, for the twin only, and is skipped where `guest/RK0.DSK` or SimH is not. It has the machine begin with the pack and holds a talk with RT-11 in which a file is copied, compared and deleted, has SimH do the same, and compares what the two consoles said and what the two packs then hold. Each command waits for the prompt after the one before it, so that nothing is typed into what the system says. It found the console's pace, which no test of the project's own programs had: they wait for a character and have done with it before the next.
- **A system on the board**: `scripts/talk.py` holds that talk with the board, through the loader's terminal, and with SimH, and compares what the two have said. On 2026-09-28 they said the same 1558 bytes, in the three builds, and the pack on the card was then what SimH's copy was: a program made for the day read the file from the card and summed it, and the sums were those of the copy. A talk leaves the pack so that the next one says the same.
- **Between cogs**, `cogs_test.ogo` in the root: 20,000 bytes each way through the console with the cog of the other end running at once, and resets with a byte on its way; and the clock with the program's own cog counting, by which `mac/ticks.mac` is to take a second. The tests of `dl11` are one cog taking the part of three in turn; this is the only place that asks whether a cog sees what another wrote, in the order it was written. It runs on the board only.
- **A sweep** is a larger table made elsewhere and run under the twin only: `scripts/vectors.py -n 12000 -scale 2 -o FILE` takes a quarter of an hour; put FILE in place of `pdp11/vectors_test.go`, under a package clause, in a twin kept with `scripts/twin.sh -k DIR`, and run `GOARCH=386 go test ./pdp11` there.

The twin is for a fast answer about the emulator's logic and for what a board has not the time for. It is not a verdict on what the board does; the board is. `ogo help test` states OctoGo's position. A `.go` file beside the `.ogo` files of a package goes into the twin as it is: `pdp11/host_test.go` has the vectors look at all of memory after every case, for a word written that no case names, where the board looks once at the end.

A program that is compared with SimH must not depend on how long a drive takes, which is SimH's guess and not this machine's: it waits for what it wants to see. SimH's sector counter is a random number, and is left out of the table.

A case the generator makes must not depend on what SimH has and the machine under test has not. SimH keeps its console and its clock whatever it is told, so the generator sets breakpoints on their registers and drops a case that hits one; and it clears all of memory before each case and lists every word that is not zero after it.

A review by the Codex agent on 2026-09-27 found four faults the tests had not, all of them in what happens between instructions or between cogs and none in an instruction: a reset with a byte on its way, a trap's second push after its first had failed, an interrupt let in by the one before it, and what `Run` answers when its last instruction is a WAIT. Each has its test now. That is where to look next: combinations of events, not more instructions.

## What it costs, measured

P2-EC, `mac/bench.mac`: 303,004 instructions, of which a third each are `ADD R2,(R1)+`, `INC R3` and `SOB`.

| Build | Instructions a second |
| --- | --- |
| checked, 160 MHz | 114,904 |
| `--unchecked`, 160 MHz | 131,113 |
| `--unchecked --clock 200MHz` | 163,874 |

That is with `ogo` v0.44.0, the console, the clock and the disk on the bus, and the machine counting how far it has come. With the compilers of the same day before it, the three ran 120,287, 134,369 and 167,962 with the console alone, 119,811, 133,071 and 166,302 with the console and the clock, 116,629, 133,364 and 166,760 with the disk as well, and 116,540, 131,455 and 164,318 with the count. A device more to ask every `pollEvery` instructions costs about 1%, and so does where the build has put things: with the disk in the program and not on the bus the first two ran 117,762 and 131,912.

Sixty interrupts of the clock take 985 to 999 ms from when the program enables them, the first cycle being under way by then.

The talk with RT-11, from the loader's first byte to the last prompt, of which six seconds are the loader, the benchmark and the clock's second: 36 s checked, 32 s `--unchecked`, and 26 s `--unchecked --clock 200MHz`.

A block of the card, with its command and its checksum:

| Build | Microseconds to read a block |
| --- | --- |
| checked, 160 MHz | 1610 |
| `--unchecked`, 160 MHz | 1239 |
| `--unchecked --clock 200MHz` | 1050 |

To write one takes 2.5 to 5 ms, most of which is the card's. All of `TEST.DSK` is read and compared in 9.6 s by the tests, which are built checked. With `settle` at 0, 1 or 2 the first thing of any length the card sends fails its checksum, at 160 MHz and at 200 MHz alike, and with 3 to 6 all of 500 blocks are read; it is 8. These were measured with `ogo` 3875205f89d4, of the day before v0.44.0, as was the talk with RT-11: the card was not there when v0.44.0 was.

In clocks at 160 MHz, `--unchecked`: a call and its return 75 to 115; a field of the machine read and tested, 30; a `switch`, about 5 for every case it passes. A function with a branch in it is never inlined. The measurements and their programs are in `OCTOGO.md`. Measure again after an `ogo` upgrade before relying on any of it: the compiler of 2026-09-28 made the emulator 6 to 8% faster by making a named constant its value, where the three before it had agreed to within 2%.

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
| KW11-L line clock | done |
| the SD card, and a file's place on its FAT32 volume | done |
| RK11 disk controller, with files on the card for packs | done |
| RT-11 V4, single job | begins, and does in a talk of nine commands what it does in SimH |
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

What is in `guest/` since 2026-09-28, put there by the user: `rt11swre.tar.Z`, RT-11 V4 on RK05 from SimH's software kits, with the license quoted above. `guest/rt11v4/` is the kit unpacked, whose `rtv4_rk.dsk` is of 3267 blocks, and `guest/RK0.DSK` that pack made a whole one, 2,494,464 bytes, which is what goes to the card. SimH begins with it as an 11/40 without memory management and 28K words: RT-11SJ V04.00C.

The programs in `mac/` are the project's own.

## Working rules

- An OctoGo gap or fault is a result, not an obstacle. Report it to the user with a minimal reproducer and measured numbers, write it into `OCTOGO.md`, and use the idiomatic workaround meanwhile. When `ogo` has it fixed, take the workaround out and the entry with it.
- What another agent's review says is reproduced before it is acted on, as a test that fails, and the test stays.
- Code of general use, such as an SPI or SD driver and later video, is written as a package with no dependency on the emulator, so that it can move into OctoGo's standard library.
- What a binary does is measured on the board before it is written down, with the `ogo version` and the clock it was measured at.
- A test that fails is first suspected of being wrong itself. Of the differences from SimH met so far, one was the machine's, which counted an instruction it could not fetch as a step, and the rest were the test's: a generator that let a case reach SimH's console, a stale word of memory, an expectation miscounted.
- The repository is private, and the user has delegated the timing of making it public. Say so when all of these hold: LICENSE, AUTHORS and a README stating the status exist; the history holds no guest software and no personal data; the project builds with a tagged `ogo` release; and a stranger with a board can clone, `ogo run`, and watch a recognisable PDP-11 program at the terminal. They hold since `ogo` v0.44.0 of 2026-09-28, and the user was told so that day. The history has the review of 2026-09-27 with the paths of the machine it was written on, which the user knows of and keeps.
- A commit is made when the user asks for one, and so is a push. The work is committed on a branch, in commits of one thing each, every one of which builds and passes the tests under the twin; `master` is fast-forwarded to the branch and pushed, and the branch deleted. Before anything is added, what would be added is looked at for guest software, for personal data and for the paths of this machine.

## License

BSD-3-Clause: the text of `../ogo/LICENSE` under "The p2-11 Authors", who are listed in AUTHORS. Every source file, script and Makefile begins with the header OctoGo's own sources carry, in the file's comment syntax:

```
// Copyright 2026 The p2-11 Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.
```

Code taken from elsewhere keeps its own notice, and is recorded before it is committed. The preference is to write from the DEC handbooks and to use other emulators as a reference for behaviour only.

## Open decisions

- Whether the program is built `--unchecked` by those who run it. It is 14% faster.
- A lock shared with `../ogo` around board access, offered and not yet answered.
