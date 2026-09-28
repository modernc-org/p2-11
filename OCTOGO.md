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

Of the five that are open, the first two are one: what the backend makes of the
C it is given. A call is dear, and what is not inlined is called. The others
are small, and none was measured on a board, there being nothing to measure.

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
119,811 instructions a second checked and 133,071 unchecked.

## 3. `ogo fmt` takes the indentation from the second line of an expression

```go
func f(a, b, c int) bool {
	return a < b &&
		b < c
}
```

gofmt leaves that as it is. `ogo fmt` puts `b < c` under `return`, and does
the same to an operand of `+` on a line of its own and to the second line of
an `if`'s condition. What is built is the same; what is read is not.

**Meanwhile:** the emulator has no expression of more than a line. The one it
would have had, in `attach` of `main.ogo`, is an `if` and a `return`.

## 4. A program cannot ask how fast its clock is

The frequency is chosen where the program is built, with `--clock`, and `p2`
has no name for it. What `p2` counts in clocks is of use to a program that
knows how many of them a second has: `p2.GetCt`, `p2.WaitUntil` and
`p2.WaitCycles`, and the periods a smart pin is given with `p2.WritePinX`, a
bit of a serial line among them.

```go
import "p2"

func main() {
	next := p2.GetCt()
	for {
		next += 160000000 / 60 // at 160 MHz, and at no other frequency
		p2.WaitUntil(next)
		p2.PinToggle(56)
	}
}
```

**Meanwhile:** the cog that counts the cycles of the line clock times them in
microseconds, with `p2.GetUs` and `p2.WaitUs`, which the backend's library
makes of the frequency. That is good to a microsecond where the frequency is
a whole number of MHz, and a cycle of a sixtieth of a second wants no better.
`sd` waits a number of clocks for the card's bit, and the number is the one
for the fastest clock there is.

## 5. An error cannot be returned that comes of a call given a local buffer

```go
type failure struct {
	what string
}

func (f *failure) Error() string {
	return f.what
}

var errEmpty = failure{"nothing to fill"}

func fill(p []byte) error {
	if len(p) == 0 {
		return &errEmpty
	}
	p[0] = 1
	return nil
}

func first() (byte, error) {
	var buf [16]byte
	if err := fill(buf[:]); err != nil {
		return 0, err
	}
	return buf[0], nil
}
```

```
main.ogo:22:13: cannot return local err, which holds a pointer into local buf: its storage does not outlive the function; declare buf at package scope
```

What `fill` returns is the address of a variable of the package or nothing,
and never anything of `p`. It is the way a Go program reads into a buffer of
its own and passes on what went wrong.

**Meanwhile:** the sixteen bytes `sd` reads a card's size from are a field of
the `Card`, not a local of the method that reads them.

## Found here and closed

| What | Closed by |
| --- | --- |
| Assigning a call's several results to fields, `l.rx, l.request = control(l.rx, v, l.request)`, took the compiler 23 s in a program of twelve lines, and all the memory there was in a larger one. It had come in between 086cf7f and 43262bc. | ce72a9e |
| An array literal was one line of C, and a table of 8000 numbers more than the backend's preprocessor takes in a line. | bad9e5a |
| `ogo fmt` and gofmt disagreed about the names of a constant block of which only the first has a value, about `for i := 0; ; i++`, and about the second line of a call's arguments. | 35dda36 |
| An unsigned number of 32 bits ordered against a constant with a name and no type was compared as though it had a sign: for `a, b uint32 = 12000, 5000` and `const patience = 10000`, `b-a < patience` was true on the board. The backend warned, and built. | c8fd036 |
| A named constant was an object of the C, read from hub RAM at every use, 10 clocks each, and a helper that named one was too large to be inlined, 112 clocks a call where the same helper with a literal took 40. The emulator gained 6% checked and 8% unchecked by it. | c8fd036 |
