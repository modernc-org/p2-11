# The mixed model: a PASM core for the PDP-11, its rare work in OctoGo

A handoff from the ogo session of 2026-10-03, written at the user's request, for
the p2-11 session to read before deciding anything. It records an idea discussed
with the user, the facts behind it, and a plan to test it in steps that each end
in a measurement. Nothing here has been built. A number marked **measured** was
measured on a P2 board; one marked **estimate** is arithmetic from measured
instruction timings and has not been measured.

## 0. In short

Today an instruction costs `Run`'s loop (about 350 clocks), a call of its function
(about 155) and its body, all in hub execution, where a taken jump costs 19 clocks
and a call that saves registers 150 to 160. The semantic work of `MOV R1,R2` is a
handful of clocks; the 832 it costs is almost all the cost of running C from hub
memory.

In the mixed model, a cog of its own runs a hand-written PASM **core** from cog and
LUT memory. The core fetches, decodes and executes the common instructions with the
PDP-11 registers in cog registers. Whatever it does not do, it hands back to the
existing OctoGo `pdp11.Machine`, unexecuted: the I/O page, traps and interrupts,
WAIT/HALT/RESET, and any corner it would rather not get exactly right. The 11/40
itself split its work the same way between fast hardware paths and microcode.

The estimate is 5 to 15 times today's speed for what the core does, less whatever
the hand-backs cost. That cost is the first thing to measure (section 8, stage 1).
The OctoGo emulator stays the reference, and stays everything that runs under the
twin.

Using the core changes the project's story: the CPU's hot loop would no longer be
OctoGo. Whether that is wanted is the user's call (section 9).

## 1. Where the time goes today (measured, from this repository's own notes)

From CLAUDE.md, "What it costs, measured", 2026-10-02, with `ogo` at ad6edef, at
160 MHz:

- **`mac/bench.mac`:** 129,766 instructions a second checked, 144,701
  `--unchecked`, and 181,005 `--unchecked --clock 200MHz`.
- **Per shape, unchecked, in clocks:**

  | Shape | Clocks |
  | --- | --- |
  | `NOP` | 696 |
  | `SOB` taken | 448 |
  | `BR` | 512 |
  | `MOV R1,R2` | 832 |
  | `INC R3` | 936 |
  | `MOV #1,R2` | 1271 |
  | `MOV (R1)+,R2` | 1552 |
  | `MOV 2(R1),R2` | 2066 |
  | `ADD R2,(R1)+` | 2647 |
  | `JSR PC,@#sub` | 1470 |

- **What the time is:** `Run`'s loop is about 350 clocks: five hub accesses, some
  sixty instructions and four taken jumps. A call of `double` or `single` is about
  155. An operand in memory costs about 700 more, through `address` and `read`, and
  one written back about 1800.
- **What the talks execute:**
  - **Unix V6:** 5.59 million instructions, 96% of them with the memory management
    on. `MOV` is 28%, the branches 15.5%, `SOB` 9.2%, `CMP` 8.7%, `MTPI` 6.2%,
    `JSR` 4.4%, `ADD` 4.4%, `CLR` 4.3%, `TST` 2.4%, `RTS` 2.3% and `MFPI` 2.2%.
  - **RT-11:** 5.74 million instructions, with the unit off. The branches are 35%,
    `MOV` 13.5%, `TSTB` 12.7%, `CMP` 5% and `CMPB` 4.5%.

Measured by the ogo session on a P2-EDGE at 160 MHz, from hub execution, as the
emulator runs:

| Access | Clocks |
| --- | --- |
| `rdlut` | 3 |
| `wrlut` | 2 |
| `rdlong` | about 15 (eight in a row) |
| `wrlong` | 8 in a row, 15 alone |
| `add` on a cog register | 2 |
| read-modify-write of a hub long | about 27 |

## 2. Why PASM, and why on its own cog

- **The cost is the place, not the work.** In cog execution an instruction takes 2
  clocks and a taken jump 4, against 19 from hub. A register is a cog register.
  There are no calls, so nothing saves registers through the hub stack.
