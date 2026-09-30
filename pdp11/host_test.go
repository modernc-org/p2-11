// Copyright 2026 The p2-11 Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package pdp11

// What only the machine the emulator is written on has the time for.
//
// This file is Go and no OctoGo. scripts/twin.sh puts it beside the twin of
// the package, and the board never sees it.

import "testing"

func init() {
	thorough = true
}

// The console reaches memory below the I/O page whatever size the machine was
// given: 65,536 words and more is what a length narrowed to 16 bits loses,
// and what no test binary on the board has the room for beside the vectors.
func TestConsoleAnySize(t *testing.T) {
	for _, words := range []int{65535, 65536, 65537, 90000, MaxWords} {
		var m Machine
		mem := make([]uint16, words)
		m.Memory(mem)
		m.Reset()
		for _, a := range []uint16{0, 0o1000, IOPage - 2} {
			if !m.Deposit(a, a^0o52525) {
				t.Errorf("%d words: nothing deposited at %06o", words, a)
				continue
			}
			if v, ok := m.Examine(a); !ok || v != a^0o52525 || mem[a>>1] != a^0o52525 {
				t.Errorf("%d words: %06o examined at %06o, %v, and %06o in memory", words, v, a, ok, mem[a>>1])
			}
		}
		if !m.Load(0o1000, []uint16{1, 2, 3}) {
			t.Errorf("%d words: a program not loaded", words)
		}
	}
}
