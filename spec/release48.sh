#!/bin/sh
# Build the 48K multiload tapes: release/nemesis48_VERSION.tap, and the
# test tape nemesis48hc.tap (here in spec/: ours only, not released; the
# ship is safe and powered up each life).  Each tape holds the core and
# eight stage blocks, one image of the game per stage (build48.py with
# Z48_SHARED=1 and Z48_STAGE=1 to 8), packed with zx0 (make_tap48.py).
#
# First the keep lists (reloc/z48_keepc_*.txt) are checked against the
# census and gen.py (tools/z48/keep48.sh, about 90 seconds), but only when
# gen.py, the platform's sources, the list scripts, the census or the ROM
# have changed since the last check passed (reloc/z48_keep.stamp).
#
# About 40 seconds once the layout search's answers are kept
# (z48_fitcache.json); the first build in a fresh tree takes a few minutes.
#   usage: release48.sh VERSION
cd "$(dirname "$0")"
set -e
V=${1:?usage: release48.sh VERSION}
if [ "$V" != "$(cat VERSION)" ]; then echo "release48.sh: $V is not VERSION ($(cat VERSION))"; exit 1; fi
STAMP=../reloc/z48_keep.stamp
NOW=$(cat ../reloc/gen.py ../reloc/listing.py ../reloc/z80info.py ../tools/z48/*.py ../tools/z48/*.pkl \
      plat_spec.asm native.asm convert.asm render.asm pace.asm ship.asm star_check7.asm spr_pmap.asm \
      ../nem.rom | md5sum | cut -c1-32)
if [ "$(cat $STAMP 2>/dev/null)" != "$NOW" ]; then
    sh ../tools/z48/keep48.sh
    echo "$NOW" > $STAMP
fi
for C in "" c; do
    for n in 1 2 3 4 5 6 7 8; do
        if [ -n "$C" ]; then export Z48_CHEAT=1; else unset Z48_CHEAT; fi
        Z48_SHARED=1 Z48_STAGE=$n python3 build48.py > /dev/null
    done
    python3 make_tap48.py nemesis48h$C.tap NEMESIS48 nemesis48h$C.sna \
        nemesis48_s2h$C.sna nemesis48_s3h$C.sna nemesis48_s4h$C.sna nemesis48_s5h$C.sna \
        nemesis48_s6h$C.sna nemesis48_s7h$C.sna nemesis48_s8h$C.sna
done
mkdir -p release
cp nemesis48h.tap release/nemesis48_${V}.tap
ls -l release/nemesis48_${V}.tap nemesis48hc.tap
