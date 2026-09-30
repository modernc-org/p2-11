#!/usr/bin/env python3
# Copyright 2026 The p2-11 Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""poster.py puts the last frame of a GIF first, as its poster.

What does not play a GIF shows its first frame: a forum that shrinks it, a
feed reader, the thumbnail a blog makes of a post. The first frame of a
recorded session is an empty terminal with a prompt in it, and the last one is
the session done, so the last one is put in front of the rest, held for a
while, and the recording plays from its beginning after it.

Usage: scripts/poster.py [-hold MS] GIF [OUT]

	-hold MS  how long the poster is shown before the recording plays
	          (default 3000)
	GIF       the recording, as agg makes it
	OUT       where to write the result (default: over GIF)

It wants Pillow, which decodes each frame whole, agg having written most of
them as what changed since the one before, and numpy.
"""

import argparse
import os
import sys

import numpy

from PIL import Image


def frames(path):
    """Answer the frames of the GIF, each a whole picture, and how long each
    is shown, in milliseconds."""
    im = Image.open(path)
    out = []
    for i in range(im.n_frames):
        im.seek(i)
        out.append((im.convert('RGB'), im.info.get('duration', 100)))
    return out


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('-hold', type=int, default=3000)
    p.add_argument('-h', '--help', action='store_true')
    p.add_argument('gif', nargs='?')
    p.add_argument('out', nargs='?')
    args = p.parse_args()
    if args.help or not args.gif:
        print(__doc__)
        return

    shown = frames(args.gif)
    last = shown[-1][0]
    if shown[0][0].tobytes() == last.tobytes():
        sys.exit('poster.py: %s begins with its last frame already' % args.gif)
    shown = [(last, args.hold)] + shown

    # One palette of every colour the frames have, which a terminal's few fit
    # in, and each pixel the index of its own colour in it. Pillow's quantize
    # comes near a colour, not to it.
    colours = set()
    for im, _ in shown:
        colours.update(c for _, c in im.getcolors(1 << 24))
    if len(colours) > 256:
        sys.exit('poster.py: %s has %d colours, more than a GIF has' % (args.gif, len(colours)))
    colours = sorted(colours)
    keys = numpy.array([r << 16 | g << 8 | b for r, g, b in colours])
    pictures = []
    for im, _ in shown:
        a = numpy.asarray(im, dtype=numpy.uint32)
        index = numpy.searchsorted(keys, a[..., 0] << 16 | a[..., 1] << 8 | a[..., 2])
        p = Image.fromarray(index.astype(numpy.uint8), 'P')
        p.putpalette([v for c in colours for v in c])
        pictures.append(p)

    out = args.out or args.gif
    new = out + '.new.gif'
    try:
        pictures[0].save(new, save_all=True, append_images=pictures[1:],
                         duration=[d for _, d in shown], loop=0, optimize=True)
        check = frames(new)
        if len(check) != len(shown) or any(a[0].tobytes() != b[0].tobytes() for a, b in zip(check, shown)):
            sys.exit('poster.py: the frames written are not the frames read')
        os.replace(new, out)
    finally:
        if os.path.exists(new):
            os.unlink(new)
    print('%s: %d frames, the first of them the last, held %d ms, %d bytes' %
          (out, len(shown), args.hold, os.path.getsize(out)))


if __name__ == '__main__':
    main()
