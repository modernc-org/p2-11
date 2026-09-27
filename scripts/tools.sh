#!/bin/bash
# Copyright 2026 The p2-11 Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# tools.sh fetches and builds the two programs the other scripts use and the
# repository does not hold, into tools/, which git ignores:
#
#   tools/simh       SimH, whose PDP-11/40 is the reference scripts/vectors.py
#                    asks what an instruction does
#   tools/simtools   the macro11 cross assembler scripts/mac.py assembles the
#                    programs of mac/ with
#
# Neither is needed to build the emulator, to run it or to test it: the vectors
# and the assembled programs are in the repository. They are needed to make
# those again.
#
# Usage: scripts/tools.sh
set -eu
unset CDPATH
root=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$root/tools"
cd "$root/tools"

if [ ! -d simh ]; then
	git clone --depth 1 https://github.com/open-simh/simh.git
fi
make -C simh pdp11 TESTS=0 NOVIDEO=1 NONETWORK=1

if [ ! -d simtools ]; then
	git clone --depth 1 https://github.com/simh/simtools.git
fi
make -C simtools/crossassemblers/macro11

echo
echo "SimH:    $(git -C simh log -1 --format='%h %ad' --date=short)  tools/simh/BIN/pdp11"
echo "macro11: $(git -C simtools log -1 --format='%h %ad' --date=short)  tools/simtools/crossassemblers/macro11/macro11"
