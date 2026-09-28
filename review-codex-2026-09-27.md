p2-11 code review — 2026-09-27

Reviewed commit: `856cca45e2c47e3bd17b233c8f182d77e648f219`.

The project is a well-structured early emulator with unusually useful differential testing and clear documentation of its hardware and compiler constraints. The existing tests pass on both the host and the Propeller 2. I found four correctness issues outside that coverage: three medium-priority defects and one low-priority API defect. Five focused regression cases reproduce them on both platforms. No implementation changes were made during this review.

The review covered the processor, bus, traps, console, board integration, MACRO-11 programs, test harness, generation scripts, and project documentation. The missing clock, disk controller, and MMU are explicitly documented project scope, not review defects.

**Findings, in recommended repair order**

1. **[P2 / medium] Reset can leave the transmitter advertising ready while old work remains pending.** Locations: [Line.Reset](/home/jnml/src/modernc.org/p2-11/dl11/dl11.ogo:102), [Line.Next and Sent](/home/jnml/src/modernc.org/p2-11/dl11/dl11.ogo:89), and [transmitter-buffer writes](/home/jnml/src/modernc.org/p2-11/dl11/dl11.ogo:178).

   `Reset` sets the transmitter's DONE bit but leaves `written`, `sent`, and `out` unchanged. A byte waiting for the transmitting cog therefore survives reset, while the guest is told it can submit another. Each write increments a count, but only one byte of payload is retained. Outstanding counts can consequently outnumber distinct stored bytes.

   A deterministic reproduction on a fresh `Line` is:

   ```go
   l.Reset()
   l.Write(0o177566, 'A', 0xffff)
   l.Reset()
   // l.Pending() is true, but l.Read(0o177564) is 0o200 (DONE).
   l.Write(0o177566, 'B', 0xffff)
   first := l.Next()
   l.Sent()
   second := l.Next()
   l.Sent()
   // first == 'B', second == 'B'
   ```

   This does not require a guest to ignore readiness: reset itself asserts DONE. On the board, the focused test printed `one post-reset write transmits B then B`. Two writes before the first `Next`, without a reset, expose the same count-versus-storage mismatch and also produce `B, B`.

   A guest RESET or host `Machine.Reset` during output can therefore retain stale work and duplicate subsequent output. Define how reset cancels queued work and how an already-started physical transmission completes. Implement that handoff while preserving field ownership; simply assigning both counters from the machine cog would introduce a second writer and a race with `Sent`. Also define busy-write behavior so the pending count cannot promise payload that was never retained. SimH's console reset cancels its pending transmit event and clears its buffer; its write path schedules a single transmitter service. [Reference implementation](https://raw.githubusercontent.com/open-simh/simh/master/PDP11/pdp11_stddev.c).

2. **[P2 / medium] Trap entry performs a second stack write after the first has already aborted.** Location: [Machine.enter](/home/jnml/src/modernc.org/p2-11/pdp11/trap.ogo:88).

   The old PSW and PC are written consecutively, and `aborts` is checked only after both writes. Because `write` records an error and returns, the second bus transaction still occurs when the first failed. This contradicts the emulator's otherwise careful handling of partial instruction effects.

   Reproduction: reset a machine, put `EMT` (`0o104000`) at `0o1000`, set vector `0o30` to PC `0o2000` / PSW `0o340`, put sentinel `0o123456` at `0o157776`, and set SP=`0o160002`, PC=`0o1000`. Execute two steps. The first trap push targets unimplemented address `0o160000` and times out. Nevertheless, the second push overwrites valid RAM at `0o157776` with `0o001002`. The machine then returns `Faulted`, leaving that extra corruption behind.

   The sentinel should survive the failed first push. SimH's abort handling exits the access sequence at the failure; its trap pushes are sequential accesses, not a pair completed before checking errors. [Reference implementation](https://raw.githubusercontent.com/open-simh/simh/master/PDP11/pdp11_cpu.c).

   Check for an abort after each fallible access before issuing another one. Apply the same audit to the paired vector reads here and the paired stack reads in RTI/RTT, particularly where a subsequent read could acknowledge an I/O device. Add a regression that verifies memory effects as well as the final `Faulted` state; the existing `TestFault` checks only the state.

