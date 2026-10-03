# What this project found out about OctoGo

p2-11 is the first program of any size written in OctoGo, and finding what the
language and its compiler lack is one of the things it is for. This file is
where that is written down: what was met, the smallest program that shows it,
what was measured, and what the emulator does about it meanwhile.

Everything here was measured on a P2-EC at 160 MHz. The clocks are those of the
`ogo` of 2026-09-28, `v0.43.1-0.20260928095216-ed3022eabb19`, and what the
emulator runs at is that of `v0.44.0`. A number of clocks is good to within
sixteen: what an access to hub RAM takes depends on where in memory the build
has put things.

An entry is removed when `ogo` no longer shows it and the emulator no longer
works around it. What was found and is closed is at the end, by name.

Of the three that are open, all are one: what the backend makes of the C it is
given. A call is dear, and what is not inlined is called. `ogo` v0.46.0, of
2026-09-29, changed both: it inlines a function of six statements at most
itself, a branch or a check in it or not. The tables of 1 and 2 are of the
compilers before it, as said above; what v0.46.0 makes of the same helpers is
under each, as `../ogo`'s CHANGELOG measured it on a P2-EDGE at 160 MHz. The
two stay open because the emulator is still written for what a call costs:
with v0.46.0 it runs 0.1% faster than with `--no-inline`, in all three builds,
its hot path having no small function left to inline. 3 is what a profile of
the emulator found on 2026-10-02, with `ogo`
v0.47.2-0.20261002103426-b80a9c3f7bab+dirty, of where the clocks go in code
that runs from hub memory, as the emulator's does: into the saving of a
function's registers at every call, and into jumps. 4 is what the emulator
does about all three since 2026-10-03: its hot loop is PASM, which OctoGo
carries as a Spin2 object.

## 1. A call is dear, and a function with a branch in it was called

| The helper, called in a loop | Clocks a call, `--unchecked` |
| --- | --- |
| two tests and three returns | 83 |
| two tests and one return | 76 |
| one expression, no test | 14, inlined |
| a field of the receiver tested against a constant | 28, inlined |
| a method reading a word of an array after one test | 113 |

```go
// Called.
func nz(v, sign uint16) uint16 {
	if v == 0 {
		return 4
	}
	if v&sign != 0 {
		return 8
	}
	return 0
}

// Inlined.
func (m *machine) aborted() bool {
	return m.traps&aborts != 0
}
```

A call and its return cost what forty or fifty instructions do, an
instruction being two clocks.

With v0.46.0, `nz`, two tests and three returns, is inlined and takes 29
clocks a call.

A `switch` is a chain of comparisons in the order of its cases. One of sixteen
cases, in a method called in a loop, costs 149 clocks on average and 179 for
its fifteenth.

This is what decided how the emulator is written. Its first version was small
methods, as the same program would be in Go: an instruction went through
`Step`, `execute`, a function for its group, one for the instruction, and from
there to `operand`, `load`, `readWord`, `aborted`, `nz` and `store`. It ran
21,059 instructions a second. With one call to an instruction where that can
be had, an operand in a register dealt with where it is met, and no helper on
the way that only tests something, it ran 111,316 with the same compiler: 5.3
times as many, from the same instructions in the same order.

**Meanwhile:** the emulator is written for what a call costs, and says so where
it matters, at the head of `pdp11/exec.ogo` and of `pdp11/bus.ogo`.

## 2. A runtime check was a call

| In a loop | Clocks, checked | Clocks, `--unchecked` |
| --- | --- | --- |
| a method that tests a field of its receiver | 211 | 28 |
| a method that writes a register, `m.r[r] = v` | 215 | 21 |
| `m.r[i&7] += uint16(i)`, where it stands | 70 | 36 |
| two accessors of one array element each | 411 | 56 |

```go
var ram [126976]uint16

func readWord(a uint32) uint16 {
	return ram[a>>1]
}

func writeWord(a uint32, v uint16) {
	ram[a>>1] = v
}
```

The check of the receiver for nil and the check of an index each call a helper
that has a branch in it, which by 1 is not inlined; and a function that calls
one is in turn too large to be inlined itself.

With v0.46.0, checked, a method testing a field of its receiver takes 51 clocks
a call where it took 211, a setter of an array's element 67 where 229, and two
accessors of a word 102 where 395: the call was most of what a check cost.

The emulator as it is now loses less to them, its checks being few a call:
114,904 instructions a second checked and 131,113 unchecked.