- **The core fits.** A cog executes at full speed from its 496 general registers
  (`$000`-`$1EF`) and from its 512 longs of LUT. The base instruction set's decode,
  eight addressing modes and condition codes plausibly need a few hundred
  instructions. The registers, the PSW, both modes' page tables (2 x 8 pages x 4
  longs) and the decode tables fit beside them.
- **The ISA suits it.** PDP-11 instructions are regular: eight registers and eight
  addressing modes, applied the same way everywhere. `ALTS`/`ALTD` index the
  register file in one instruction. `SKIPF`/`EXECF`, which the Spin2 interpreter is
  built on, share code paths between addressing modes at no cost for the skipped
  instructions in cog execution.
- **What stays expensive is the emulated memory.** It stays in hub RAM, roughly 9
  to 16 clocks a read in cog execution, and that is now the dominant cost of an
  instruction.

**A cog of its own** (architecture A) is the recommended form. The core's cog runs
no C, so all of its cog RAM and LUT are the core's. Nothing it does can disturb the
backend's registers, its FCACHE or its locals. The price is one cog and a
cross-cog hand-back (section 4.4). Section 5 has the in-cog alternative and why it
comes second.

## 3. What OctoGo offers for it today (nothing new needed)

- **A package may carry `.spin2` files** (ogo v0.47.0, which `vga` already uses).
  - A function declared without a body binds to the PUB method of its name.
  - What crosses: an integer of 32 bits or fewer, a bool, a pointer.
  - A pointer handed to a Spin2 method is taken to be kept for ever, so only
    package storage may be passed, as `vga`'s `params` is.
  - The PASM goes in the `.spin2` file's DAT section. A PUB `start(block)` does
    `coginit(16, @entry, block)` (16 is COGEXEC_NEW) and answers the cog, as
    `vga_tile_driver.spin2` does. The core then finds the block in PTRA.
- **flexcc cannot link a separate `.pasm2`** with C (tested 2026-10-02). The DAT
  section of a `.spin2` file is the way in.
- **Addresses** cross as numbers through `unsafe.Pointer`:
  `uint32(uintptr(unsafe.Pointer(&memory[0])))`, as `vga` hands its driver the
  cells.
- **`p2.ReadLUT` / `p2.WriteLUT`** (ogo, 2026-10-03; see section 6). They are not
  needed for architecture A.
- **The host cannot build a program that calls a Spin2 object.** The twin never
  sees the core: the core package is P2-only, as `vga` is.

## 4. Architecture A

### 4.1 Who does what

The core does what is most of every talk, by the counts in section 1:

- **Double-operand:** `MOV(B)`, `CMP(B)`, `BIT(B)`, `BIC(B)`, `BIS(B)`, `ADD`, `SUB`.
- **Single-operand:** `CLR(B)`, `COM(B)`, `INC(B)`, `DEC(B)`, `NEG(B)`, `ADC(B)`,
  `SBC(B)`, `TST(B)`, `ROR(B)`, `ROL(B)`, `ASR(B)`, `ASL(B)`.
- **Control:** the branches, `SOB`, `JMP`, `JSR`, `RTS`.
- **The rest:** `SWAB`, `SXT`, `XOR`, and the condition-code operations.
- **Operands:** all eight addressing modes on memory below the I/O page.
- **In stage 4:** the memory management's translation, and `MTPI`/`MFPI`, which are
  8.4% of V6.

The core hands back, unexecuted:

- every access to the I/O page;
- `EMT`, `TRAP`, `BPT`, `IOT`, `RTI`, `RTT`, `WAIT`, `HALT`, `RESET`, `MARK`;
- the EIS `MUL`/`DIV`/`ASH`/`ASHC` (all four can move into the core later);
- the floating-point and reserved instructions;
- an odd address, a non-existent address, and an access the pages do not admit;
- everything while the T bit is set.

The core may also hand back any instruction it would rather not get exactly right,
such as one naming the same register with side effects in both operands.

