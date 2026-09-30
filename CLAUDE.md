# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

p2-11 is a PDP-11 emulator for the Parallax Propeller 2 (P2), written in OctoGo. Its purposes, in order:

1. To be an idiomatic example of a non-trivial OctoGo application. OctoGo is pre-release and this is the first real program written in it, so how the code reads outranks how clever it is.
2. To find what OctoGo is missing or gets wrong. What was found is in `OCTOGO.md`.
3. Fun.

**Status, 2026-09-30.** The processor, the console and the line clock exist. A program on the board says what it is, sizes memory by trapping, and echoes what is typed with the receiver interrupting; another waits for sixty interrupts of the clock, which take a second. The processor agrees with SimH's 11/40 on every one of the 2902 cases in the repository, of which 522 are the memory management's, and of the 15,685 of a sweep made before it had any. The disk controller exists, with files on the SD card for its packs, and does on the board what SimH's does with a program of 35 steps. The machine begins with RT-11 V4 on a pack, on the board as under the twin, and says in a talk of nine commands what SimH says, and leaves the pack as SimH leaves it. The KT11-D memory management exists since 2026-09-29, with 248 KB of memory, and costs a tenth of the speed with the unit off and an eighth more with it on. Unix V6 runs since the same day: it begins from the root pack of SimH's kit, on the board as under the twin, logs in, compiles a C program with its own compiler and runs it, and says in a talk of fourteen lines what SimH says. Keep this file in step as code lands, and delete what stops being true.

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
scripts/talk.py -talk v6           # the talk with Unix V6, its pack being on the card, a minute and a half
scripts/record.py                  # a session with V6 on the board, as v6-demo.cast for the README's GIF, two minutes
scripts/card.py put guest/RK0.DSK RK0.DSK   # the pack onto the card through the board, two minutes
scripts/card.py put guest/UNIX0.DSK RK0.DSK # the root pack of Unix V6 there instead
scripts/card.py sum RK0.DSK guest/RK0.DSK   # which blocks of the pack on the card differ from the file, 15 s
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

Bytes written into that pipe before the `\x1d` reach the program as console input, unchanged: a carriage return arrives as one. The program runs a benchmark of about three seconds before it says anything, and waits a second by the line clock before the program that reads the console is started; what is typed earlier is lost to the reset that starts it.

`*.p2asm` is the assembly the backend wrote. Reading it is how generated code is judged.

### What is generated, and by what

| File | Made by | From |
| --- | --- | --- |
| `pdp11/vectors_test.ogo` | `scripts/vectors.py` | SimH, one to two minutes |
| `mac/demo.ogo`, and so on for every `.mac` | `scripts/mac.py mac/demo.mac` | the MACRO-11 source beside it |
| `mac/disk_table.ogo` | `scripts/rk.py` | SimH running `mac/disk.mac` with two packs the script makes, a second |
| `logo.svg` | `scripts/logo.py` | nothing: the name drawn as strokes, its ones the toggle switches of a front panel |
| `v6-demo.gif` | `scripts/record.py`, then `agg --idle-time-limit 120 --last-frame-duration 5 v6-demo.cast v6-demo.gif`, then `scripts/poster.py v6-demo.gif`, which puts the last frame first, held 3 s, since what does not play a GIF shows its first frame, and a session's first is an empty terminal | a session with Unix V6 on the board, its root pack on the card, two minutes |

`scripts/tools.sh` fetches and builds SimH and the macro11 assembler into `tools/`, which git ignores, each at the revision the repository's files were made with. Nothing needs them but these three scripts. Made again with the same tools and arguments, the files come out as they are. The recording is the exception: made again, it has the timing of its own session; and agg, asciinema's converter, is not among the tools, nor asciinema, which plays the `.cast`. `scripts/poster.py` wants Pillow and numpy, and checks that every frame it writes is the frame it read: Pillow's `quantize` comes near a colour, not to it.

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

