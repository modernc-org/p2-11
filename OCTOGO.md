# What this project found out about OctoGo

p2-11 is the first program of any size written in OctoGo, and finding what the
language and its compiler lack is one of the things it is for. This file is
where that is written down: what was met, the smallest program that shows it,
what was measured, and what the emulator does about it meanwhile.

Everything here was measured on a P2-EC at 160 MHz, with the `ogo` of
2026-09-28, `v0.43.1-0.20260928095216-ed3022eabb19`. A number of clocks is
good to within sixteen: what an access to hub RAM takes depends on where in
memory the build has put things.

An entry is removed when `ogo` no longer shows it and the emulator no longer
works around it. What was found and is closed is at the end, by name.

The two that are open are one: what the backend makes of the C it is given. A
call is dear, and what is not inlined is called.

## 1. A function with a branch in it is called, and a call is dear

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

## 2. A runtime check is a call

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

The emulator as it is now loses less to them, its checks being few a call:
120,287 instructions a second checked and 134,369 unchecked.

## Found here and closed

| What | Closed by |
| --- | --- |
| Assigning a call's several results to fields, `l.rx, l.request = control(l.rx, v, l.request)`, took the compiler 23 s in a program of twelve lines, and all the memory there was in a larger one. It had come in between 086cf7f and 43262bc. | ce72a9e |
| An array literal was one line of C, and a table of 8000 numbers more than the backend's preprocessor takes in a line. | bad9e5a |
| `ogo fmt` and gofmt disagreed about the names of a constant block of which only the first has a value, about `for i := 0; ; i++`, and about the second line of a call's arguments. | 35dda36 |
| An unsigned number of 32 bits ordered against a constant with a name and no type was compared as though it had a sign: for `a, b uint32 = 12000, 5000` and `const patience = 10000`, `b-a < patience` was true on the board. The backend warned, and built. | c8fd036 |
| A named constant was an object of the C, read from hub RAM at every use, 10 clocks each, and a helper that named one was too large to be inlined, 112 clocks a call where the same helper with a literal took 40. The emulator gained 6% checked and 8% unchecked by it. | c8fd036 |