The OctoGo `Machine` executes every handed-back instruction with the code it has
today, so the 11/40's semantics in the rare cases stay where they are tested
against SimH.

### 4.2 The one rule: complete, or leave no trace

Each instruction the core starts ends one of two ways:

- **Completed** with every side effect, exactly as `Machine` would leave it.
- **Handed back** with nothing changed: registers, PSW and memory as they were
  before its fetch.

This rule removes most of the difficulty:

- The core never has to reproduce what an aborted instruction leaves behind on an
  11/40. It hands back the instruction, and `Machine` takes the abort with the
  existing code.
- The order the core computes things in is free, as long as it validates
  everything before it commits anything.

In practice the core works in two phases:

1. **Compute and validate.** Work out every effective address and every new
   register value into temporaries, translating and checking each access: page,
   length, permission, odd address, end of memory.
2. **Commit.** Write registers, memory and flags.

A memory write is always the last thing an instruction does, so nothing written to
memory ever has to be undone. `JSR` pushes and then sets the PC, so both of its
addresses are validated before either write. The 11/40's stack limit is handled by
the same rule: a kernel push below 0o400 is handed back, and `Machine` requests the
trap.

### 4.3 State, and where it lives

While the core runs, it owns the CPU state in its registers: R0-R7, the PSW, the
two stack pointers (kernel and user; the 11/40 has no supervisor mode) and its copy
of the page tables. The `Machine` fields are stale until the next synchronisation.

The two sides share one **block of longs** in hub RAM, a package array passed to
`start` as `vga` passes `params`. It holds:

- the registers, the PSW and the other mode's SP;
- a command word, written by OctoGo, and a reason word, written by the core;
- the handed-back instruction's PC;
- a count of completed instructions;
- the hub address of `memory[0]` and its length in words;
- the enable bit, and both modes' page tables in the core's form.

A page-table entry is the `page` of `mmu.go` (`base`, `low`, `high`, `may`).

`SETQ` with `RDLONG`/`WRLONG` moves the whole block at about a long a clock once the
hub slot comes up. The core's side of a synchronisation is therefore tens of
clocks; the OctoGo side, field by field, is the dearer one.

`pdp11` stays Go for the twin. Suggested shape, for the p2-11 session to judge:

- **Two Go-pure methods on `Machine`** copy the CPU state to and from such a block.
- **One hook in `Run`** replaces its inner loop: "execute up to `left` instructions
  and report how many completed and why you stopped". Its type is an interface in
  `pdp11` that the twin never implements.
- **A P2-only package**, say `core`, implements the hook with the `.spin2` file.

A Go model of the core's split, an implementation of the same hook that executes
the fast-path subset and hands back the rest, would let the twin test the hand-back
logic. It is optional.

### 4.4 Batches, interrupts, and what a hand-back costs

`Run` asks the devices every `pollEvery` (32) instructions and after anything that
sets `attention`. Everything that sets `attention` is an I/O page access or a trap,
which the core hands back anyway. So the core can replace exactly `Run`'s inner
loop:

- OctoGo says "up to `left`".
- The core runs that many, or fewer if it hands one back.
- `Run` goes on as it does today: it executes the handed-back instruction, takes
  traps, and asks the devices.

Everything is the same as now except where the instructions run. Interrupt timing
in instructions, `Now()`, `Count` and SR2 keep their present semantics.

There are two kinds of exit:

- **A batch ending.** The PSW's priority and mode cannot change inside the core:
  that takes a PSW write, a trap or an RTI, all handed back. So OctoGo can ask the
  devices with the priority it already knows, and needs only the count from the
  core. When nothing is due, the reply is "go on" and no state is copied. When an
  interrupt is due, the state is synchronised and `Machine` takes the interrupt.
- **A hand-back.** A full synchronisation each way, plus `Machine` executing the
  instruction at today's cost.

Signalling costs (estimates):

- **Core side:** a hub long and a poll loop, a few tens of clocks.
- **OctoGo side:** a `for` loop around a hub read in hub execution, about 50 clocks
  an iteration. The backend has `_cogatn`, `_pollatn` and `_waitatn`. The `p2`
  package does not expose them yet, and the ogo session can add `p2.CogAtn` and
  friends on request.

