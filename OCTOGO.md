# What this project found out about OctoGo

p2-11 is the first program of any size written in OctoGo, and finding what the
language and its compiler lack is one of the things it is for. This file is
where that is written down: what was met, the smallest program that shows it,
what was measured, and what the emulator does about it meanwhile.

Everything here was measured on a P2-EC at 160 MHz unless it says otherwise.
Two compilers were used, and an entry says which it holds for:

| Called here | Version | What it is |
| --- | --- | --- |
| the compiler on PATH | `v0.42.1-0.20260923071228-086cf7f98feb` | what `ogo` was on 2026-09-27 |
| the tree's compiler | `v0.43.1-0.20260926212526-43262bc1be0e` | `../ogo` at its HEAD of 2026-09-26 |

An entry is removed when the compiler on PATH no longer shows it and the
emulator no longer works around it.

## 1. Assigning a call's several results to fields: the compiler runs away

**The tree's compiler only. The compiler on PATH is not affected, so this came
in between 086cf7f and 43262bc.**

```go
type line struct {
	rx      uint16
	request bool
}

func control(csr, v uint16, request bool) (uint16, bool) {
	return csr | v, request
}

var l line

func main() {
	l.rx, l.request = control(l.rx, 64, l.request)
	println(l.rx, l.request)
}
```

| Compiler | `ogo build` takes |
| --- | --- |
| on PATH | 0.6 s |
| the tree's | 22.8 s |

With package variables for targets in place of the fields it takes 0.5 s, and so
it does with one result in place of two. In a method, `l.rx, l.request =
control(l.rx, v, l.request)`, it takes 11.4 s.

Two such statements in a program with a few calls between `main` and them, and
the compiler does not finish: it allocates until it is stopped. Under `ulimit
-v 4000000` it ends after about 22 s in `fatal error: out of memory`, inside
`(*emitter).collectFuncCross`, which is on the stack eight deep with a slice
one longer at each level.

```go
type device interface {
	write(a, v, mask uint16)
}

type line struct {
	rx, tx               uint16
	rxRequest, txRequest bool
}

func control(csr, v uint16, request bool) (uint16, bool) {
	if v&64 == 0 {
		request = false
	}
	return csr&^64 | v&64, request
}

func (l *line) write(a, v, mask uint16) {
	switch a & 6 {
	case 0:
		if mask&64 != 0 {
			l.rx, l.rxRequest = control(l.rx, v, l.rxRequest)
		}
	case 4:
		if mask&64 != 0 {
			l.tx, l.txRequest = control(l.tx, v, l.txRequest)
		}
	}
}

type machine struct {
	dev device
	mem [16]uint16
}

func (m *machine) attach(d device) {
	m.dev = d
}

func (m *machine) writeIO(a, size, v uint16) {
	mask := uint16(0xffff)
	if size == 1 {
		mask = 0x00ff
	}
	m.dev.write(a&^1, v, mask)
}

func (m *machine) write(a, size, v uint16) {
	if a >= 32 {
		m.writeIO(a, size, v)
		return
	}
	m.mem[a>>1] = v
}

func (m *machine) address(spec uint16) uint16 {
	return m.mem[spec&7]
}

func (m *machine) double(ir uint16) {
	a := m.address(ir & 7)
	m.write(a, 2, m.mem[ir>>6&7])
}

func (m *machine) run(n int) {
	for i := 0; i < n; i++ {
		m.double(uint16(i))
	}
}

var (
	l line
	m machine
)

func main() {
	m.attach(&l)
	m.run(3)
	println(l.rx, l.rxRequest)
}
```

In the emulator itself a second shape did the same, which has not been made
smaller than the emulator: with the console's `Write` storing one result,
`l.rxRequest = requests(l.rx, v, l.rxRequest)`, where `requests` returns its
third parameter on one of its paths, the whole program did not build either.

**Meanwhile:** `dl11.Line.Write` does what the helper did where it stands, twice.

## 2. A named constant is read from memory at every use

Both compilers.

```go
import "p2"

const n = 1000000

var ram [126976]uint16

func main() {
	var a, sum uint32
	t := p2.GetCt()
	for i := 0; i < n; i++ {
		ram[a>>1] = uint16(i)
		sum += uint32(ram[a>>1])
		a = (a + 2) & 0x1fffe
	}
	println(sum, p2.GetCt()-t)
}
```

The constant is emitted as `static const int n = 1000000;`, and the backend
reads it from hub RAM where it is used, `rdlong result1, ptr__dat__`, in place
of comparing with an immediate.

| The loop's bound | Clocks per iteration, `--unchecked` |
| --- | --- |
| `n` | 71.0 |
| `1000000` | 60.5 |

An expression of constants is not folded either: `m.traps&(trapOdd|trapTimeout)
!= 0` reads both and ORs them where it runs.

What it costs beyond the read is that it decides what is inlined, since the
backend inlines by size:

