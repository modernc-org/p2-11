# p2-11

A PDP-11/40 on a [Parallax Propeller 2](https://www.parallax.com/propeller-2/),
written in [OctoGo](https://pkg.go.dev/modernc.org/ogo).

OctoGo is a Go-like language for the Propeller 2 in which a goroutine is one of
the chip's eight cores. This is the first program of any size written in it,
and it is here as much to show what such a program looks like as to run a
PDP-11.

## Status

Early. The processor and the console are there, and nothing to boot an
operating system from yet.

```
$ ogo run
303004 instructions in 2672 ms, 113399 a second

PDP-11/40 on a Propeller 2, in OctoGo
28K words of memory
Type; control-D halts.
```

The first line is the emulator timing itself on a loop. The rest is a PDP-11
program, [mac/demo.mac](mac/demo.mac): it finds out how much memory there is by
reading upwards until the bus times out and the processor traps, prints that in
decimal with the extended instruction set's DIV, and then waits, the console's
receiver interrupting for every key.

| | |
| --- | --- |
| KD11-A processor with the KE11-E extended instruction set | there |
| traps, interrupts, the trace bit, the stack limit | there |
| DL11 console, on the serial line the program is loaded through | there |
| KW11-L line clock | not yet |
| RK11 disk, from an image on the SD card | not yet |
| KT11-D memory management | not yet |

The processor is tested against the PDP-11/40 of
[SimH](https://opensimh.org): 2380 cases of a machine before an instruction and
after it, on the board and on the machine the program is written on. A sweep of
15,685 more agrees as well.

## Running it

It needs a Propeller 2 board and OctoGo. It was written with a P2 Edge module,
P2-EC, and needs the `ogo` of 2026-09-27 or a later one:

```sh
go install modernc.org/ogo@458488c32397  # v0.43.1-0.20260927203343-458488c32397
```

```sh
ogo run                                  # build, load, and open a terminal
ogo build --unchecked --clock 200MHz     # as fast as it goes: 155,068 a second
ogo test ./...                           # the tests, on the board
scripts/twin.sh                          # the packages' tests under Go, no board needed
```

## How it is put together

| | |
| --- | --- |
| [main.ogo](main.ogo) | the program: three cogs, one stepping the machine, one reading the serial line, one writing it |
| [pdp11](pdp11) | the machine: processor, memory, bus, traps and interrupts |
| [dl11](dl11) | the console |
| [mac](mac) | the PDP-11 programs it carries, in MACRO-11 and assembled |
| [scripts](scripts) | what makes the test vectors, assembles the programs, and runs the tests under Go |

The three cogs share memory and no lock: every variable two of them share is
written by one of them only.

Only the program at the root knows about the Propeller 2. The packages are Go
once they are given a package clause, which is how their tests also run where
there is no board.

What writing it found out about OctoGo is in [OCTOGO.md](OCTOGO.md).

## Software for it

None is in this repository and none will be. What runs on a PDP-11 is, for the
most part, not free to pass on; what is, the early Unix versions among it, will
be fetched from where it is kept.

## License

BSD-3-Clause, see [LICENSE](LICENSE).

SimH was the reference for what a PDP-11/40 does, and the programs in `mac/` are
assembled with Richard Krehbiel's macro11. Neither is part of this repository;
`scripts/tools.sh` fetches both, at the revisions that were used.