The cost to watch is a batch end. If asking three devices through an interface
costs 1000 to 1500 clocks, that is 30 to 50 clocks an instruction at 32 a batch,
which is half the core's own cost. Two remedies, in order of preference:

1. **A larger `pollEvery` with the core.** 32 was right when an instruction took
   7 µs. At about 1 µs, 128 or 256 instructions is the same latency in time, and
   the console's pace is counted in instructions anyway.
2. **Asking the devices on the OctoGo cog while the core runs the next batch.**
   This gives up the instruction-exact timing of interrupts, so it is not the first
   choice.

Stage 1 measures this before anything else is built on it.

### 4.5 Memory, bytes and the memory management

- **Byte order.** `memory` is a `[]uint16` in hub RAM, little-endian, as the
  PDP-11 is. So the byte at physical address `pa` is `rdbyte` at `memory base + pa`,
  and the word at an even `pa` is `rdword` there.
- **Other cogs.** The disk's cog keeps using `Fetch`/`Store` while the core runs,
  as it does while `Run` runs. Memory is the bus, and the core caches none of it,
  instructions included, so self-modifying code is no concern.
- **With the unit off,** an address at or above 0o160000 is handed back. Below it,
  the address is checked against the length of memory.
- **With the unit on,** translation follows `read`/`write`:
  - Page `a>>13`; offset `d = a & 0o17777`.
  - Check `low <= d <= high` and the cycle against `may`; then `pa = base + d`.
  - A `pa` in the I/O page, or any failed check, is handed back.
  - Both modes' tables live in the core, so `MTPI`/`MFPI` and a trap's switch of
    space need nothing new.
  - Anything that changes the tables (a PAR/PDR/SR0 write, a change of mode) is a
    hand-back, after which OctoGo sends the tables again.
- **The PDR's written bit.** The simplest exact handling is to hand back the first
  write to a page not yet marked written. That happens once per page until the
  program clears the bit, and `write` then sets it as it does today.
- **SR2** is the PC of the last instruction fetched. On a synchronisation, OctoGo
  sets it from the block, unless SR0's error bits hold it.

### 4.6 Inside the core (a sketch, not a design)

- **Registers.**
  - **R0-R7:** eight consecutive cog registers, read with `ALTS` and written with
    `ALTD` by register number.
  - **The PSW:** one register, with C and Z mirrored into the P2's flags where that
    saves instructions.
  - **Arithmetic:** in 32 bits. A carry out of 16 bits is bit 16 (`TESTB`), a sign
    is bit 15 or bit 7, and a byte is sign-extended with `SIGNX`.
- **Fetch.** Translate the PC (with the unit on, the code page can be cached as
  `Run` caches it), `rdword`, then add 2 to the PC.
- **Decode.** A table in LUT indexed by the top bits of the instruction, then
  `JMP`. A second level for the `00xxxx` and `10xxxx` groups, as `Run`'s switch has.
- **Operands.** One routine per operand position and mode. `SKIPF` patterns can
  share most of it.
- **The loop.** Count, `DJNZ` on the batch, fetch again.

Room: about 1000 longs of cog RAM and LUT together. The hot path should fit in cog
RAM, where a taken jump costs the same as in LUT.

### 4.7 What it might cost (estimates)

In cog execution, at 2 clocks an instruction, 4 a taken jump and 9 to 16 a hub
access:

| Shape | Core (estimate) | Today, unchecked (measured) |
| --- | --- | --- |
| fetch and decode | about 35 | about 350 |
| `MOV R1,R2` | about 65 | 832 |
| `BR` / `SOB` | about 60 | 512 / 448 |
| `ADD R2,(R1)+` | about 125 | 2647 |

The benchmark's mix would then cost about 85 clocks an instruction plus a batch end
amortised (unknown: 5 to 50 clocks, depending on 4.4). That is about 1.2 to 1.9
million instructions a second at 160 MHz, 8 to 13 times today's 144,701.

