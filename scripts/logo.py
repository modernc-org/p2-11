#!/usr/bin/env python3
# Copyright 2026 The p2-11 Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""logo.py writes logo.svg: the name of the project, with its two ones drawn
as the toggle switches of a front panel, up.

Everything is drawn here as strokes of one width, so that no typeface is
part of it, and nothing in it is a mark of anyone's, DEC's or Parallax's
among them. There is a dark plate, an off-white for the letters and a red
for the switches.

Usage: scripts/logo.py [-o FILE]

	-o FILE   where to write it (default logo.svg in the repository's root)
"""

import argparse
import os

INK = '#231e2b'   # the plate
BONE = '#ece6d8'  # the letters
RED = '#d94f70'   # the switches

WIDTH = 16        # of a stroke
HALF = WIDTH / 2  # what a stroke with round ends overhangs its line by
GAP = 18          # between two glyphs, from the edge of one to the next

# A glyph is drawn about x on a baseline at y 100, its letters reaching
# from y 30 to 130. It answers what it draws, and how far left and right of
# x its lines reach.


def p(x, colour):
    return ('<path d="M%g,30 V130" stroke="%s"/>'
            '<circle cx="%g" cy="65" r="35" stroke="%s"/>' % (x, colour, x + 35, colour), 0, 70)


def two(x, colour):
    return ('<path d="M%g,40 A30,30 0 0 1 %g,40 C%g,64 %g,78 %g,100 L%g,100" stroke="%s"/>'
            % (x, x + 60, x + 60, x + 30, x + 2, x + 60, colour), 0, 60)


def hyphen(x, colour):
    return '<path d="M%g,60 H%g" stroke="%s"/>' % (x, x + 30, colour), 0, 30


def toggle(x, colour):
    """A one that is a toggle switch: its bezel, its handle, and the knob
    on the end of it."""
    return ('<path d="M%g,100 H%g" stroke="%s"/>'
            '<path d="M%g,100 V28" stroke="%s"/>'
            '<circle cx="%g" cy="26" r="14" fill="%s" stroke="none"/>'
            % (x - 20, x + 20, colour, x, colour, x, colour), -20, 20)


def layout(glyphs):
    """Draws the glyphs left to right, a gap between them and a nudge where
    one is asked for, and answers the drawing and how wide it is."""
    out = []
    pen = 0
    for glyph, colour, nudge in glyphs:
        pen += nudge
        _, left, right = glyph(0, colour)
        x = pen - left + HALF
        drawing, _, _ = glyph(x, colour)
        out.append(drawing)
        pen = x + right + HALF + GAP
    return ''.join(out), pen - GAP


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-o', default=os.path.join(root, 'logo.svg'))
    parser.add_argument('-h', '--help', action='store_true')
    args = parser.parse_args()
    if args.help:
        print(__doc__)
        return

    drawing, width = layout([
        (p, BONE, 0),
        (two, BONE, 0),
        (hyphen, BONE, -2),
        (toggle, RED, -2),
        (toggle, RED, 0),
    ])
    across, down = 44, 30  # the plate's margins
    w, h = width + 2 * across, 138 + 2 * down
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g" width="%g" height="%g" role="img" aria-label="p2-11">\n'
           '  <title>p2-11</title>\n'
           '  <rect width="%g" height="%g" rx="22" fill="%s"/>\n'
           '  <g transform="translate(%g,%g)" fill="none" stroke-width="%g" stroke-linecap="round" stroke-linejoin="round">\n'
           '    %s\n'
           '  </g>\n'
           '</svg>\n' % (w, h, w, h, w, h, INK, across, down - 2, WIDTH, drawing))
    with open(args.o, 'w') as f:
        f.write(svg)


if __name__ == '__main__':
    main()