## 3. A function that calls another saves its registers, and a jump from hub memory costs 19

The emulator was profiled on 2026-10-02: `prof/` in the repository runs each
shape of instruction in a loop and says what one costs, and a program of loops,
below, what the backend's own conventions cost. Everything here is
`--unchecked` at 160 MHz unless said otherwise, and the code runs from hub
memory, which a loop with a call in it does: FCACHE copies into cog memory only
a loop that calls nothing. The tables of 1 and 2 were measured in loops it had
copied, which is why their numbers are smaller than these.

| In a loop of 100,000, an iteration that | Clocks from hub memory | From cog memory |
| --- | --- | --- |
| adds to a word of the hub | 56 | 40 |
| reads a word of the hub as well | 93 | 65 |
| writes a word of the hub, and nothing else | 45 | 33 |
| takes one of two branches, alternately | 76 | 44 |
| goes through a `switch` of eight, every case in turn | 141 | 75 |
| calls a leaf of two hub reads and a branch | 201 | 201 |
| calls a function that calls that leaf, saving 4 registers | 369 | 370 |

```go
// leaf calls nothing, and is too long to be inlined.
func leaf(s []uint32, a uint32) uint32 {
	v := s[a&63]
	if v > a {
		v -= a
	} else {
		v += a
	}
	v ^= a << 3
	v += s[v&63]
	if v&1 != 0 {
		v = v*3 + 1
	}
	return v + a
}

// guard has a guard clause that is never taken, and then calls a leaf.
func guard(s []uint32, a uint32) uint32 {
	if a == 0xffffffff {
		return 0
	}
	return leaf(s, a)
}
```

The column from cog memory is the same program built as `ogo` builds it; the
one from hub memory is built with `--fcache=0` given to the backend, which
`ogo` does not do, so that the loops run where the emulator's code runs. The
loops with a call in them are not copied either way.

So: a taken jump costs 19 clocks from hub memory and 4 from cog or LUT memory,
and a `switch` is a chain of them, 19 for every case it passes; a hub read
costs 25 to 37 and a write about 10; a leaf costs its call and return, about
40, and its body; and a function that calls another costs 150 to 160 clocks a
call besides. That is the backend's convention: a function that is not a leaf
has its locals in a pool of registers every such function shares, `local01` on,
and saves all of them to the hub stack on the way in and restores them on the
way out, `pushregs_` and `popregs_` in the assembly, each a routine in cog
memory that returns to hub memory, which costs a reload of the instruction
FIFO, three a call. A leaf has registers of its own, `_var01` on, and saves
nothing. spin2cpp's `NeedToSaveLocals` in `backends/asm/outasm.c` answers true
for every function that is not a leaf, with a FIXME above it about saving only
what is used before the first call.

What that does to the emulator, in clocks an instruction before and after the
dispatch moved from `execute`, a function of its own, into `Run`:

| Instruction | Before | After |
| --- | --- | --- |
| `SOB`, taken | 747 | 481 |
| `BR` | 763 | 545 |
| `MOV R1,R2` | 1043 | 865 |
| `MOV (R1)+,R2` | 1735 | 1543 |
| `ADD R2,(R1)+` | 2872 | 2663 |

`execute` was called for every instruction, 155 clocks, and found SOB, a tenth
of what Unix V6 executes, after fifteen comparisons, each a taken jump. The
benchmark went from 104,089 to 120,526 instructions a second checked, and from
118,360 to 137,292 unchecked, and the talk with Unix V6 from 95 s to 88.

An immediate operand, `#n`, is a third of what V6 and RT-11 read. Found in
`double` where it stands, without the call of `address`, `MOV #1,R2` costs
1271 clocks where it cost 1529. Written first as a case of a `switch` before
`s >= 8`, it put 24 clocks on every other two-operand instruction, the test of
the mode being a taken jump for what fails it; nested inside `if s >= 8`, 6 on
one with a source in a register and 22 to 30 on one with a source in memory.
A test added to a path is a taken jump for everything that fails it, and the
backend predicates only a short body. An instruction now costs `Run`'s loop, about 350
clocks, a call of its function, 155 for `double` and `single` and 40 for the
leaf `branch`, and its body; an operand in memory costs the calls of `address`
and `read`, 680 in all, and one written back `write` as well, 1800 for
`ADD R2,(R1)+`.

What else was tried, with the C the compiler emits kept and given back to it:

