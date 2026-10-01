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

Of the two that are open, both are one: what the backend makes of the C it is
given. A call is dear, and what is not inlined is called. `ogo` v0.46.0, of
2026-09-29, changed both: it inlines a function of six statements at most
itself, a branch or a check in it or not. The tables are of the compilers
before it, as said above; what v0.46.0 makes of the same helpers is under each,
as `../ogo`'s CHANGELOG measured it on a P2-EDGE at 160 MHz. The two stay open
because the emulator is still written for what a call costs: with v0.46.0 it
runs 0.1% faster than with `--no-inline`, in all three builds, its hot path
having no small function left to inline.

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

## Found here and closed

| What | Closed by |
| --- | --- |
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