The microSD slot has a card since 2026-09-28: an SDHC of 32 GB, 62,333,952 blocks, which the program is loaded with in place as it was without. The card agreed with the user is an SDHC of 4 to 32 GB, MBR with one FAT32 partition, holding image files with upper-case 8.3 names, each copied once onto the fresh filesystem so that it is contiguous. `TEST.DSK` on it is 4872 blocks of 512 bytes, each block filled with its own number as a little-endian 32-bit value. On this card the partition begins at block 8192 and `TEST.DSK` at block 38720. The tests write to blocks of `TEST.DSK` and to no others, and put back what was there. The pack of drive 0 is the file `RK0.DSK`, and so on to `RK7.DSK`. `RK0.DSK` is on the card since 2026-09-28, from block 43616. It held RT-11 V4 until 2026-09-29, as `guest/RK0.DSK` has it but for what the talks have written, which is what SimH writes to its copy; it holds since the root pack of Unix V6, `guest/UNIX0.DSK` but for what the talks with it have written. `RK1.DSK`, `RK2.DSK` and `RK3.DSK` are on it since the evening of 2026-09-29, the other three packs of V6, which the user copied with the card out, each in one piece. A file goes onto the card without the card coming out: `scripts/card.py put guest/RK0.DSK RK0.DSK`, which is how the pack was put back on 2026-09-28 after an editor's output file, left on it by hand, had the talk on the board disagree with SimH; "A new machine" tells of it.

One load of about 130 on that day ended with the loader's `sendAddressSize: timeout`, and the twenty after it went well. Whether the card in the slot has to do with it is not known.

On 2026-09-29, with `ogo` v0.46.0, whose loader is v0.44.0's, 4 loads of 40 ended with the loader's `Error writing port`: three in `ogo test ./...`, which then says of the package `[the board produced no result]`, and one in `ogo run`. Each went well when it was done again, and so did ten loads of one package in a row. The loader takes a write that comes back short for that error, and does not say why. On 2026-09-30 one load of nine ended so, again in `ogo test ./...`.

## A new machine

The work moved to another machine on 2026-09-28. What the repository does not hold, and a machine needs that is to go on with it:

| What | Where it comes from |
| --- | --- |
| `ogo` v0.44.0 or later | the user installs it from `../ogo`, or `go install modernc.org/ogo@v0.44.0` |
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

## Architecture

| Package | What it is | Imports `p2` |
| --- | --- | --- |
| the root | the program: the cogs, the serial line, what is loaded and run | yes |
| `pdp11` | the machine: processor, memory, bus, traps and interrupts | no |
| `dl11` | the DL11 serial line unit, which is the console | no |
| `kw11` | the KW11-L line clock | no |
| `rk11` | the RK11 disk controller and its RK05 drives | no |
| `sd` | an SD card's blocks, read and written over SPI | yes |
| `card` | a second program: puts a file of this machine into a file on the card and sums one there, over the serial line, for `scripts/card.py` | yes |
| `fat` | where on a disk a file of its FAT32 volume is | no |
| `mac` | the PDP-11 programs the emulator carries, source and assembled | no |

Only the root, `card` and `sd` know the Propeller 2. The others are Go once they have a package clause, which is what `scripts/twin.sh` relies on. `sd` and `fat` know nothing of the emulator, and are written to be of use without it.

**The card** is driven by the code, pin by pin, with no smart pin and no cog of its own. What is read is checked against the card's checksum and what is written is checked by the card, which is how a loop that read too early was found: the compiler had made it faster. The time between the card's clock falling and its bit being read is in the source since, `settle` in `sd/sd.ogo`, and what it was measured to have to be. `fat` does not read files: a file written once to an empty volume is one run of blocks, `fat` says where it begins and refuses one that is in pieces, and what uses the image reads and writes the card's blocks. Of a volume whose tables are no mirrors of each other it reads the one the volume names, which is what says where a file is; one that names a table it has not is damaged.

