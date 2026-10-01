#!/usr/bin/env python3
# Copyright 2026 The p2-11 Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""font.py writes the font the VGA console shows a VT100's screen in.

Its characters are where package vt100 puts them in a cell: the special
graphics at 0 to 31, in the order of their set, ASCII, and Latin-1 from 0xA0,
with the pound sign of the United Kingdom set among it. 0x7F to 0x9F are blank.

The glyphs are Unscii's, by Viznut, of 8 by 16 dots, which is in the public
domain: unscii-16.hex of Unscii 2.1, which scripts/tools.sh fetches into
tools/. Seven that the VT100 has and Unscii has not are drawn here: the
pictures of HT, FF, CR, LF, NL and VT, two small letters one above the other,
as the VT100 drew them, and the sign for not equal, which is = with / over it.

The font is written as the tile driver of p2_vga_text reads it: 16 lines of
256 bytes, the top line of every character from character 0 and then the
next, a character's leftmost dot in the lowest bit; in longs, so that it is
aligned as the driver reads it.

Usage: scripts/font.py [-o FILE] [HEX]

	HEX      the font (default tools/unscii-16.hex)
	-o FILE  where to write (default vga/font.ogo)
"""

import argparse
import os
import sys

HEIGHT = 16

# The special graphics, 137 to 176 octal, as Unicode has them.
GRAPHICS = [
    0x00A0,  # _ blank
    0x25C6,  # ` diamond
    0x2592,  # a checkerboard, the error character
    0x2409,  # b HT
    0x240C,  # c FF
    0x240D,  # d CR
    0x240A,  # e LF
    0x00B0,  # f degree
    0x00B1,  # g plus or minus
    0x2424,  # h NL
    0x240B,  # i VT
    0x2518,  # j lower right corner
    0x2510,  # k upper right corner
    0x250C,  # l upper left corner
    0x2514,  # m lower left corner
    0x253C,  # n crossing lines
    0x23BA,  # o scan line 1
    0x23BB,  # p scan line 3
    0x2500,  # q scan line 5, a horizontal line
    0x23BC,  # r scan line 7
    0x23BD,  # s scan line 9
    0x251C,  # t left T
    0x2524,  # u right T
    0x2534,  # v bottom T
    0x252C,  # w top T
    0x2502,  # x vertical bar
    0x2264,  # y less than or equal
    0x2265,  # z greater than or equal
    0x03C0,  # { pi
    0x2260,  # | not equal
    0x00A3,  # } pound sign
    0x00B7,  # ~ centred dot
]

# Letters of 5 lines, for the pictures of the controls.
LETTERS = {
    'C': ['.XX', 'X..', 'X..', 'X..', '.XX'],
    'F': ['XXX', 'X..', 'XX.', 'X..', 'X..'],
    'H': ['X.X', 'X.X', 'XXX', 'X.X', 'X.X'],
    'L': ['X..', 'X..', 'X..', 'X..', 'XXX'],
    'N': ['X..X', 'XX.X', 'X.XX', 'X..X', 'X..X'],
    'R': ['XX.', 'X.X', 'XX.', 'X.X', 'X.X'],
    'T': ['XXX', '.X.', '.X.', '.X.', '.X.'],
    'V': ['X.X', 'X.X', 'X.X', 'X.X', '.X.'],
}

PICTURES = {0x2409: 'HT', 0x240C: 'FF', 0x240D: 'CR', 0x240A: 'LF', 0x2424: 'NL', 0x240B: 'VT'}


def picture(pair):
    """Answer the glyph of a control's picture: its first letter at the top
    left, its second at the bottom right."""
    rows = [0] * HEIGHT
    for letter, top, left in ((pair[0], 3, 1), (pair[1], 9, 4)):
        for y, line in enumerate(LETTERS[letter]):
            for x, dot in enumerate(line):
                if dot == 'X':
                    rows[top + y] |= 0x80 >> (left + x)
    return rows


def read(path):
    """Answer the glyphs of a .hex font of 8 by 16, by code point, each a list
    of 16 lines, the leftmost dot in the highest bit."""
    glyphs = {}
    with open(path) as f:
        for line in f:
            code, bits = line.strip().split(':')
            if len(bits) == 2 * HEIGHT:
                glyphs[int(code, 16)] = [int(bits[i:i + 2], 16) for i in range(0, len(bits), 2)]
    return glyphs


def reverse(b):
    """Answer a byte with its bits in the other order."""
    return int('{:08b}'.format(b)[::-1], 2)


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('-o', default='vga/font.ogo')
    p.add_argument('-h', '--help', action='store_true')
    p.add_argument('hex', nargs='?', default='tools/unscii-16.hex')
    args = p.parse_args()
    if args.help:
        print(__doc__)
        return
    if not os.path.exists(args.hex):
        sys.exit('font.py: no %s; scripts/tools.sh fetches it' % args.hex)

    glyphs = read(args.hex)
    for code, pair in PICTURES.items():
        glyphs[code] = picture(pair)
    glyphs[0x2260] = [a | b for a, b in zip(glyphs[ord('=')], glyphs[ord('/')])]

    codes = GRAPHICS + list(range(0x20, 0x7F)) + [None] * (0xA0 - 0x7F) + list(range(0xA0, 0x100))
    assert len(codes) == 256
    font = [[0] * 256 for _ in range(HEIGHT)]
    for c, code in enumerate(codes):
        if code is None:
            continue
        if code not in glyphs:
            sys.exit('font.py: %s has no U+%04X' % (args.hex, code))
        for y in range(HEIGHT):
            font[y][c] = reverse(glyphs[code][y])

    with open(args.o, 'w') as out:
        out.write('''// Copyright 2026 The p2-11 Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

// Code generated by scripts/font.py; DO NOT EDIT.

// Font is Unscii's of 8 by 16 dots, by Viznut, in the public domain, with the
// special graphics of the VT100 at 0 to 31, ASCII, and Latin-1 from 0xA0, as
// package vt100 puts characters in its cells: 16 lines of 256 bytes, a
// character's leftmost dot in the lowest bit.
var Font = [1024]uint32{
''')
        for y in range(HEIGHT):
            out.write('\t// line %d\n' % y)
            line = font[y]
            longs = [line[i] | line[i + 1] << 8 | line[i + 2] << 16 | line[i + 3] << 24 for i in range(0, 256, 4)]
            for i in range(0, 64, 8):
                out.write('\t' + ' '.join('0x%08x,' % v for v in longs[i:i + 8]) + '\n')
        out.write('}\n')


if __name__ == '__main__':
    main()
