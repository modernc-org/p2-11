#!/usr/bin/env python3
# Copyright 2026 The p2-11 Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""talk.py holds a talk with what is on a pack, on the board and in SimH.

The talk is the one of rk11/host_test.go, which that test holds with the
machine where it runs under Go: what is waited for, and what is typed when it
has come. This script loads the program onto the board, which begins with the
pack that is RK0.DSK on its card, and types what the talk says when the
console has said what the talk waits for. It has the PDP-11/40 of SimH do the
same with a copy of the pack, and compares what the two consoles have said.

The pack is no part of the repository, and neither is SimH, which
scripts/tools.sh fetches and builds. The pack on the card is written to by a
talk that writes, and is after it what the copy is that SimH has written to.

Usage: scripts/talk.py [-simh PDP11] [-pack FILE] [-port PORT] [-o DIR] [BINARY]

	-simh PDP11  the SimH binary (default $SIMH, or tools/simh/BIN/pdp11)
	-pack FILE   the pack SimH begins with (default guest/RK0.DSK)
	-port PORT   where the board is (default /dev/ttyUSB0)
	-o DIR       where to leave what the two have said, board.txt and
	             simh.txt, and the pack as SimH has left it, simh.dsk

The binary is p2-11.binary unless one is named. It is what "ogo build" makes.
"""

import argparse
import ast
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time

PACK = 4872 * 512
PATIENCE = 150  # seconds, for all of the talk


def talk(source):
    """Answer the lines of the talk in the Go source: what is waited for,
    and what is typed."""
    text = open(source).read()
    m = re.search(r'^var rt11 = \[\]line\{\n(.*?)^\}', text, re.M | re.S)
    if not m:
        sys.exit('talk.py: %s: no talk there' % source)
    string = r'"(?:[^"\\]|\\.)*"'
    lines = re.findall(r'\{(%s), (%s)\}' % (string, string), m.group(1))
    return [(ast.literal_eval(cue), ast.literal_eval(typed)) for cue, typed in lines]


def quoted(s):
    return '"%s"' % s.replace('\\', '\\\\').replace('\r', '\\r').replace('\n', '\\n').replace('"', '\\"')


def simh(binary, pack, lines, tmp):
    """Answer what the console of SimH has said, and the pack as it is
    left."""
    image = os.path.join(tmp, 'rk0.dsk')
    shutil.copy(pack, image)
    os.chmod(image, 0o600)
    ini = ['set cpu 11/40', 'set cpu nommu', 'set cpu 56K']
    for dev in 'rha ptr ptp lpt dz rl hk rx rp rq tm tq rom'.split():
        ini.append('set %s disabled' % dev)
    for n in range(1, 8):
        ini.append('set rk%d disabled' % n)
    ini.append('attach rk0 %s' % image)
    for cue, typed in lines:
        then = 'send %s; go' % quoted(typed) if typed else 'echo #END; exit'
        ini.append('expect %s %s' % (quoted(cue), then))
    ini += ['echo #START', 'boot rk0', 'exit']
    path = os.path.join(tmp, 'talk.ini')
    with open(path, 'w') as f:
        f.write('\n'.join(ini) + '\n')
    try:
        out = subprocess.run([binary, path], capture_output=True, timeout=60).stdout
    except subprocess.TimeoutExpired:
        sys.exit('talk.py: SimH did not come to an end')
    except OSError as e:
        sys.exit('talk.py: %s: %s; scripts/tools.sh builds it' % (binary, e.strerror))
    if b'#START\n' not in out or b'#END' not in out:
        sys.exit('talk.py: SimH said\n%s' % out[-2000:].decode(errors='replace'))

    # SimH says what it does when something has come that it waited for, and
    # says it where the console is.
    out = re.sub(re.escape(path.encode()) + rb'-\d+> [^\n]*\n', b'', out)
    said = out.split(b'#START\n', 1)[1].split(b'#END', 1)[0]
    with open(image, 'rb') as f:
        return bytes(b & 0x7f for b in said), f.read()[:PACK]


def board(binary, port, lines):
    """Answer what the board has said, from when it was loaded."""
    if subprocess.run(['fuser', '-s', port]).returncode == 0:
        sys.exit('talk.py: %s is busy' % port)
    p = subprocess.Popen(['ogo', 'loadp2', '-t', '-NOEOF', '-p', port, '-b', '230400', binary],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    said = b''
    at = 0
    end = time.time() + PATIENCE
    try:
        for cue, typed in lines:
            while True:
                i = said.find(cue.encode(), at)
                if i >= 0:
                    at = i + len(cue)
                    break
                if time.time() > end:
                    print('talk.py: waiting for %r' % cue)
                    return said
                if select.select([p.stdout], [], [], 1)[0]:
                    b = os.read(p.stdout.fileno(), 4096)
                    if not b:
                        print('talk.py: the loader has come to an end')
                        return said
                    # What gives a slow terminal time is left out, as SimH
                    # leaves it out.
                    said += bytes(c & 0x7f for c in b).replace(b'\0', b'')
            p.stdin.write(typed.encode())
            p.stdin.flush()
    finally:
        # The loader is not left with the port.
        try:
            p.stdin.write(b'\x1d')
            p.stdin.flush()
            p.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            p.kill()
            p.wait()
    return said


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('-simh', default=os.environ.get('SIMH', 'tools/simh/BIN/pdp11'))
    p.add_argument('-pack', default='guest/RK0.DSK')
    p.add_argument('-port', default='/dev/ttyUSB0')
    p.add_argument('-o')
    p.add_argument('-h', '--help', action='store_true')
    p.add_argument('binary', nargs='?', default='p2-11.binary')
    args = p.parse_args()
    if args.help:
        print(__doc__)
        return
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lines = talk(os.path.join(root, 'rk11', 'host_test.go'))
    if not os.path.exists(args.pack) or os.path.getsize(args.pack) != PACK:
        sys.exit('talk.py: %s is no pack of %d bytes' % (args.pack, PACK))
    with tempfile.TemporaryDirectory() as tmp:
        there, left = simh(args.simh, args.pack, lines, tmp)
    began = time.time()
    all_of_it = board(args.binary, args.port, lines)
    took = time.time() - began

    # What the program says before the machine begins is not the machine's.
    first = lines[0][0].encode()
    begin = there[:there.find(first)] if first in there else there
    i = all_of_it.find(begin[:16])
    here = all_of_it[i:] if i >= 0 else all_of_it
    if args.o:
        os.makedirs(args.o, exist_ok=True)
        for name, data in (('board.txt', all_of_it), ('simh.txt', there), ('simh.dsk', left)):
            with open(os.path.join(args.o, name), 'wb') as f:
                f.write(data)
    if here == there:
        print('%d lines of talk in %.0f s, and the board has said what SimH has: %d bytes' %
              (len(lines), took, len(here)))
        return
    i = 0
    while i < min(len(here), len(there)) and here[i] == there[i]:
        i += 1
    print('the board has said %d bytes and SimH %d, which differ at %d' % (len(here), len(there), i))
    print('the board: %r' % here[max(0, i - 60):i + 60])
    print('SimH:      %r' % there[max(0, i - 60):i + 60])
    sys.exit(1)


if __name__ == '__main__':
    main()