**A file goes onto the card** through the board: `card/` is a program of its own, which `scripts/card.py` builds and loads in place of the emulator and speaks to in lines through the loader's terminal. A block is its 512 bytes after a header that sums them, escaped where a byte is one the terminal would take for itself, and four blocks are on their way at once; a cog reads the line into a ring and `main` writes the card from it, says of each block whether it arrived as summed and is written, and afterwards sums every block of the file back for the script to compare. It cannot make a file: the file must be on the card already, and `fat` says where it is.

**The disk** does a transfer on the cog of `Serve`, or on the machine's where no cog serves, which is how the tests of `rk11` run under the twin. A seek takes no time and ends when the controller has been looked at twice, the controller being ready before the drive as it is with an arm to move. A pack that cannot be read is the checksum error of the RK11, which a program tries again, and one that cannot be written its drive error. `mac/boot.mac` is the bootstrap, the project's own: it leaves in the registers what the bootstraps of a PDP-11 leave there for what a pack begins with.

**Five cogs.** `main` steps the machine with `Machine.Run`. `receive` does nothing but read the serial line, since nothing is buffered behind `p2.ReadByte` and a byte arriving while the cog is elsewhere is lost. `transmit` writes it, seven bits of each byte, as SimH's console does: V6 sends a character with its even parity in the eighth bit, which a terminal of today shows as another character. `line` counts the cycles of the power line for the clock, `hz` of them a second, which is 60. It times each from when its second began, so that what one is late by is not added to the next, and in microseconds, which is good to one and forgives a cycle that is late. `turn` opens the card, puts the packs it finds in their drives, and then moves blocks between the card and memory as the controller orders.

**Between cogs there is no lock and no channel.** Every variable two cogs share is written by one of them only: `dl11.Line` has a ring whose head the receiving cog writes and whose tail the machine's cog writes, and a count of bytes written by the program beside a count of bytes sent by the transmitting cog; `kw11.Clock` has a count of cycles the counting cog writes beside the count of them the register knows of; `rk11.Controller` has an order with its number, which the machine's cog writes, and a report with the number of the order it is of, which the cog of the disk writes. Memory is the exception, as it is on a bus that a device can take: the cog of the disk reads and writes words of it through `Machine.Fetch` and `Machine.Store`, while the program runs. A channel's rendezvous would stall the cog that reads the line.

**A device** implements `pdp11.Device` and is attached at an address range and a priority. The machine reads and writes its registers through `Read` and `Write(a, v, mask)`, the mask saying which bits a byte write touches. It learns of interrupts by asking: `Request` answers the vector the device wants, `Granted` that it was taken. The devices are asked from the highest priority down, every `pollEvery` instructions and as soon as the program has touched a device or the status word, and again after every interrupt taken, until none is due that the status word lets in. What a device's other cogs have done is brought into its registers when the machine next calls it.

**What is handed to another cog is not called back.** A device's `Reset` runs on the machine's cog and may not write what another cog owns. So the console's does not cancel a byte that is on its way: the transmitter is ready when the byte has left. There is one byte on its way at most, and a program that writes while the transmitter is busy overwrites it, as in a UART. The disk's does not leave a transfer to go on into memory that is the program's again: it says which order is abandoned, which the other cog looks at between two blocks, and waits.

**A pin is the cog's that drives it.** What the cogs drive is ORed, so a pin one cog holds high is not another's to pull low. The card is opened by the cog that uses it, `turn`, and a test that uses the card on its own cog closes it, which lets go of the pins.

**Time is counted in instructions** where a device has none of its own. `Machine.Now` says how far the machine has come, a machine that waits coming as far as one that runs, and the console hands the program what has arrived no closer together than `apart` instructions, 1000 as in SimH. Without that RT-11 took a line that was sent at once the wrong way round: its receiver's interrupt goes on at priority 0 after ten instructions, and counts on the next character taking a character's time. A terminal at 230400 baud leaves it five instructions.

