#!/bin/sh
# The 48K build's keep lists (reloc/z48_keepc_1.txt to z48_keepc_8.txt,
# z48_feonly.txt, z48_reads.txt), made from the two census runs of the MSX
# original kept here (cA.pkl, cB.pkl) and from reloc/gen.py's patches.
# About 90 seconds: the lists are made twice.
#
# The lists are made with gen.py's shared patches (NEM_Z48 off), as they
# were first made, and must match reloc/ exactly.  They are then made again
# with the 48K's own patches too (NEM_Z48=1), and must keep nothing that
# reloc/'s lists leave out: a 48K patch that reaches code the lists dropped
# fails the check.  (With the 48K's patches the lists keep less, as of
# 14 November 3:A115-A151 in every stage and 0:5BD3-5BF4 in stage 8: room
# that could be won back, by committing those lists and retesting.)
#
#   sh keep48.sh          remake the lists and check them against reloc/
#                         (exit 1 if any differs)
#   sh keep48.sh write    remake the lists and write them into reloc/
#
# spec/release48.sh runs the check whenever gen.py, these scripts, the
# census files or the platform's sources have changed since the last check.
# The census itself (census48.py) is run only if the census has to change:
#   TARGETS=1 python3 census48.py 40000 cA.pkl
#   DEATHS=1 GAMEOVER=1 python3 census48.py 60000 cB.pkl
# (about five minutes each, side by side; it needs the 128K build's test
# build first: cd spec && NEM_PIN_R=1 python3 build.py).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
cp "$HERE/cA.pkl" "$HERE/cB.pkl" "$W/"
make() {    # make the lists into $W/$1, with NEM_Z48=$2
    mkdir "$W/$1"
    ( cd "$W" && export NEM_ROOT="$ROOT" Z48_KEEP_OUT="$W/$1" NEM_Z48=$2 &&
      python3 "$HERE/keep1.py" > /dev/null && python3 "$HERE/keepN.py" > /dev/null &&
      for n in 1 2 3 4 5 6 7 8; do KEEP_PHASE=1 python3 "$HERE/keepC.py" $n > /dev/null; done &&
      for n in 1 2 3 4 5 6 7 8; do KEEP_PHASE=2 python3 "$HERE/keepC.py" $n > /dev/null; done &&
      python3 "$HERE/tabread.py" > /dev/null )
}
make out 0
cd "$W"
LISTS="z48_keepc_1.txt z48_keepc_2.txt z48_keepc_3.txt z48_keepc_4.txt z48_keepc_5.txt z48_keepc_6.txt z48_keepc_7.txt z48_keepc_8.txt z48_feonly.txt z48_reads.txt"
if [ "$1" = write ]; then
    for f in $LISTS; do cp "out/$f" "$ROOT/reloc/$f"; done
    echo "keep48.sh: the keep lists written into reloc/"
    exit 0
fi
bad=0
for f in $LISTS; do
    if ! cmp -s "out/$f" "$ROOT/reloc/$f"; then echo "keep48.sh: reloc/$f is not what the census and gen.py give now"; bad=1; fi
done
make out48 1
for f in $LISTS; do
    if [ -n "$(grep -v '^#' "out48/$f" | grep -vxFf "$ROOT/reloc/$f")" ]; then echo "keep48.sh: with the 48K's patches, $f keeps items reloc/$f leaves out"; bad=1; fi
done
if [ $bad = 1 ]; then
    echo "keep48.sh: the keep lists are out of date (sh tools/z48/keep48.sh write remakes them; then rebuild and retest)"
    exit 1
fi
echo "keep48.sh: the keep lists match the census and gen.py"