3. **[P2 / medium] Interrupt entry does not reconsider other eligible requests before fetching an instruction.** Locations: [Machine.due](/home/jnml/src/modernc.org/p2-11/pdp11/trap.ogo:55) and [Machine.interrupt](/home/jnml/src/modernc.org/p2-11/pdp11/trap.ogo:125).

   `due` calls `interrupt` once. `interrupt` takes the first eligible request and stops, even if the vector installs a PSW whose priority permits another pending request. `due` then clears attention and allows instruction execution. The second request can wait through a normal polling block or an instruction that halts the machine.

   Reproduction using the existing test bells: assert the priority-6 and priority-4 requests together. Set the priority-6 vector's PSW to zero and place HALT at its handler address `0o3000`. Leave the priority-4 vector at PSW `0o340` and put NOP at `0o2000`. One `Step` returns `Halted`, PC=`0o003002`, with grant counts high=1 and low=0. Reconsidering the pending interrupt after installing IPL 0 would instead grant the lower request and execute its NOP, yielding PC=`0o002002` with both grants recorded.

   This differs from SimH's dispatch loop, which recalculates interrupt eligibility after entry and returns to dispatch before fetching an instruction. [Reference implementation](https://raw.githubusercontent.com/open-simh/simh/master/PDP11/pdp11_cpu.c). The trigger is a vector whose installed priority is below another outstanding request; ordinary handlers that mask those requests do not encounter it.

   Reconsider pending traps and interrupts after each entry until no currently eligible event remains. Preserve the periodic poll for newly arriving asynchronous requests, but do not defer requests already pending across a priority change caused by entry. Add this case beside the existing tests whose vectors use priorities that mask competing requests.

4. **[P3 / low] `Run` reports `Running` when WAIT consumes the last instruction in its budget.** Location: [Machine.Run](/home/jnml/src/modernc.org/p2-11/pdp11/exec.ogo:27).

   Waiting is detected only at the start of the outer loop. If WAIT decrements `n` to zero, the loop exits with the default result `Running`, even though `m.waiting` is already true. This makes the returned state depend on the caller's instruction budget.

   Reproduction: reset a machine, deposit `0o000001` at `0o1000`, set PC=`0o1000`, and call `Step`. Both host and board return `Running` (0), rather than `Waiting` (1). PC is correctly `0o1002` and Count is 1. Calling `Run(2)` on the same initial program reports `Waiting`.

   Return the waiting state when the budget ends on WAIT, consistently with `Run`'s documented promise to report what the machine is doing. Add tests for `Step`, a budget ending exactly on WAIT, and a larger budget. The current main loop polls again, so this is primarily an API and debugger/event-loop correctness issue.

**Validation and limits**

| Check | Result |
| --- | --- |
| Existing host suite, `scripts/twin.sh`, including `GOARCH=386 go vet` | Passed: all 13 tests, including 2,380 vectors and the demo integration test |
| Existing board suite, `ogo test -p /dev/ttyUSB0 ./...` | Passed: all 13 tests, including the same vectors and demo; root and `mac` also reported success |
| Focused host regression cases | All five reproduced the reported defects |
| Focused board regression cases, `-run TestReview` | All five reproduced the same defects |
| Bash syntax for both shell scripts; Python AST parsing for both Python scripts | Passed |

The board runs used installed OctoGo `v0.43.1-0.20260926212526-43262bc1be0e`, built with Go 1.27.0, at the default 160 MHz. Host tests used Go 1.27.0 with 32-bit integers through `GOARCH=386`. The initial older installed compiler could not parse the project; after the user's compiler update, the full hardware suite succeeded. Host execution needed access outside the sandbox because the sandbox rejected 32-bit test binaries. The board port was checked for use before the test invocations.

