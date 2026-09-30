#!/usr/bin/env python3
# Copyright 2026 The p2-11 Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""record.py records a session with Unix V6 on the board, for the README.

A shell with the prompt "$ " is started in a terminal of 80 columns and 24
rows, types "ogo run" in the repository's directory, and what the session
types to Unix is typed a moment after each prompt, at the pace of a person:
the kernel's name, root, a C program written with echo, compiled with cc and
run, and then what it made is removed and the buffers written out, twice,
before the terminal is left and the shell's prompt comes again. Everything
the terminal is sent is written down with the time it came, as an asciicast
of version 2, which asciinema plays:

	asciinema play v6-demo.cast

and from which agg, asciinema's converter, makes the GIF of the README, the
waits being left as long as they were:

	agg --idle-time-limit 120 --last-frame-duration 5 v6-demo.cast v6-demo.gif

The root pack of Unix V6 is to be on the card as RK0.DSK, and the session
leaves it as a talk does. A recording made again has the timing of its own
session, so it does not come out as the one before it did.

Usage: scripts/record.py [-port PORT] [CAST]

	-port PORT  the board's port, which is to be free before anything is
	            loaded (default /dev/ttyUSB0); ogo run finds the board itself
	CAST        where to write the recording (default v6-demo.cast)
"""

import argparse
import codecs
import fcntl
import json
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLUMNS, ROWS = 80, 24
PATIENCE = 240  # seconds, for any one prompt
PAUSE = 0.6  # seconds between a prompt and what is typed, as a person leaves
KEY = 0.07  # seconds between two keys

# What is waited for, and what is typed when it has come. None ends it.
SESSION = [
    ('$ ', 'ogo run\r'),
    ('@', 'rkunix.40\r'),
    ('login: ', 'root\r'),
    ('# ', 'echo \'main(){printf("hello, world\\n");}\' > hello.c\r'),
    ('# ', 'cat hello.c\r'),
    ('# ', 'cc hello.c\r'),
    ('# ', 'ls -l a.out\r'),
    ('# ', 'a.out\r'),
    ('# ', 'rm hello.c a.out\r'),
    ('# ', 'sync\r'),
    ('# ', 'sync\r'),
    ('# ', '\x1d'),  # leaves the loader's terminal
    ('$ ', None),
]


class Terminal:
    """A shell in a pseudo-terminal, and what it has said, with when."""

    def __init__(self):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(ROOT)
            env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'USER', 'LANG', 'GOPATH', 'GOROOT')}
            env.update(TERM='xterm-256color', PS1='$ ', COLUMNS=str(COLUMNS), LINES=str(ROWS))
            os.execvpe('bash', ['bash', '--norc', '--noprofile', '-i'], env)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack('HHHH', ROWS, COLUMNS, 0, 0))
        self.start = time.time()
        self.events = []
        self.unread = ''
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')

    def read(self, patience):
        """Take what the terminal has been sent within so many seconds."""
        if not select.select([self.fd], [], [], patience)[0]:
            return
        try:
            s = self.decoder.decode(os.read(self.fd, 4096))
        except OSError:
            return
        if s:
            self.events.append([round(time.time() - self.start, 6), 'o', s])
            self.unread += s

    def idle(self, seconds):
        """Go on taking what comes, for so many seconds."""
        end = time.time() + seconds
        while time.time() < end:
            self.read(0.01)

    def wait(self, cue):
        """Wait for the cue, and report whether it came."""
        end = time.time() + PATIENCE
        while cue not in self.unread:
            if time.time() > end:
                return False
            self.read(0.2)
        self.unread = self.unread[self.unread.index(cue) + len(cue):]
        return True

    def type(self, text):
        for c in text:
            os.write(self.fd, c.encode())
            self.idle(KEY)

    def end(self):
        os.write(self.fd, b'exit\r')
        time.sleep(0.5)
        try:
            os.kill(self.pid, 9)
        except OSError:
            pass


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('-port', default='/dev/ttyUSB0')
    p.add_argument('-h', '--help', action='store_true')
    p.add_argument('cast', nargs='?', default='v6-demo.cast')
    args = p.parse_args()
    if args.help:
        print(__doc__)
        return
    if subprocess.run(['fuser', '-s', args.port]).returncode == 0:
        sys.exit('record.py: %s is busy' % args.port)

    t = Terminal()
    failed = None
    try:
        for cue, typed in SESSION:
            if not t.wait(cue):
                failed = 'waited in vain for %r' % cue
                break
            if typed is None:
                break
            t.idle(1.0 if typed == '\x1d' else PAUSE)
            t.type(typed)
        t.idle(1.0)
    finally:
        if failed:
            os.write(t.fd, b'\x1d')  # the loader is not left with the port
            time.sleep(2)
        t.end()
    if failed:
        sys.exit('record.py: ' + failed)

    header = {
        'version': 2, 'width': COLUMNS, 'height': ROWS, 'timestamp': int(t.start),
        'title': 'p2-11: Unix V6 on a Propeller 2, booting and compiling',
        'env': {'SHELL': '/bin/bash', 'TERM': 'xterm-256color'},
    }
    with open(args.cast, 'w') as f:
        f.write(json.dumps(header) + '\n')
        for e in t.events:
            f.write(json.dumps(e) + '\n')
    print('%s: %.0f s' % (args.cast, t.events[-1][0]))


if __name__ == '__main__':
    main()
