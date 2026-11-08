#!/bin/sh
# nxbuild.sh out.nex : the Spectrum Next build (main snapshot + nx_low.asm as bank 8)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
cd "$HERE"
# Pacing: 30 ticks a second (the 60 Hz MSX's rate): screens 2, 2, 1 frames
# apart at most (nx_low.asm, PACE_30), and a tick left undrawn if the game
# falls behind 14 eighths of a frame a tick (pace_adapt).  NEM_PACE=25 for
# the previous pacing (15 eighths, screens at least 2 frames apart).
PACE=${NEM_PACE:-30}
if [ "$PACE" = 30 ]; then ADAPT_DEF=14,8; PDEF=-DPACE_30=1; else ADAPT_DEF=15,8; PDEF=; fi
# The Next's native graphics loads (native_next.py: native_next.dat for
# nx_pack.py, native_tables_next.asm for the build)
python3 -I "$HERE/native_next.py" > nxbuild_native.log 2>&1 || { tail -20 nxbuild_native.log; exit 1; }
NEM_NEXT=1 NEM_FPT=${NEM_FPT:-2} NEM_ADAPT=${NEM_ADAPT:-$ADAPT_DEF} python3 build.py > nxbuild.log 2>&1 || { tail -20 nxbuild.log; exit 1; }
grep -v '\.' nemesis_next.sym | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\): EQU \(0x[0-9A-F]*\)$/\1 equ \2 \& 0xFFFF/p' > nx_syms.inc
sjasmplus --nologo --msg=war --sym=nx_low.sym --lst=nx_low.lst $PDEF nx_low.asm
# stage 5's turrets and skeletons, and the shots over the scenery
# (nx_tur.asm): their own page, with the low bank's symbols
grep -v '\.' nx_low.sym | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\): EQU \(0x[0-9A-F]*\)$/\1 equ \2 \& 0xFFFF/p' > nx_lsyms.inc
sjasmplus --nologo --msg=war --sym=nx_tur.sym --lst=nx_tur.lst nx_tur.asm
# The graphics (spec/nxgfx: the character pool and the stage files; our
# drawings of Konami's sprite enemies from spec/nx_art.py): NEM_ARC_SPR=0
# leaves out the sprite drawings (nx_pack.py)
python3 -I "$HERE/nx_pack.py" >> nxbuild.log
PB=$(grep -i "^plat_boot:" nemesis_next.sym | sed 's/.*0x0000//')
python3 -I "$HERE/sna2nex.py" nemesis_next.sna "$OUT" $PB AEA0 nx_low.bin nx_gfx.dat
python3 -I "$HERE/enh_patch.py" "$OUT" nemesis_next.sym nxgfx/patches.txt