| The body of a method called in a loop | Clocks a call |
| --- | --- |
| `return m.traps&3 != 0` | 24, inlined |
| `return m.traps&aborts != 0`, with `const aborts = 3` | 111, called |

**Meanwhile:** nothing. The emulator names its constants. Its first version,
with every one of them replaced by its value, ran 5% faster, which is not
worth what the program would read like.

## 3. A function with a branch in it is called, and a call is dear

Both compilers, and the backend's doing rather than the emitter's.

| The helper, called in a loop | Clocks a call, `--unchecked` |
| --- | --- |
| two tests and three returns | 87 |
| two tests and one return | 79 |
| one expression, no test | 16, inlined |
| a method reading a word of an array after one test | 116 |

A call and its return cost about what fifty instructions do, an instruction
being two clocks.

A `switch` is a chain of comparisons in the order of its cases. One of sixteen
cases, in a method called in a loop, costs 160 clocks on average and 199 for
its fifteenth.

This is what decided how the emulator is written. Its first version was small
methods, as the same program would be in Go: an instruction went through
`Step`, `execute`, a function for its group, one for the instruction, and from
there to `operand`, `load`, `readWord`, `aborted`, `nz` and `store`. It ran
21,059 instructions a second. With one call to an instruction where that can
be had, an operand in a register dealt with where it is met, and no helper on
the way that only tests something, it runs 111,316: 5.3 times as many, from the
same instructions in the same order.

**Meanwhile:** the emulator is written for what a call costs, and says so where
it matters, at the head of `pdp11/exec.ogo` and of `pdp11/bus.ogo`.

## 4. A runtime check is a call

Both compilers.

| In a loop | Clocks, checked | Clocks, `--unchecked` |
| --- | --- | --- |
| a method that tests a field of its receiver | 215 | 24 |
| `m.r[i&7] += uint16(i)` | 79 | 36 |
| two accessors of one array element each | 422 | 71 |

The check of the receiver for nil and the check of an index each call a helper
that has a branch in it, which by 3 is not inlined; and a function that calls
one is in turn too large to be inlined itself.

The emulator as it is now loses less to them, its checks being few a call:
111,316 instructions a second checked and 124,847 unchecked.

## 5. An array literal is one line of C, and 65,535 characters is all there may be

Both compilers.

```go
var table = [...]uint16{
	0o000000, 0o000001, 0o000002, // ... and so on, 8000 elements in all
}

func main() {
	println(len(table), table[7999])
}
```

The emitter writes the initializer on one line, about nine characters an
element. With 6000 elements the program builds. With 8000 the backend's
preprocessor gives up on the line, and what the user is told is

```
flexcc crashed: libc_musl.go:466:PopJumpBuffer
	TODO unsupported setjmp/longjmp usage
```

by the tree's compiler, and the same under a Go stack trace by the one on PATH.

**Meanwhile:** `scripts/vectors.py` writes the vectors as arrays of 4000 numbers
and a function that answers the ith of them.

## 6. `ogo fmt` and gofmt disagree in three places

Both compilers. The sources of the packages that do not import `p2` are Go once
they have a package clause, so the two formatters meet on the same text.

```go
const (
	trapOdd = 1 << iota // a word at an odd address
	trapTimeout // an address nothing answers at
	trapReserved // an instruction this processor does not have
)

func f(a, b, c int) int {
	for i := 0; ; i++ {
		if i > a {
			break
		}
	}
	return g("no vector or no stack for a trap",
		a, b, c)
}
```

| | gofmt | `ogo fmt` |
| --- | --- | --- |
| names of a constant block where only the first has a value | padded to the longest, the comments after | not padded, the comments after the first's value |
| a `for` clause with no condition | `for i := 0; ; i++` | `for i := 0;; i++` |
| the second line of a call's arguments | one tab deeper than the call | as deep as the call |

**Meanwhile:** the repository is what `ogo fmt` makes of it.

## Fixed in the tree, and still met with the compiler on PATH

These are no findings any more. They are here because the emulator's tests work
around the first until `ogo` on PATH is the tree's.

- **The address of an element where an interface is wanted.** `take(&bells[1])`
  reached the backend unconverted, "incompatible types in parameter passing:
  expected _struct__ringer but got pointer to _struct__bell", and `var r ringer =
  &bells[1]` was refused as "an interface holds a pointer: write the address of
  a variable, or &T{...}". Through a variable, `p := &bells[1]; take(p)`, it
  builds, which is what `TestAttach` does.
- **`if n, ok = f(); ok {`** was a syntax error, `"=": expected [',' ":="]`.
- **Nine tests in a package** did not build, `fit 480 failed: pc is 497`, where
  any eight of them did. With the compiler on PATH the tests of `pdp11` are run
  in two goes: `ogo test -run 'Test[ACDIWRF]' ./pdp11` and `ogo test -run
  TestVectors ./pdp11`.
