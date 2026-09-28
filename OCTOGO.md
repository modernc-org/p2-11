# What this project found out about OctoGo

p2-11 is the first program of any size written in OctoGo, and finding what the
language and its compiler lack is one of the things it is for. This file is
where that is written down: what was met, the smallest program that shows it,
what was measured, and what the emulator does about it meanwhile.

Everything here was measured on a P2-EC at 160 MHz, with the `ogo` of
2026-09-27, `v0.43.1-0.20260927203343-458488c32397`. A number of clocks is
good to within sixteen: what an access to hub RAM takes depends on where in
memory the build has put things.

An entry is removed when `ogo` no longer shows it and the emulator no longer
works around it. What was found and is closed is at the end, by name.

## 1. An unsigned number and an untyped constant are compared as though signed

```go
const patience = 10000

var a, b uint32 = 12000, 5000

func main() {
	println(a-b < patience, b-a < patience)
}
```

Go says `true false`, `b-a` being 4294960296. The board says `true true`.

The constant is emitted as `static const int patience = 10000;`, the comparison
as `(b - a) < patience`, and the backend compares the two as signed numbers.
It says so while it builds, and builds:

```
warning: signed/unsigned comparison may not work properly
```

| `b-a < c`, with `c` | The board says |
| --- | --- |
| `const c = 10000` | true, which is wrong |
| `const c = 10000`, written `c > b-a` | true, which is wrong |
| `const c uint32 = 10000` | false |
| the literal `10000` | false |
| `const c = 10000`, and `a`, `b` of sixteen bits | false |

So it takes a number of 32 bits whose upper bit is set, an ordering, and a
constant that has a name and no type. Equality is not affected.

**Meanwhile:** the emulator has no such comparison. Its tests had one, a time
in milliseconds against how long to wait, and the constant has a type there
now: `cogs_test.ogo`. A build of this repository that warns has met it again.

## 2. A named constant is read from memory at every use

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
of comparing with an immediate. It is what 1 comes from as well.

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
| `return m.traps&3 != 0` | 40, inlined |
| `return m.traps&aborts != 0`, with `const aborts = 3` | 112, called |

**Meanwhile:** nothing. The emulator names its constants. Its first version,
with every one of them replaced by its value, ran 5% faster, which is not
worth what the program would read like.

## 3. A function with a branch in it is called, and a call is dear

The backend's doing rather than the emitter's.

| The helper, called in a loop | Clocks a call, `--unchecked` |
| --- | --- |
| two tests and three returns | 88 |
| two tests and one return | 88 |
| one expression, no test | 16, inlined |
| a method reading a word of an array after one test | 125 |

A call and its return cost about what fifty instructions do, an instruction
being two clocks.

A `switch` is a chain of comparisons in the order of its cases. One of sixteen
cases, in a method called in a loop, costs 153 clocks on average and 192 for
its fifteenth.

This is what decided how the emulator is written. Its first version was small
methods, as the same program would be in Go: an instruction went through
`Step`, `execute`, a function for its group, one for the instruction, and from
there to `operand`, `load`, `readWord`, `aborted`, `nz` and `store`. It ran
21,059 instructions a second. With one call to an instruction where that can
be had, an operand in a register dealt with where it is met, and no helper on
the way that only tests something, it runs 113,399: 5.4 times as many, from the
same instructions in the same order.

**Meanwhile:** the emulator is written for what a call costs, and says so where
it matters, at the head of `pdp11/exec.ogo` and of `pdp11/bus.ogo`.

## 4. A runtime check is a call

| In a loop | Clocks, checked | Clocks, `--unchecked` |
| --- | --- | --- |
| a method that tests a field of its receiver | 215 | 32 |
| `m.r[i&7] += uint16(i)` | 76 | 40 |
| two accessors of one array element each | 422 | 71 |

The check of the receiver for nil and the check of an index each call a helper
that has a branch in it, which by 3 is not inlined; and a function that calls
one is in turn too large to be inlined itself.

The emulator as it is now loses less to them, its checks being few a call:
113,399 instructions a second checked and 124,131 unchecked.

## Found here and closed

| What | Closed by |
| --- | --- |
| Assigning a call's several results to fields, `l.rx, l.request = control(l.rx, v, l.request)`, took the compiler 23 s in a program of twelve lines, and all the memory there was in a larger one. It had come in between 086cf7f and 43262bc. | ce72a9e |
| An array literal was one line of C, and a table of 8000 numbers more than the backend's preprocessor takes in a line. | bad9e5a |
| `ogo fmt` and gofmt disagreed about the names of a constant block of which only the first has a value, about `for i := 0; ; i++`, and about the second line of a call's arguments. | 35dda36 |