**Traps** are bits in `Machine.traps`, the most urgent lowest. An access that fails requests one and reads as zero, there being nothing to unwind with, and what follows asks `m.traps&aborts != 0` before it does anything else: before the instruction changes anything, and before the next access of a sequence, a trap's two pushes among them. `attention` is a bit among the traps that is no trap: whatever needs the instructions to stop following one another for a moment sets it, so that the loop in `Run` tests one word.

**The order of things inside an instruction is the 11/40's**, down to what is left behind when an access fails halfway, and that is what the vectors hold the code to. SimH's `pdp11_cpu.c` was the reference for behaviour; nothing of it is copied.

**Memory management** is the KT11-D, in `pdp11/mmu.ogo`: what a page's two registers come to is worked out when they are written, into a `page` with where it begins and what offsets and cycles it admits, so that `read` and `write` do their arithmetic once, inline; `space` says whose pages an access goes through, the current mode's but while MFPI and MTPI reach into the previous mode's and a trap into the kernel's. A read that will be written back asks the page for writing, as the bus cycle DATIP does, so that an abort comes before the read. `Run` keeps SR0 and the page the program is in in registers, since a write to a register of the unit and a change of mode ask for attention, which ends its run of instructions; that is what took the unit's cost from a third to an eighth. The console, `Examine` and `Deposit`, reads memory as it is on the bus, whatever the map says, and so do `Fetch` and `Store`, whose addresses are the bus's 18 bits. There is no SR1: 177574 answers nothing, as on the 11/40. A page that goes past the end of the bus goes on at 0, the carry out of 18 bits being lost, and RESET in the kernel's mode turns the unit off and clears what it recorded of an abort, as the INIT it sends does.

**The code is shaped by what a call costs** (`OCTOGO.md`, 1). `Run` fetches where it stands, `execute` finds the instruction's function, an operand in a register is dealt with where it is met, and `read`, `write` and `address` are called for operands in memory only. There are no helpers that only test something. Do not "tidy" that into small methods without measuring: the first version was written that way and ran a fifth as fast.

## Tests

