# p2-11

A PDP-11/40 on a [Parallax Propeller 2](https://www.parallax.com/propeller-2/),
written in [OctoGo](https://pkg.go.dev/modernc.org/ogo).

OctoGo is a Go-like language for the Propeller 2 in which a goroutine is one of
the chip's eight cores. This is the first program of any size written in it,
and it is here as much to show what such a program looks like as to run a
PDP-11.

## Status

The processor, the console, the line clock and the disk are there, and RT-11
V4 runs: it begins from a pack on the SD card and does what it does in SimH.
There is no memory management yet, which Unix wants.

```
$ ogo run
303004 instructions in 2637 ms, 114904 a second
60 cycles of the line clock in 988 ms

PDP-11/40 on a Propeller 2, in OctoGo
28K words of memory
Type; control-D halts.
```

The first line is the emulator timing itself on a loop, and the second how long
a PDP-11 program, [mac/ticks.mac](mac/ticks.mac), waited for sixty interrupts
of the clock, the first of which was on its way when it began. The rest is
[mac/demo.mac](mac/demo.mac): it finds out how much memory there is by
reading upwards until the bus times out and the processor traps, prints that in
decimal with the extended instruction set's DIV, and then waits, the console's
receiver interrupting for every key.

That is what the machine does with no disk. With an SD card in the slot that
has a file `RK0.DSK`, it begins with what is on that pack:

```
RK0.DSK is the pack in drive 0
...
RT-11SJ  V04.00C

.
```

| | |
| --- | --- |
| KD11-A processor with the KE11-E extended instruction set | there |
| traps, interrupts, the trace bit, the stack limit | there |
| DL11 console, on the serial line the program is loaded through | there |
| KW11-L line clock | there |
| the SD card's blocks, and where a file of its FAT32 volume is | there |
| RK11 disk with RK05 drives, a file on the SD card for a pack | there |
| RT-11 V4, the single job monitor | runs |
| KT11-D memory management | not yet |

The processor is tested against the PDP-11/40 of
[SimH](https://opensimh.org): 2380 cases of a machine before an instruction and
after it, on the board and on the machine the program is written on. A sweep of
15,685 more agrees as well. The disk is tested against SimH's too, with a
program of 35 steps, [mac/disk.mac](mac/disk.mac). And so is all of it: a talk
with RT-11 in which a file is copied, compared and deleted says on the board
what it says in SimH, and leaves on the card what SimH leaves in its file.

## Running it

It needs a Propeller 2 board and OctoGo. It was written with a P2 Edge module,
P2-EC, and needs `ogo` v0.44.0 or a later one:

```sh
go install modernc.org/ogo@v0.44.0
```

```sh
ogo run                                  # build, load, and open a terminal
ogo build --unchecked --clock 200MHz     # as fast as it goes: 163,874 a second
ogo test ./...                           # the tests, on the board
scripts/twin.sh                          # the packages' tests under Go, no board needed
scripts/talk.py                          # a talk with what is on the pack, on the board and in SimH
```

## How it is put together

| | |
| --- | --- |
| [main.ogo](main.ogo), [disk.ogo](disk.ogo) | the program: five cogs, one stepping the machine, one reading the serial line, one writing it, one counting the cycles of the line clock, one moving blocks between the card and memory |
| [pdp11](pdp11) | the machine: processor, memory, bus, traps and interrupts |
| [dl11](dl11) | the console |
| [kw11](kw11) | the line clock |
| [rk11](rk11) | the disk controller and its drives |
| [sd](sd) | an SD card's blocks, read and written over SPI |
| [fat](fat) | where on a disk a file of its FAT32 volume is |
| [mac](mac) | the PDP-11 programs it carries, in MACRO-11 and assembled |
| [scripts](scripts) | what makes the test vectors, assembles the programs, and runs the tests under Go |

The cogs share memory and no lock: every variable two of them share is
written by one of them only.

Only the program at the root and `sd` know about the Propeller 2. The other
packages are Go once they are given a package clause, which is how their tests
also run where there is no board. `sd` and `fat` know nothing about the PDP-11.

What writing it found out about OctoGo is in [OCTOGO.md](OCTOGO.md).

## A disk

A pack is a file on the card: `RK0.DSK` for drive 0, and so on to `RK7.DSK`.
The card is an SD card of any size with a FAT32 volume, and the file is an
image of an RK05 pack, 2,494,464 bytes, copied to a card that has not had a
file deleted, so that it is in one piece.

```sh
truncate -s 2494464 RK0.DSK              # an image that is shorter is made a whole pack
cp RK0.DSK /media/card/ && sync
```

## Software for it

None is in this repository and none will be. What runs on a PDP-11 is, for the
most part, not free to pass on; what is, the early Unix versions among it, will
be fetched from where it is kept.

## License

BSD-3-Clause, see [LICENSE](LICENSE).

SimH was the reference for what a PDP-11/40 does, and the programs in `mac/` are
assembled with Richard Krehbiel's macro11. Neither is part of this repository;
`scripts/tools.sh` fetches both, at the revisions that were used.
