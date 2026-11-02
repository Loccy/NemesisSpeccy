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
NEM_NEXT=1 NEM_FPT=${NEM_FPT:-2} NEM_ADAPT=${NEM_ADAPT:-$ADAPT_DEF} python3 build.py > nxbuild.log 2>&1 || { tail -20 nxbuild.log; exit 1; }
grep -v '\.' nemesis_next.sym | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\): EQU \(0x[0-9A-F]*\)$/\1 equ \2 \& 0xFFFF/p' > nx_syms.inc
sjasmplus --nologo --msg=war --sym=nx_low.sym $PDEF nx_low.asm
# The MSX2 graphics, if the user has put the patch's IPS next to nem.rom
python3 -I "$HERE/msx2_pack.py"
ENH=""
[ -f msx2_stages.dat ] && ENH=msx2_stages.dat
PB=$(grep -i "^plat_boot:" nemesis_next.sym | sed 's/.*0x0000//')
python3 -I "$HERE/sna2nex.py" nemesis_next.sna "$OUT" $PB AEA0 nx_low.bin $ENH
if [ -n "$ENH" ]; then python3 -I "$HERE/enh_patch.py" "$OUT" nemesis_next.sym msx2_patches.txt; fi