The talks pay for their hand-backs. Each costs a synchronisation and today's
`Machine` cost, so hand-backs that are 1% of instructions at about 3000 clocks each
add about 30 clocks an instruction. With the memory management on, every memory
access adds a translation, about 10 instructions.

**Stage 0 below turns these into a projection from the talks' real instruction
mix, before any PASM is written.**

## 5. Architecture B: the core on the machine's own cog (untested)

The core could instead be loaded into the LUT of the cog that runs `Machine` and
entered and left like a call: a Spin2 method copies it into LUT with `SETQ2` and a
burst `RDLONG` and jumps to it.

What it would save:

- the cog;
- the cross-cog signalling. A hand-back becomes a return.

`p2.ReadLUT` would let the OctoGo side read the core's state where the core keeps
it.

What stands against it:

- **Room.** Only `$200`-`$2FF` of the LUT is free beside the backend: 256 longs
  for code and data together. Above it is the backend's FCACHE (OCTOGO.md, 3). The
  cog registers are the backend's. 256 longs is tight for the core described above.
- **Unknowns.** Whether the backend's FCACHE survives being overwritten while the
  core runs, and how a Spin2 method can jump into LUT and come back, are untested.

Keep B in mind if the cog budget (section 9) makes A impossible.

## 6. A smaller step that needs no PASM: the register file in LUT

The ogo session added `p2.ReadLUT(addr uint32) uint32` and
`p2.WriteLUT(addr, v uint32)` on 2026-10-03, at the user's request, as generally
useful, in ogo 669910a. As of this writing that commit is local to the ogo
session's tree and not yet pushed, so pull before relying on them.

- **What they do.** Each is the one instruction, RDLUT or WRLUT, inlined where it
  is called (no call in the listing). Addresses are 0 to 255 (LUT `$200`-`$2FF`),
  range-checked in a checked build. On the host, a LUT is an array per thread.
- **Measured on a P2-EDGE:** a read costs 3 clocks and a write 2, from hub
  execution. A hub read costs about 15 and a write 8 to 15.

The register file and the PSW in LUT would save roughly 10 to 25 clocks per access,
several accesses an instruction. **Estimate:** 5 to 15% on the benchmark.

What it costs the code:

- **The twin has no `p2`.** `pdp11` would need a Go stub package `p2` for the twin
  (the two functions over an array), or an indirection that costs a call.
- **A LUT is the cog's, not the `Machine`'s.** Two machines stepped on one cog
  (tests do this) share it, so `Run` would load the LUT on entry and store it on
  exit, keeping `R` and `psw` the truth outside `Run`. Everything `Run` reaches
  (`double`, `single`, `due`, `enter`, `setPSW`) would then use the LUT.

The core in section 4 makes this step redundant, since its registers are cog
registers. It is worth doing only as a stopgap, or if the core is not pursued.

## 7. How to know the core is right

The core can always hand back, so a fault in it is a completed instruction that
`Machine` would have completed differently. Four nets:

1. **The vectors.** Run the 2902 cases (522 of the memory management) on the board
   with the core attached, with the same expected results. The table is a test
   file of `pdp11`, which a `core` test cannot import, so it needs exporting or a
   hook. The p2-11 session's call.
2. **Lockstep on real workloads.**
   - Batch size 1. The core logs its memory write in the block, as address, old
     and new. No fast-path instruction writes more than one word; trap entry,
     which pushes two, is handed back.
   - OctoGo restores the old words and the pre-instruction state, executes the
     instruction with `Machine`, and compares registers, PSW and the written words.
   - A write `Machine` makes elsewhere goes unseen unless `write` is given a
     logging hook for the test.
   - Slow, but it checks the RT-11 and V6 boots instruction by instruction.
3. **Fuzzing in lockstep.** Random instruction words over random registers and
   memory. Flags, bytes, the same register in both operands, the PC as an operand
   and odd addresses are where emulators are wrong.
4. **The talks with SimH,** `scripts/talk.py`, end to end, as today.