- **The vectors**, `pdp11/vector_test.ogo` over `pdp11/vectors_test.ogo`: 2902 cases of a machine before and after one or two steps, the after being what SimH's 11/40 made of it, with whether it halted. They go through every instruction and addressing mode, the traps, the status word at its address, the stack limit, and 300 cases of whatever sixteen bits came up. Every case begins with the registers of the memory management holding a background, each page where its address says and the unit off, and names the registers it sets and those that changed, SR2 among them after every case; one case in eight has the unit on. The 522 cases that are the unit's put operands in pages that are elsewhere, through every addressing mode; abort in every way there is, a page not there, read-only or shorter than the address, growing either way, on a read, a write and a read that will be written back, in both modes, and see in the second step what the trap left frozen; fetch an instruction or the word after it from such a page; reach into the previous mode's space with MFPI and MTPI; read and write every register, in words and bytes; go past the end of the bus, where a page at 777700 goes on at 0, reading, writing and fetching either side of it; and RESET with the unit on, which turns it off in the kernel's mode and does nothing in the user's. The last two groups have random choices of their own, so that adding them left the cases before them as they were. SimH's 11/40 has an SR1 at 177574 that no 11/40 had, so the generator keeps cases off it as it keeps them off the console.
- **By hand**: `pdp11/machine_test.ogo` for the bus, interrupts, the console's switches, what `Run` answers and that a program run ends where the same program stepped ends, with a device of its own, and for what the vectors cannot reach of the memory management: the console reading memory beneath the map and a trap from the user's space taking its vector and its stack through the kernel's; `pdp11/host_test.go`, under the twin only, for the console on machines of 65,535 words and more, up to all that 18 bits reach, which no test binary on the board has the room for beside the vectors; `dl11/dl11_test.ogo` for the line by itself and for the line as console of a machine that runs `mac/demo.mac`, whose output is compared with what it says in SimH; `kw11/kw11_test.ogo` for the clock by itself and for the clock on a machine, which runs `mac/ticks.mac` to where it ends in SimH, and keeps the cycles that pass while the processor's priority holds them back for one interrupt, as SimH does.
- **The card**: `fat/fat_test.ogo` finds files on a disk that is made up block by block as it is read, with a directory in two clusters that are not neighbours and files in one piece and in several, and on a volume whose two tables are no mirrors of each other, under the twin and on the board. `sd/sd_test.ogo` reads the card in the slot and writes nothing. `card_test.ogo` in the root reads all of `TEST.DSK` and compares it, and writes seventeen blocks of it, reads them and puts back what they had. The last two run on the board only, and pass on a board with no card, or no such file, saying that nothing was tested.
- **The disk**: `mac/disk.mac` has the controller do 35 things, among them every function, every error a program can cause, interrupts, and registers written a byte at a time, and writes the registers after each into a table. Memory ends for it where the bus ends, at 760000, which the extension bits of the control register reach, so SimH is given 248 KB for it and the machines that run it have as much. `scripts/rk.py` has SimH make that table, and `rk11/rk11_test.ogo` compares: with the controller doing the transfers itself, and with the test as the cog of the disk after every 1, 7, 49 and 343 instructions. What the program cannot ask is tested by hand: a pack that fails, at once or after a block, the bus address moving or not, a drive that is busy, a pack taken out, and the bootstrap, which leaves in SimH what it leaves here. `disk_test.ogo` in the root runs the program with the cog of the disk and `TEST.DSK` on the card, on the board only.
- **A system**: `rk11/host_test.go` is Go, for the twin only, and is skipped where `guest/RK0.DSK` or SimH is not. It has the machine begin with the pack and holds a talk with RT-11 in which a file is copied, compared and deleted, has SimH do the same, and compares what the two consoles said and what the two packs then hold. Each command waits for the prompt after the one before it, so that nothing is typed into what the system says. It found the console's pace, which no test of the project's own programs had: they wait for a character and have done with it before the next.
- **A system, Unix**: `TestV6` in the same file holds a talk of fourteen lines with Unix V6, begun from `guest/UNIX0.DSK`: it logs in, lists, writes a C program with echo, compiles it with cc and runs it, removes it, sums a file and syncs. What the two consoles said is compared; the packs are not, every file read having its time of access written, and the two machines keeping time differently. Nothing the talk says depends on the time or on what a talk before it left: the compiler's temporary files give /tmp the time of the talk, so `ls /` shows no times and `ls -l /lib` shows the kit's. Two things the talk with RT-11 had not taught: a talk types a moment after the prompt, a quarter of a second of the board's, because getty sets its terminal up again just after prompting and that flushes what came before, which on the board is the first letter of the name; and a talk ends with sync, twice, since the next load resets the board while V6 still holds its last writes in the buffer cache, which left the pack on the card with a directory from the middle of a compile.
- **A system on the board**: `scripts/talk.py` holds that talk with the board, through the loader's terminal, and with SimH, and compares what the two have said. It compares the board's bytes as they came since 2026-09-29: it had dropped their eighth bit, as the talks under the twin drop it, and so did not see V6's parity there, which the user's terminal did, and made garbage of; the talk with V6 then failed until `transmit` sent seven bits. On 2026-09-28 they said the same 1558 bytes, in the three builds, and the pack on the card was then what SimH's copy was: a program made for the day read the file from the card and summed it, and the sums were those of the copy. A talk leaves the pack so that the next one says the same. With `-talk v6` it holds the talk with Unix V6, whose root pack is then to be on the card: on 2026-09-29 the board said what SimH said, 1357 bytes, in 96 s and then in 94 s, the second time being the proof that a talk leaves the pack so. It said so again that evening with `ogo` v0.46.0, in 94 s, and then with the other three packs of the kit on the card as well, which V6 mounts and SimH is not given, in 95 s. What the pack on the card holds is compared with the file by `scripts/card.py sum RK0.DSK guest/RK0.DSK`, which names the blocks that differ: after a talk, blocks 8 to 9 and 38 to 45, the second directory segment and the swap area, and 1423 to 1458, where the copied file was.
- **Between cogs**, `cogs_test.ogo` in the root: 20,000 bytes each way through the console with the cog of the other end running at once, and resets with a byte on its way; and the clock with the program's own cog counting, by which `mac/ticks.mac` is to take a second. The tests of `dl11` are one cog taking the part of three in turn; this is the only place that asks whether a cog sees what another wrote, in the order it was written. It runs on the board only.
- **A sweep** is a larger table made elsewhere and run under the twin only: `scripts/vectors.py -n 12000 -scale 2 -o FILE` takes a quarter of an hour; put FILE in place of `pdp11/vectors_test.go`, under a package clause, in a twin kept with `scripts/twin.sh -k DIR`, and run `GOARCH=386 go test ./pdp11` there.