- `-O2` to the backend, which adds common subexpressions, loop strength
  reduction, aggressive memory and cold code: 103,414 against 103,661 checked
  and 116,495 against 117,946 unchecked. Nothing.
- `read` placed in LUT memory with `__attribute__((lut))`, which flexspin's C
  has and OctoGo does not: `MOV (R1)+,R2` 1322 where 1536, `MOV 2(R1),R2` 1633
  where 2075, and the benchmark 148,240 a second where 138,611, 7% from one
  function of 151 longs. `address` there instead, 168 longs: 146,449. The
  branches in LUT memory cost 4, and the FIFO is not reloaded on the way in.
  The LUT holds 240 longs of code as the backend lays it out, from 528 to 768,
  the top 256 longs being kept for FCACHE whether `--fcache=0` is given or not;
  `double` and `read` together, 457 longs, would not fit, and the hot path,
  `Run`, `double`, `single`, `address`, `read`, `write` and `branch`, is 1,460.
  A pragma that places a function, and a way to spend the LUT, are what OctoGo
  would need.
- `read`, `address` and `write` marked with the attribute `ogo` marks a small
  function with, `__attribute__((inline))`: the backend left them as they were.

Checked, the emulator was 14% slower than unchecked, 120,526 against 137,292:
the receiver `m` was tested for nil at every access to a field of it, four
instructions a time and twelve of them on `Run`'s path to an instruction, and
`m.R[ir>>6&7]` was bounds-checked though the index is three bits. And every
operation on a `uint16` was followed by a `getword` that keeps it one, 94 of
them in `double`, two clocks each. The compiler of that evening,
v0.47.2-0.20261002211137-ad6edefafc2b, writes narrow unsigned arithmetic with
fewer conversions, 79 `getword` in `double`, and leaves out of a checked build
the checks the program proves, ten tests of `m` on `Run`'s path: the same code
runs 128,883 a second checked and 143,399 unchecked with it, 7% and 4% more,
and the two are 11% apart.

**Meanwhile:** the dispatch is in `Run`, what comes most often first, an
immediate operand is found where it stands, and the rest stays as it is: what
is left to gain is in the backend's hands, a call that saves less, a jump that
costs less, and the LUT. Since 2026-10-03 the instructions a program mostly
executes are the core's, in PASM, which 4 tells of, and these costs are what
the machine's own code pays for the rest.

## 4. The hot loop is PASM, which OctoGo carries as a Spin2 object

What 3 measured is what C becomes on this backend, and no rewriting of the
emulator in OctoGo gets near an 11/40's speed from there. So since 2026-10-03
the instructions a program mostly executes are executed by a core in PASM,
`core/core.spin2`, on a cog of its own, which the package `core` carries as
`vga` carries its driver: functions without bodies, `start`, `execute`, `bind`
and `stop`, bind the object's PUB methods, and the program hands the object
the addresses it works on. Nothing new was needed of OctoGo for it.

It makes the machine five times as fast: `mac/bench.mac` runs 761,316
instructions a second where the machine alone runs 137,979, `MOV R1,R2` costs
167 clocks where it cost 880, `ADD R2,(R1)+` 389 where 2684, a taken `SOB` 115
where 496. What the core leaves to the machine, the I/O page, traps and the
rarer instructions, costs what it did and 710 clocks more for the hand-back.

What it took, besides the PASM:

- The machine's state is the core's where the machine keeps it, so nothing is
  copied: `pdp11.Machine.Places` makes numbers of the addresses of its fields
  with `unsafe.Pointer`, and of the layout of a page, which is the backend's
  to choose; `core.Attach` refuses a layout the core is not written for.
- The handshake is PASM too, in the object's PUB methods: the program writes a
  command into a long and waits for the core to clear it, in a loop of the
  method's inline assembly, so that no OctoGo loop polls a word another cog
  writes. OctoGo's rule for that, which ogo c789abd wrote down on the same
  day, is among what is closed below.
- A cog holds 496 longs and its LUT 512, and the core is about 930: its
  registers, tables and most of its code in the cog, the rest of its code and
  the pages of the memory management in the LUT, which the core loads itself
  from where `coginit` started it, PTRB, as Eric Smith's driver loads its own.
  A label past cog address $1FF is no register, which the compiler says where
  the label is used, as "does not appear to be a register".
- A Spin2 object's CON names, method names and DAT labels share one
  namespace, without regard to case, and Spin2's keywords are in it: `bind` as
  a label and a method, `BIND` as a constant beside the method, `place` as a
  label beside a constant `PLACE`, `reg` and `next` as labels, each failed.
  ogo 8f5eb43 writes that down in "Functions implemented in Spin2".