## 8. A plan in stages, each ending in a measurement

0. **Projection, no PASM.**
   - Under the twin, count in the RT-11 and V6 talks what the core would hand back
     for a given fast-path set, by reason, as the talks' mix was counted on
     2026-10-02.
   - Combine the counts with 4.7's estimates and stage 1's round trip into a
     projected speed per talk.
   - This decides the fast-path set, and whether `MTPI`/`MFPI`, the PSW and trap
     entry belong in the core, before anything is built.
1. **The protocol, with an empty core.**
   - The core hands back every instruction, the hook in `Run`, the block, start and
     stop.
   - Everything still passes, since `Machine` does all the work.
   - **Measure:** the cost of a hand-back and of a batch end, on the board. This is
     what 4.4's choices hang on.
2. **Fetch, decode, the register modes, the branches and `SOB`.** Lockstep, the
   vectors, `prof/`.
3. **Every fast-path instruction and mode, unit off.** The vectors, fuzzing, the
   RT-11 talk, the benchmark.
4. **The memory management in the core, then `MTPI`/`MFPI`.** The V6 talk.
5. **Tuning.**
   - `pollEvery` for the core.
   - Signalling by ATN.
   - `SKIPF`.
   - The EIS, trap entry and the PSW write, moved into the core where stage 0's
     counts say they pay.

## 9. Decisions for the user, before stage 1

- **The story.** p2-11's first purpose is to be an idiomatic OctoGo program. With
  the core, the CPU's hot loop is PASM: "a PDP-11 hosted by OctoGo, its fast path
  in PASM". OctoGo would remain the reference, the slow path, the devices and the
  system. It would also show OctoGo and PASM working together, which is a purpose
  of its own.
- **A cog.**
  - `main`, `receive`, `transmit`, `line` and `turn` are five cogs. `vga` makes six,
    and the core seven.
  - The VGA driver takes an eighth for a moment as it starts.
  - A keyboard driver of one cog (phase 2) would take that eighth for good. The VGA
    driver would then have to start before it, and nothing more would fit, unless
    two of the OctoGo cogs are merged or architecture B is used.
- **Determinism.** Keeping interrupts exact to the instruction (4.4) costs speed.
  Giving it up changes what the tests can compare.

## 10. Considered and not taken

- **`extern register` (COG RAM for a C global):** scalars only, so `R[r]` cannot be
  indexed. Each copy is per cog, and the space is shared with the backend's
  registers.
- **A `.pasm2` beside the C:** the backend cannot link one (tested).
- **The whole emulator in PASM:** it duplicates `pdp11`, loses the reference that
  makes the core testable, and gains little over the mixed model, where the rare
  paths are rare.
- **A function placed in LUT (`__attribute__((lut))`):** measured in OCTOGO.md, 3,
  at 7% for `read`. OctoGo has no way to ask for it, and the user declined one for
  now.

## 11. What the ogo session can add on request

- **`p2.CogAtn(mask)`, `p2.PollAtn() bool`, `p2.WaitAtn()`:** the backend has them
  as intrinsics; adding them is small.
- **`p2.CogId()`, `p2.CogStop(id)`:** likewise.
- **Anything the measurements of stages 0 and 1 show is missing.**

## Appendix: timings used

**Measured on a P2-EDGE at 160 MHz:**

- From hub execution: `rdlut` 3, `wrlut` 2, `rdlong` about 15 (eight in a row),
  `wrlong` 8 in a row and 15 alone, an `add` on a cog register 2.
- A taken jump: 19 from hub, 4 from cog or LUT (p2-11).
- A call that saves registers: 150 to 160 (p2-11).

**From the P2 documentation:**

- In cog or LUT execution, an instruction takes 2 clocks.
- `RDLONG`/`RDWORD`/`RDBYTE` take 9 to 16, and `WRLONG` 3 to 10.
- `SETQ` bursts move about a long a clock after the first.
- `ALTS`, `ALTD` and `TESTB` take 2.
- Instructions `SKIPF` skips cost nothing in cog execution.
