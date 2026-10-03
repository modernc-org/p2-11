#!/bin/bash
# Copyright 2026 The p2-11 Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# twin.sh runs the tests of the packages that do not import p2 under Go, on this
# machine, from the sources the board runs.
#
# A package that does not touch the Propeller 2 is Go once it is given a package
# clause, with printf spelled fmt.Printf. This script makes that twin in a
# directory of its own -- every .ogo file as a .go file, under a go.mod that
# names the module ogo.mod does -- and runs "go vet" and "go test" there, with
# GOARCH=386 so that int is 32 bits wide as it is on the target.
#
# A .go file beside the .ogo files of a package goes into the twin as it is. It
# is where a test says what only this machine has the time for.
#
# Its use is a fast answer about the emulator's logic, and test sets too large
# to load onto a board. What the board does is decided on the board: ogo test.
#
# Usage: scripts/twin.sh [-k DIR] [go test arguments]
#   -k DIR   make the twin in DIR and keep it; by default it goes to a temporary
#            directory that is removed afterwards
#
#   scripts/twin.sh                     every package
#   scripts/twin.sh -run Vectors ./pdp11
set -eu
unset CDPATH
root=$(cd "$(dirname "$0")/.." && pwd)

keep=
if [ "${1:-}" = -k ]; then
	keep=${2:?usage: twin.sh [-k DIR] [go test arguments]}
	shift 2
fi
if [ -n "$keep" ]; then
	mkdir -p "$keep"
	twin=$(cd "$keep" && pwd)
else
	twin=$(mktemp -d)
	trap 'rm -rf "$twin"' EXIT
fi

module=$(awk '$1 == "module" { print $2 }' "$root/ogo.mod")
printf 'module %s\n\ngo 1.25\n' "$module" > "$twin/go.mod"

cd "$root"
find . -name '*.ogo' -not -path './tmp/*' -not -path './guest/*' -not -path './tools/*' -printf '%h\n' | sort -u |
	while read -r dir; do
		# A package that imports p2, or carries a Spin2 object, is for the
		# board only.
		if grep -q -s -E '^(import)?[[:space:]]*"p2"' "$dir"/*.ogo; then
			continue
		fi
		if compgen -G "$dir/*.spin2" > /dev/null; then
			continue
		fi
		if [ "$dir" = . ]; then
			package=main
		else
			package=$(basename "$dir")
		fi
		mkdir -p "$twin/$dir"
		for f in "$dir"/*.ogo; do
			out="$twin/${f%.ogo}.go"
			{
				printf 'package %s\n\n' "$package"
				if grep -q -E '(^|[^.[:alnum:]_])printf\(' "$f"; then
					printf 'import "fmt"\n\n'
				fi
				sed -E 's/(^|[^.[:alnum:]_])printf\(/\1fmt.Printf(/g' "$f"
			} > "$out"
		done
		for f in "$dir"/*.go; do
			if [ -e "$f" ]; then
				cp "$f" "$twin/$f"
			fi
		done
	done

# Where a test that begins with a pack finds it, and SimH, if they are there.
export P2_11_ROOT=${P2_11_ROOT:-$root}

cd "$twin"
if [ $# -eq 0 ]; then
	set -- ./...
fi
GOARCH=386 go vet ./...
GOARCH=386 go test "$@"