Focused tests were kept outside the repository in `/tmp/p2-11-review-2026-09-27-twin` and `/tmp/p2-11-review-2026-09-27-board`. Their failures are expected assertions demonstrating defects, distinct from the passing existing suite. The five test names are `TestReviewResetPendingTransmit`, `TestReviewWritesWhileBusy`, `TestReviewFailedFirstTrapPush`, `TestReviewReconsiderInterruptsBeforeFetch`, and `TestReviewWaitAtBudgetBoundary`.

No new SimH sweep was run, and no assembled tables were regenerated: the reference tools were not installed in this checkout. The reported 15,876-case historical sweep and performance figures were not independently reproduced. Behavioral comparisons above use the linked upstream SimH source; they are not claims of a new differential execution against the exact commit that generated the checked-in vectors. Board tests exercise the relevant interleavings sequentially; they do not constitute a sustained concurrent serial stress test.

**Project evaluation and follow-up recommendations**

The package boundaries are appropriate: only the root imports `p2`, the CPU reaches peripherals through a narrow interface, and the Go twin exercises the same implementation. Static allocation and explicit ownership fit the target. The code explains instruction side effects, operand ordering, and trap precedence where they matter. The performance-driven grouping of instruction code is justified by measurements in `OCTOGO.md`; splitting it into many small helpers would need fresh target measurements.

The reference vectors, hand-written device tests, and complete demo together provide a strong foundation. The most valuable next tests are combinations of events, not simply more random opcodes: reset during transmission, successive pending interrupts, aborts partway through bus sequences, and instruction-budget boundaries.

Several nonblocking improvements would make future changes easier to trust:

- **Strengthen the vector oracle.** [runCase](/home/jnml/src/modernc.org/p2-11/pdp11/vector_test.ogo:119) compares registers and memory, but does not assert the final execution state or instruction count. Beyond the first `0o4000` bytes it checks and clears only addresses named by a vector. An erroneous write to another RAM address could escape detection and survive into a later case. A host-only full-RAM comparison/clear would close that gap without spending board resources. Include state/count expectations where the reference permits them, and add comparisons between batched `Run` and repeated `Step`.
- **Test actual cog interaction.** The DL11 tests explicitly simulate the three cogs in turn. Add a target stress test for sustained receive/transmit traffic, ring-counter wraparound, and reset while transmission is pending or in flight. Single-writer ownership is a useful invariant, but alone does not establish compiler visibility or publication ordering. Keep the shared-memory assumptions documented and verify the polling code after compiler changes; the sibling compiler documentation already notes this dependency.
- **Make tool versions reproducible.** [tools.sh](/home/jnml/src/modernc.org/p2-11/scripts/tools.sh:25) fetches moving repository heads. The vector header records its SimH commit, but the bootstrap script cannot recreate that version directly. Pin or accept explicit revisions for both external tools, record assembler provenance, and put an exact known-working OctoGo version and installation command in the README. “Late September 2026” is insufficient when nearby compiler versions differ in syntax and test-runner capacity.
- **Make generators fail explicitly on tool errors.** [mac.py](/home/jnml/src/modernc.org/p2-11/scripts/mac.py:46) and [vectors.py](/home/jnml/src/modernc.org/p2-11/scripts/vectors.py:455) consume subprocess stdout without checking those subprocess exit statuses. Check failures and report stderr before parsing or replacing output; use a temporary output file and replace the destination after successful generation and formatting. A timeout for reference execution would also bound cases that unexpectedly wait or loop.

Fix the transmitter reset and partial-abort behavior first, then interrupt redispatch and the WAIT return value. Preserve the existing target-specific optimizations and add the focused cases to the ordinary test suite as each defect is repaired.
