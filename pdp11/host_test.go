// Copyright 2026 The p2-11 Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package pdp11

// What only the machine the emulator is written on has the time for.
//
// This file is Go and no OctoGo. scripts/twin.sh puts it beside the twin of
// the package, and the board never sees it.

func init() {
	thorough = true
}