The twin is for a fast answer about the emulator's logic and for what a board has not the time for. It is not a verdict on what the board does; the board is. `ogo help test` states OctoGo's position. A `.go` file beside the `.ogo` files of a package goes into the twin as it is: `pdp11/host_test.go` has the vectors look at all of memory after every case, for a word written that no case names, where the board looks once at the end.

A program that is compared with SimH must not depend on how long a drive takes, which is SimH's guess and not this machine's: it waits for what it wants to see. SimH's sector counter is a random number, and is left out of the table.

A case the generator makes must not depend on what SimH has and the machine under test has not. SimH keeps its console and its clock whatever it is told, so the generator sets breakpoints on their registers and drops a case that hits one; and it clears all of memory before each case and lists every word that is not zero after it.

A review by the Codex agent on 2026-09-27 found four faults the tests had not, all of them in what happens between instructions or between cogs and none in an instruction: a reset with a byte on its way, a trap's second push after its first had failed, an interrupt let in by the one before it, and what `Run` answers when its last instruction is a WAIT. Each has its test now. That is where to look next: combinations of events, not more instructions.

Another, of 2026-09-30, found five more of the kind, none of them in what an instruction does by itself: a volume whose tables are no mirrors of each other, whose table that does not count could have had a file written over another; a page that goes past the end of the bus; RESET with the unit on; the console of a machine of 64K words or more; and a read into one address that failed after its first block. Each has its test now, which failed before the fault was mended; the fourth's runs under the twin only.

## What it costs, measured

P2-EC, `mac/bench.mac`: 303,004 instructions, of which a third each are `ADD R2,(R1)+`, `INC R3` and `SOB`.

| Build | Instructions a second | With memory management on |
| --- | --- | --- |
| checked, 160 MHz | 104,556 | 89,778 |
| `--unchecked`, 160 MHz | 118,685 | 103,379 |
| `--unchecked --clock 200MHz` | 148,385 | 129,212 |

That is with `ogo` v0.44.0 on 2026-09-29, the console, the clock and the disk on the bus, the machine counting how far it has come, and its memory management, with the pages where their addresses say when it is on. The day before, without the unit, the three ran 114,904, 131,113 and 163,874, which is what the unit costs with the unit off: a tenth, of which the paragraph on memory above says what is what. With the compilers of the same day before it, the three ran 120,287, 134,369 and 167,962 with the console alone, 119,811, 133,071 and 166,302 with the console and the clock, 116,629, 133,364 and 166,760 with the disk as well, and 116,540, 131,455 and 164,318 with the count. A device more to ask every `pollEvery` instructions costs about 1%, and so does where the build has put things: with the disk in the program and not on the bus the first two ran 117,762 and 131,912.

