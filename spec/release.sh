#!/bin/sh
# Build both editions into release/: nemesis_VERSION_fast.{tap,sna} (one
# tick in two drawn, the default build) and nemesis_VERSION_smooth.{tap,sna}
# (four ticks in five drawn).  VERSION must match the file VERSION, which
# the title screen shows.  Leaves the fast build in place.
#   usage: release.sh VERSION
cd "$(dirname "$0")"
set -e
V=${1:?usage: release.sh VERSION}
# the title shows VERSION (build.py), so the file names must agree with it
if [ "$V" != "$(cat VERSION)" ]; then echo "release.sh: $V is not VERSION ($(cat VERSION))"; exit 1; fi
mkdir -p release
NEM_DRAW_EVERY=0 python3 build.py > /dev/null
python3 make_tap.py > /dev/null
cp nemesis.tap release/nemesis_${V}_smooth.tap
cp nemesis.sna release/nemesis_${V}_smooth.sna
python3 build.py > /dev/null
python3 make_tap.py > /dev/null
cp nemesis.tap release/nemesis_${V}_fast.tap
cp nemesis.sna release/nemesis_${V}_fast.sna
ls -l release