- When the cog and the LUT were full, what is rare went to hub RAM: an
  `orgh` section of the object's DAT, which a cog executes from hub, slower.
  Its entries are reached through registers the core sets from PTRB at its
  start, `@label - @entry` being where in the image a label is, so that where
  the backend puts the image matters not, and within it every jump is
  relative. Nothing of OctoGo's was needed for that either. The status word
  and the page registers run there, and the core binding itself to a machine.
- The host cannot build a package with a Spin2 object, so the twin leaves it
  out, and the core is tested on the board only: against the machine's own
  code on random instructions and random programs, and on pdp11's 2902
  vectors of SimH's.

## Found here and closed

| What | Closed by |
| --- | --- |
| Whether a cog that spins on a variable another cog writes sees the write was nowhere said, though the console's ring and the tests between cogs relied on it, and Go leaves a compiler free to keep the variable in a register. OctoGo's specs.go says it since, "Memory shared between cogs": a loop reads Hub RAM on every pass, a cog's writes reach it in program order, and a value of 32 bits or fewer is read and written whole; a test holds the backend's listing to it. | c789abd |
| Assigning a call's several results to fields, `l.rx, l.request = control(l.rx, v, l.request)`, took the compiler 23 s in a program of twelve lines, and all the memory there was in a larger one. It had come in between 086cf7f and 43262bc. | ce72a9e |
| An array literal was one line of C, and a table of 8000 numbers more than the backend's preprocessor takes in a line. | bad9e5a |
| `ogo fmt` and gofmt disagreed about the names of a constant block of which only the first has a value, about `for i := 0; ; i++`, and about the second line of a call's arguments. | 35dda36 |
| An unsigned number of 32 bits ordered against a constant with a name and no type was compared as though it had a sign: for `a, b uint32 = 12000, 5000` and `const patience = 10000`, `b-a < patience` was true on the board. The backend warned, and built. | c8fd036 |
| A named constant was an object of the C, read from hub RAM at every use, 10 clocks each, and a helper that named one was too large to be inlined, 112 clocks a call where the same helper with a literal took 40. The emulator gained 6% checked and 8% unchecked by it. | c8fd036 |
| `ogo fmt` took the indentation from what continues a line: in `return a < b &&` with `b < c` on the next line, `b < c` came back under the `return`, and so an operand on a line of its own and the second line of a condition. | bfde4df |
| A program could not ask how fast its clock is, which is chosen where it is built, with `--clock`. `p2.ClockFreq()` says: 160000000 on the board as built, and 200000000 built with `--clock 200MHz`. The emulator counts the cycles of its line clock in microseconds as before, which is good to one and forgives a cycle that is late. | d5af0c8 |
| An error could not be returned that came of a call given a local buffer, `if err := fill(buf[:]); err != nil { return 0, err }`: "cannot return local err, which holds a pointer into local buf", of a `fill` that returns the address of a variable of the package or nothing. | c888892 |
| An `if` that began with a call, `if two(); ok {`, was refused with "expected [AssignOp '{' '=' ...]", where Go takes any simple statement before the condition. The test that met it named the call's results instead, which is Go as well and stays. | e76f833, in v0.45.0 |
| A control character written as an octal escape and followed by a digit from 0 to 7 was another character on the board: `"\0337"`, ESC and 7, was 0337 and a NUL, and `"\0010"` was 010 and a NUL, with nothing to warn. `ogo` wrote `\033` as C has it, and the backend's lexer reads octal digits for as long as they come, which is flexprop#115. The tests of `vt100` found it, whose DECSC is ESC 7: the twin saved the cursor where the board put a character. | 01dda6d, in v0.47.0 |
| A name a package had for a function or a constant of its own was looked up among the variables of `main`, which are named in C by their names in the source. With `func seven` and `const n = 4` in a package, and `var seven = nine` and `var n [16]uint32` in `main`, the package's `seven()` was 9 on the board and `for i := range n` summed to 120, with nothing to warn; with `i < n` against the array the build stopped in the compiler, "emit: cannot compare [16]uint32 with a value of another type". A constant used in an expression was right, being made a number first. `vga` found it, whose block of parameters was `var params [16]uint32` beside `vt100`'s `const params = 16`; a program that went through all of p2-11 found four names more, all used so that they were right. | 9b236f5, in v0.47.1 |
