// Copyright 2026 The p2-11 Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package rk11

// What only the machine the emulator is written on can do: begin with a pack
// that is a file there, talk to what is on it, and have SimH do the same.
//
// This file is Go and no OctoGo. scripts/twin.sh puts it beside the twin of
// the package, and the board never sees it. Neither the pack nor SimH is
// part of the repository, and without them there is no test. P2_11_ROOT is
// where the repository is, which scripts/twin.sh says; the pack is
// guest/RK0.DSK there, and SimH tools/simh/BIN/pdp11.

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"testing"
	"time"

	"modernc.org/p2-11/dl11"
	"modernc.org/p2-11/kw11"
	"modernc.org/p2-11/mac"
	"modernc.org/p2-11/pdp11"
)

// A file is a pack that is a file of this machine, in memory.
type file struct {
	data []byte
}

func (f *file) Read(block uint32, p []byte) error {
	if block >= Blocks || int(block+1)*BlockSize > len(f.data) {
		return &errPack
	}
	copy(p, f.data[block*BlockSize:])
	return nil
}

func (f *file) Write(block uint32, p []byte) error {
	if block >= Blocks || int(block+1)*BlockSize > len(f.data) {
		return &errPack
	}
	copy(f.data[block*BlockSize:], p)
	return nil
}

// A line is what is waited for and what is typed when it has come. What is
// waited for ends with the prompt, so that nothing is typed into what the
// system is saying: it says what is typed when it is typed.
type line struct {
	cue, typed string
}

// rt11 is a talk with RT-11 V4, which begins by itself with a file of
// commands. A file is copied, compared with what it is a copy of, and
// deleted, and where it was is free again.
var rt11 = []line{
	{"D 56=0\r\n\r\n.", "DIR/BRIEF *.COM\r"},
	{"2820 Free blocks\r\n\r\n.", "SHOW CONFIGURATION\r"},
	{"No SYSGEN options enabled\r\n\r\n\r\n.", "COPY README.TXT X.TXT\r"},
	{"COPY README.TXT X.TXT\r\n\r\n.", "DIR X.TXT\r"},
	{"2784 Free blocks\r\n\r\n.", "DIFFERENCES README.TXT X.TXT\r"},
	{"differences found\r\n\r\n.", "DELETE/NOQUERY X.TXT\r"},
	{"DELETE/NOQUERY X.TXT\r\n\r\n.", "DIR/FULL X.TXT\r"},
	{"0 Files, 0 Blocks\r\n 2820 Free blocks\r\n\r\n.", "SHOW\r"},
	{"free slots\r\n\r\n\r\n.", ""},
}

// guest answers the pack of that name, or skips the test if there is none.
func guest(t *testing.T, name string) []byte {
	data, err := os.ReadFile(filepath.Join(os.Getenv("P2_11_ROOT"), "guest", name))
	if err != nil {
		t.Skip("no pack to begin with: ", err)
	}
	if len(data) != Blocks*BlockSize {
		t.Fatalf("%s is of %d bytes, and a pack has %d", name, len(data), Blocks*BlockSize)
	}
	return data
}

// here has the machine under test begin with the pack and holds the talk
// with it. It answers what the console has said, and leaves the pack as the
// talk has left it. This test is all the cogs there are: for every 2000
// instructions a cycle of the line passes, and what the console has to say
// leaves.
func here(t *testing.T, pack []byte, talk []line) []byte {
	var (
		machine pdp11.Machine
		console dl11.Line
		clock   kw11.Clock
		disk    Controller
		said    bytes.Buffer
	)
	console.Pace(&machine, 1000)
	disk.Connect(&machine, 0)
	disk.Attach(0, &file{pack}, false)
	if !machine.Attach(&clock, 0o177546, kw11.Size, 6) ||
		!machine.Attach(&disk, 0o177400, Size, 5) ||
		!machine.Attach(&console, 0o177560, dl11.Size, 4) {
		t.Fatal("no room on the bus")
	}
	machine.Reset()
	machine.Load(mac.BootAt, mac.Boot[:])
	machine.R[7] = mac.BootStart

	from := 0
	for _, l := range talk {
		for n := 0; ; n++ {
			if i := bytes.Index(said.Bytes()[from:], []byte(l.cue)); i >= 0 {
				from += i + len(l.cue)
				break
			}
			state := machine.Run(2000)
			clock.Tick()
			for console.Pending() {
				said.WriteByte(console.Next() & 0x7f)
				console.Sent()
			}
			if state == pdp11.Halted || state == pdp11.Faulted || n == 50000 {
				t.Errorf("waiting for %q: state %d, PC %06o, after %d instructions",
					l.cue, state, machine.R[7], machine.Count)
				return said.Bytes()
			}
		}
		for i := 0; i < len(l.typed); i++ {
			console.Put(l.typed[i])
		}
	}
	if console.Lost != 0 {
		t.Errorf("%d characters that were typed are lost", console.Lost)
	}
	t.Logf("%d instructions", machine.Count)
	return said.Bytes()
}

