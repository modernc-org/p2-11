#!/bin/bash
# Copyright 2026 The p2-11 Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# tools.sh fetches and builds what the other scripts use and the repository
# does not hold, into tools/, which git ignores:
#
#   tools/simh       SimH, whose PDP-11/40 is the reference scripts/vectors.py
#                    asks what an instruction does
#   tools/simtools   the macro11 cross assembler scripts/mac.py assembles the
#                    programs of mac/ with
#   tools/unscii-16.hex
#                    Unscii 2.1's font of 8 by 16, by Viznut, in the public
#                    domain, of which scripts/font.py makes the VGA console's
#
# None is needed to build the emulator, to run it or to test it: the vectors,
# the assembled programs and the font are in the repository. They are needed to
# make those again, and what is made is the same only from the same tools, so
# each is fetched at the revision the repository's were made with.
#
# Usage: scripts/tools.sh [SIMH-REVISION [SIMTOOLS-REVISION]]
set -eu
unset CDPATH

simh=${1:-87eb7d5e96f9ce0ee6ac183e20160e5c486b0712}     # Open SIMH V4.1-0 of 2026-07-15
simtools=${2:-2d9a2d96caa013428f8d0686e26a4f0164c889bf} # of 2022-12-25

# fetch DIRECTORY REPOSITORY REVISION
fetch() {
	if [ ! -d "$1/.git" ]; then
		git init -q "$1"
		git -C "$1" remote add origin "$2"
	fi
	if [ "$(git -C "$1" rev-parse -q --verify HEAD 2> /dev/null)" != "$3" ]; then
		git -C "$1" fetch -q --depth 1 origin "$3"
		git -C "$1" checkout -q --detach FETCH_HEAD
	fi
}

root=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$root/tools"
cd "$root/tools"

fetch simh https://github.com/open-simh/simh.git "$simh"
make -C simh pdp11 TESTS=0 NOVIDEO=1 NONETWORK=1

fetch simtools https://github.com/simh/simtools.git "$simtools"
make -C simtools/crossassemblers/macro11

unscii=2642c8b748fa81f24d76772d70c55faa720d98fadfec8133daf89136c5c8bfb1
if ! echo "$unscii  unscii-16.hex" | sha256sum -c --status 2> /dev/null; then
	curl -sS -o unscii-16.hex.new http://viznut.fi/unscii/unscii-16.hex
	echo "$unscii  unscii-16.hex.new" | sha256sum -c --quiet
	mv unscii-16.hex.new unscii-16.hex
fi

echo
echo "SimH:    $(git -C simh log -1 --format='%h %ad' --date=short)  tools/simh/BIN/pdp11"
echo "macro11: $(git -C simtools log -1 --format='%h %ad' --date=short)  tools/simtools/crossassemblers/macro11/macro11"
echo "Unscii:  2.1  tools/unscii-16.hex"
