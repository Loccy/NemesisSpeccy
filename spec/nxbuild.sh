#!/bin/sh
# nxbuild.sh out.nex : the Spectrum Next build (main snapshot + nx_low.asm as bank 8)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
cd "$HERE"
NEM_NEXT=1 NEM_FPT=2 python3 build.py > nxbuild.log 2>&1 || { tail -20 nxbuild.log; exit 1; }
grep -v '\.' nemesis_next.sym | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\): EQU \(0x[0-9A-F]*\)$/\1 equ \2 \& 0xFFFF/p' > nx_syms.inc
sjasmplus --nologo --msg=war --sym=nx_low.sym nx_low.asm
# The MSX2 graphics, if the user has put the patch's IPS next to nem.rom
python3 -I "$HERE/msx2_pack.py"
ENH=""
[ -f msx2_stages.dat ] && ENH=msx2_stages.dat
PB=$(grep -i "^plat_boot:" nemesis_next.sym | sed 's/.*0x0000//')
python3 -I "$HERE/sna2nex.py" nemesis_next.sna "$OUT" $PB AEA0 nx_low.bin $ENH
if [ -n "$ENH" ]; then python3 -I "$HERE/enh_patch.py" "$OUT" nemesis_next.sym msx2_patches.txt; fi