// there has the PDP-11/40 of SimH begin with the pack and holds the talk
// with it. It answers what the console has said, and leaves the pack as the
// talk has left it.
func there(t *testing.T, pack []byte, talk []line) []byte {
	simh := filepath.Join(os.Getenv("P2_11_ROOT"), "tools", "simh", "BIN", "pdp11")
	if _, err := os.Stat(simh); err != nil {
		t.Skip("no SimH to compare with: ", err)
	}
	dir := t.TempDir()
	image := filepath.Join(dir, "rk0.dsk")
	if err := os.WriteFile(image, pack, 0o600); err != nil {
		t.Fatal(err)
	}
	lines := []string{"set cpu 11/40", "set cpu nommu", "set cpu 56K"}
	for _, device := range strings.Fields("rha ptr ptp lpt dz rl hk rx rp rq tm tq rom") {
		lines = append(lines, "set "+device+" disabled")
	}
	for n := 1; n < 8; n++ {
		lines = append(lines, fmt.Sprintf("set rk%d disabled", n))
	}
	lines = append(lines, "attach rk0 "+image)
	for _, l := range talk {
		then := "echo #END; exit"
		if l.typed != "" {
			then = "send " + strconv.Quote(l.typed) + "; go"
		}
		lines = append(lines, "expect "+strconv.Quote(l.cue)+" "+then)
	}
	lines = append(lines, "echo #START", "boot rk0", "exit")
	ini := filepath.Join(dir, "talk.ini")
	if err := os.WriteFile(ini, []byte(strings.Join(lines, "\n")+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	out, err := exec.CommandContext(ctx, simh, ini).Output()
	_, body, begun := bytes.Cut(out, []byte("#START\n"))
	if err != nil || !begun || !bytes.Contains(body, []byte("#END")) {
		t.Fatalf("SimH: %v, and it said\n%s", err, out)
	}

	// SimH says what it does when something has come that it waited for,
	// and says it where the console is.
	body = regexp.MustCompile(regexp.QuoteMeta(ini)+`-\d+> [^\n]*\n`).ReplaceAll(body, nil)
	body, _, _ = bytes.Cut(body, []byte("#END"))
	for i := range body {
		body[i] &= 0x7f
	}
	left, err := os.ReadFile(image)
	if err != nil || len(left) < len(pack) {
		t.Fatalf("the pack SimH has left: %d bytes, %v", len(left), err)
	}
	copy(pack, left)
	return body
}

// differ fails the test if the two differ, and says where.
func differ(t *testing.T, what string, here, there []byte, around int) {
	if bytes.Equal(here, there) {
		return
	}
	i := 0
	for i < len(here) && i < len(there) && here[i] == there[i] {
		i++
	}
	from := max(i-around, 0)
	t.Errorf("%s: %d bytes here and %d in SimH, which differ at %d\nhere:    %q\nin SimH: %q",
		what, len(here), len(there), i,
		here[from:min(i+around, len(here))], there[from:min(i+around, len(there))])
}

func TestRT11(t *testing.T) {
	pack := guest(t, "RK0.DSK")
	ours := bytes.Clone(pack)
	theirs := bytes.Clone(pack)
	said := here(t, ours, rt11)
	if t.Failed() {
		t.Fatalf("the console has said:\n%s", said)
	}

	// The system begins with sending a terminal that is slow what gives it
	// time, which SimH leaves out.
	said = bytes.ReplaceAll(said, []byte{0}, nil)
	differ(t, "what the console has said", said, there(t, theirs, rt11), 60)
	differ(t, "the pack after the talk", ours, theirs, 16)
	if bytes.Equal(ours, pack) {
		t.Error("nothing was written to the pack")
	}
	t.Logf("the console has said:\n%s", said)
}
