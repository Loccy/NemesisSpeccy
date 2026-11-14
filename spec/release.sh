#!/bin/sh
# Build the release into release/: nemesis128-VERSION.{tap,sna}, the default
# build (adaptive pacing since 0.110; the title shows VERSION and A), and
# nemesisNext-VERSION.nex, the Spectrum Next build (the title shows VERSION and
# N); with ZEsarUX ($ZESARUX or on the PATH) the .NEX is also played for a
# minute (nx_smoke.py).
# VERSION must match the file VERSION.  The editions of 0.98-0.109 are build
# options: NEM_DRAW_EVERY=2 python3 build.py (fast), NEM_DRAW_EVERY=0 (smooth).
#   usage: release.sh VERSION
cd "$(dirname "$0")"
set -e
V=${1:?usage: release.sh VERSION}
# the title shows VERSION (build.py), so the file names must agree with it
if [ "$V" != "$(cat VERSION)" ]; then echo "release.sh: $V is not VERSION ($(cat VERSION))"; exit 1; fi
mkdir -p release
sh nxbuild.sh release/nemesisNext-${V}.nex > /dev/null
python3 nx_smoke.py release/nemesisNext-${V}.nex --msx2
python3 build.py > /dev/null
python3 make_tap.py > /dev/null
cp nemesis.tap release/nemesis128-${V}.tap
cp nemesis.sna release/nemesis128-${V}.sna
ls -l release/nemesis128-${V}.* release/nemesisNext-${V}.nex