With `ogo` v0.46.0, of the same day, which inlines a small function where it is called, the three ran 104,484, 117,900 and 147,375 with the unit off, and 104,376, 117,762 and 147,232 with `--no-inline`. What it inlines, `stackCheck`, the register pairs of the EIS, the disk's `Request` and `finish`, the clock's `update`, and helpers of `sd` and `fat`, is called seldom or never while the benchmark runs, and the binary is 371,924 bytes with it and 365,320 without. The two unchecked builds are 0.7% below v0.44.0's and the checked one 0.1%. The column with the unit on was not measured again.

Sixty interrupts of the clock take 985 to 999 ms from when the program enables them, the first cycle being under way by then.

The talk with RT-11, from the loader's first byte to the last prompt, of which six seconds are the loader, the benchmark and the clock's second: 36 s checked, 32 s `--unchecked`, and 26 s `--unchecked --clock 200MHz`, before the memory management; with it and the binary of 365 KB, 45, 39 and 32 s. The talk with Unix V6, checked, 94 to 96 s, with v0.44.0 as with v0.46.0, of which the compiler is the larger part.

A pack onto the card with `scripts/card.py`: 4872 blocks in 113 s, which is the rate of the line at 230400 baud with a block's header and its escaped bytes, and 15 s more for the build, the load and the reading back. To sum the pack on the card against a file takes 15 s in all.

A block of the card, with its command and its checksum:

| Build | Microseconds to read a block |
| --- | --- |
| checked, 160 MHz | 1610 |
| `--unchecked`, 160 MHz | 1239 |
| `--unchecked --clock 200MHz` | 1050 |

To write one takes 2.5 to 5 ms, most of which is the card's. All of `TEST.DSK` is read and compared in 9.6 s by the tests, which are built checked. With `settle` at 0, 1 or 2 the first thing of any length the card sends fails its checksum, at 160 MHz and at 200 MHz alike, and with 3 to 6 all of 500 blocks are read; it is 8. The checked build's block was measured again with v0.44.0 on 2026-09-28, 1605 µs, and with v0.46.0 on 2026-09-29, 1624 to 1640 µs, `TEST.DSK` being read in 9553 to 9605 ms; the other two were measured with `ogo` 3875205f89d4, of the day before v0.44.0, as was the talk with RT-11: the card was not there when v0.44.0 was.

In clocks at 160 MHz, `--unchecked`: a call and its return 75 to 115; a field of the machine read and tested, 30; a `switch`, about 5 for every case it passes. A function with a branch in it is never inlined. The measurements and their programs are in `OCTOGO.md`. Measure again after an `ogo` upgrade before relying on any of it: the compiler of 2026-09-28 made the emulator 6 to 8% faster by making a named constant its value, where the three before it had agreed to within 2%.

Memory is a slice the program gives the machine with `Memory`, and the program's is a 248 KB array at package scope, which is part of the binary image: 372 KB to load, 365 KB with `--no-inline`. It was an array in the `Machine` of 56 KB, which made a word access one `rdword`; a `Machine` of 248 KB does not fit beside the vectors in a test binary, and the tests want machines of their own size. With the slice an access reads its pointer and its length, and the enable bit of the memory management before them, and every instruction writes SR2: measured one by one on 2026-09-29, `--unchecked`, SR2's write is 2.4% of the speed, the enable bit 2.1%, the length 1.3% and the slice the rest of the tenth.

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
| kernel and user mode with a stack pointer each, MFPI and MTPI | done |
| the status word at 177776, the switch register at 177570 | done |
| DL11 console | done |
| KW11-L line clock | done |
| the SD card, and a file's place on its FAT32 volume | done |
| RK11 disk controller, with files on the card for packs | done |
| RT-11 V4, single job | begins, and does in a talk of nine commands what it does in SimH |
| Unix V6 | begins, logs in, compiles a C program and runs it, and does in a talk of fourteen lines what it does in SimH |
| KT11-D memory management, 248 KB | done, 2026-09-29 |
| FIS, the floating point processor | not planned: their instructions trap as on a machine without them |

