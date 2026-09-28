#!/usr/bin/env python3
# Copyright 2026 The p2-11 Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""card.py puts a file of this machine into a file on the SD card in the
board's slot, or checks one there, through the board and over the serial
line, so that the card need not come out of the slot for a pack to go onto
it.

Usage: scripts/card.py [-port PORT] [-binary FILE] put IMAGE NAME
       scripts/card.py [-port PORT] [-binary FILE] sum NAME [IMAGE]

put writes IMAGE, block by block, into NAME on the card, which must be there
already and be at least as long: the program on the board knows where a file
is and not how to make one. It then reads the file back and compares. sum
prints the checksum of every block of NAME, or, given IMAGE, says which
blocks of NAME differ from it, and writes nothing.

	-port PORT    where the board is (default /dev/ttyUSB0)
	-binary FILE  the program to load, instead of building card/ afresh

The program on the board is card/card.ogo, which this script builds with
"ogo build ./card" unless -binary names one. The two speak in lines, and a
block goes as its 512 bytes after a header that sums them, a few blocks on
their way at once; card/card.ogo says the rest.
"""

import argparse
import collections
import os
import select
import subprocess
import sys
import time

BLOCK = 512
WINDOW = 4  # how many blocks are on their way at once
TRIES = 3   # how often a block is sent that arrives wrong
ESCAPE = 0x1b
FLIP = 0x40


def fletcher(p):
    """The Fletcher-32 checksum of a block, as the board sums it."""
    a = b = 0
    for v in p:
        a += v
        b += a
    return (b % 65535) << 16 | a % 65535


def escaped(p):
    """The bytes of a block as they go over the loader's terminal, which
    would take Ctrl-] and Ctrl-Z for itself."""
    out = bytearray()
    for v in p:
        if v in (ESCAPE, 0x1a, 0x1d):
            out.append(ESCAPE)
            v ^= FLIP
        out.append(v)
    return bytes(out)


class Board:
    """The program on the board, through the loader's terminal."""

    def __init__(self, binary, port):
        if subprocess.run(['fuser', '-s', port]).returncode == 0:
            sys.exit('card.py: %s is busy' % port)
        self.p = subprocess.Popen(
            ['ogo', 'loadp2', '-t', '-NOEOF', '-p', port, '-b', '230400', binary],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.buf = b''

    def line(self, timeout):
        """The next line from the loader, or None if none came in time."""
        end = time.time() + timeout
        while True:
            i = self.buf.find(b'\n')
            if i >= 0:
                line, self.buf = self.buf[:i], self.buf[i + 1:]
                return line.replace(b'\r', b'').decode('ascii', 'replace')
            left = end - time.time()
            if left <= 0:
                return None
            if select.select([self.p.stdout], [], [], left)[0]:
                b = os.read(self.p.stdout.fileno(), 65536)
                if not b:
                    sys.exit('card.py: the loader has come to an end')
                self.buf += b

    def said(self, timeout=30):
        """The next line the program says, which begins with a word of its
        own; the loader's lines are passed over."""
        while True:
            line = self.line(timeout)
            if line is None:
                sys.exit('card.py: the board said nothing for %d s' % timeout)
            first = line.split(' ', 1)[0]
            if first in ('card', 'file', 'ok', 'bad', 'error', 'error:', 'sum', 'done', 'bye'):
                return line

    def send(self, b):
        self.p.stdin.write(b)
        self.p.stdin.flush()

    def close(self):
        """Ends the program and the loader, which is not left with the port."""
        try:
            self.send(b'quit\n')
            self.line(5)
            self.send(b'\x1d')
            self.p.stdin.flush()
            self.p.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            self.p.kill()
            self.p.wait()


def begin(board, name):
    """Waits for the program to have the card, names the file to it, and
    answers how many blocks the file has."""
    line = board.said(60)
    if not line.startswith('card '):
        sys.exit('card.py: %s' % line)
    board.send(('file %s\n' % name).encode())
    line = board.said()
    words = line.split()
    if words[0] != 'file' or len(words) < 6:
        sys.exit('card.py: %s: %s' % (name, line))
    return int(words[2])


def sums(board, name, blocks):
    """The checksums of the file's blocks, as the board reads them."""
    board.send(b'sum\n')
    out = {}
    while True:
        line = board.said()
        words = line.split()
        if words[0] == 'done':
            break
        if words[0] != 'sum':
            sys.exit('card.py: %s: %s' % (name, line))
        out[int(words[1])] = int(words[2], 16)
    if len(out) != blocks:
        sys.exit('card.py: %s: %d of %d blocks summed' % (name, len(out), blocks))
    return out


def compare(board, name, blocks, data):
    """Answers the blocks of the file that differ from the data."""
    theirs = sums(board, name, blocks)
    return [i for i in range(len(data) // BLOCK) if theirs[i] != fletcher(data[i * BLOCK:(i + 1) * BLOCK])]


def ranges(blocks):
    """Numbers as 1-3, 5, 9-12."""
    out = []
    for i in blocks:
        if out and out[-1][1] + 1 == i:
            out[-1][1] = i
        else:
            out.append([i, i])
    return ', '.join(str(a) if a == b else '%d-%d' % (a, b) for a, b in out)


def progress(done, blocks):
    if sys.stderr.isatty():
        sys.stderr.write('\r%d of %d blocks' % (done, blocks))
        sys.stderr.flush()


def put(board, image, name):
    data = open(image, 'rb').read()
    blocks = (len(data) + BLOCK - 1) // BLOCK
    data += b'\0' * (blocks * BLOCK - len(data))
    have = begin(board, name)
    if blocks > have:
        sys.exit('card.py: %s has %d blocks, and %s on the card %d' % (image, blocks, name, have))

    began = time.time()
    pending = collections.deque(range(blocks))
    tries = collections.Counter()
    away = set()
    done = 0
    while pending or away:
        while pending and len(away) < WINDOW:
            i = pending.popleft()
            tries[i] += 1
            away.add(i)
            block = data[i * BLOCK:(i + 1) * BLOCK]
            board.send(b'block %d %08x\n' % (i, fletcher(block)) + escaped(block))
        words = board.said().split()
        if words[0] == 'ok':
            away.discard(int(words[1]))
            done += 1
            if done % 64 == 0 or done == blocks:
                progress(done, blocks)
        elif words[0] == 'bad':
            i = int(words[1])
            away.discard(i)
            if tries[i] >= TRIES:
                sys.exit('\ncard.py: block %d arrived wrong %d times' % (i, TRIES))
            pending.appendleft(i)
        else:
            sys.exit('\ncard.py: %s' % ' '.join(words))
    took = time.time() - began
    if sys.stderr.isatty():
        sys.stderr.write('\n')

    differ = compare(board, name, have, data)
    if differ:
        sys.exit('card.py: %s: written in %.0f s, and read back different at %s' %
                 (name, took, ranges(differ)))
    print('%s: %d blocks written in %.0f s, and read back as they were sent' % (name, blocks, took))


def sum_(board, name, image):
    have = begin(board, name)
    if image is None:
        for i, s in sorted(sums(board, name, have).items()):
            print('%d %08x' % (i, s))
        return
    data = open(image, 'rb').read()
    blocks = (len(data) + BLOCK - 1) // BLOCK
    data += b'\0' * (blocks * BLOCK - len(data))
    if blocks > have:
        sys.exit('card.py: %s has %d blocks, and %s on the card %d' % (image, blocks, name, have))
    differ = compare(board, name, have, data)
    more = '' if have == blocks else ', and %d blocks more' % (have - blocks)
    if differ:
        sys.exit('%s: %d of %d blocks differ from %s: %s%s' % (name, len(differ), blocks, image, ranges(differ), more))
    print('%s: %d blocks as in %s%s' % (name, blocks, image, more))


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('-port', default='/dev/ttyUSB0')
    p.add_argument('-binary')
    p.add_argument('-h', '--help', action='store_true')
    p.add_argument('what', nargs='*')
    args = p.parse_args()
    what = args.what
    if args.help or not (what[:1] == ['put'] and len(what) == 3 or what[:1] == ['sum'] and len(what) in (2, 3)):
        print(__doc__)
        sys.exit(0 if args.help else 2)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    binary = args.binary
    if binary is None:
        binary = os.path.join(root, 'card', 'card.binary')
        if subprocess.run(['ogo', 'build', os.path.join(root, 'card')], cwd=root).returncode != 0:
            sys.exit('card.py: the program did not build')

    board = Board(binary, args.port)
    try:
        if what[0] == 'put':
            put(board, what[1], what[2])
        else:
            sum_(board, what[1], what[2] if len(what) == 3 else None)
    finally:
        board.close()


if __name__ == '__main__':
    main()