What the 11/40 does in its own way, all of it in the vectors: a register source is read after the destination is decoded, so `MOV R0,(R0)+` stores the stepped value; `JMP` and `JSR` to a register trap through 4, not 10; a program cannot write the trace bit at 177776; `HALT` in user mode traps through 10; the stack limit is fixed and only ever a trap after the instruction. Its memory management has an access control field of two bits, no SR1 and no trap that lets an access through, and aborts a read that will be written back before the read; SR2 is loaded at every fetch, the unit on or off, and held with SR0's page and mode while an error bit is set.

Reference facts. Addresses are 16-bit and octal; both `0o177560` and `0177560` compile.

| Device | Registers | Vector | Priority |
| --- | --- | --- | --- |
| DL11 console | RCSR 177560, RBUF 177562, XCSR 177564, XBUF 177566 | 060 in, 064 out | 4 |
| KW11-L clock | LKS 177546 | 100 | 6 |
| RK11 disk | RKDS 177400, RKER 177402, RKCS 177404, RKWC 177406, RKBA 177410, RKDA 177412, RKDB 177416 | 220 | 5 |
| KT11-D memory management | SR0 177572, SR2 177576; kernel PDR 172300 to 172316 and PAR 172340 to 172356; user PDR 177600 to 177616 and PAR 177640 to 177656 | 250, an abort | |

The I/O page is the top 8 KB of the address space, 160000 to 177777. Without memory management that leaves 56 KB of RAM; with the 18-bit KT11-D, 248 KB. An RK05 pack is 203 cylinders of 2 surfaces of 12 sectors of 256 words: 4872 blocks, 2,494,464 bytes. The PDP-11 and the P2 are both little-endian.

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
- The repository is public since the evening of 2026-09-28, at https://gitlab.com/cznic/p2-11, without announcement. It was made so when all of these held: LICENSE, AUTHORS and a README stating the status exist; the history holds no guest software and no personal data; the project builds with a tagged `ogo` release; and a stranger with a board can clone, `ogo run`, and watch a recognisable PDP-11 program at the terminal. The history has the review of 2026-09-27 with the paths of the machine it was written on, which the user knows of and keeps. Whatever is pushed is seen at once. Since 2026-09-30 GitLab mirrors it to https://github.com/modernc-org/p2-11, beside ogo's mirror there, with a push mirror whose token is a classic one of `public_repo` only: what is pushed to GitLab is on GitHub a moment later, and nothing is pushed to GitHub itself, which the next mirroring would overwrite.
- A commit is made when the user asks for one, and so is a push. The work is committed on a branch, in commits of one thing each, every one of which builds and passes the tests under the twin; `master` is fast-forwarded to the branch and pushed, and the branch deleted. Before anything is added, what would be added is looked at for guest software, for personal data and for the paths of this machine.

## License

BSD-3-Clause: the text of `../ogo/LICENSE` under "The p2-11 Authors", who are listed in AUTHORS. Every source file, script and Makefile begins with the header OctoGo's own sources carry, in the file's comment syntax:

```
// Copyright 2026 The p2-11 Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.
```

Code taken from elsewhere keeps its own notice, and is recorded before it is committed. The preference is to write from the DEC handbooks and to use other emulators as a reference for behaviour only.

The logo, `logo.svg`, is the project's own drawing, which `scripts/logo.py` makes of strokes: no typeface is in it, and nothing of DEC's or Parallax's marks, so that there is nothing in it to be too like what is someone's. The user said on 2026-09-28 that a logo matters little, and that being safe so is all that matters about one.

## Open decisions

- Whether the program is built `--unchecked` by those who run it. It is 13% faster.
- A lock shared with `../ogo` around board access, offered and not yet answered.
