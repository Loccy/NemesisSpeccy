#!/bin/sh
# Regression checks for the Spectrum build (run after build.py).
#   check_names: map buffer tracking keeps name_shadow in step with Konami
#   check_screen: drawn cells match the converted tile set
#   check_sprites: sprites and their colours (MISSILE=1: the missile along the ground)
#   check_tiles: converted tiles match the MSX shadows under their fit
#   test_convert: convert_tile against the Python model
#   test_kempston: the Kempston interface (both buttons) and hold-to-select
#   lockstep_spec: Konami RAM against the MSX original (test build)
cd "$(dirname "$0")"
set -e
# test_convert reads Konami's graphics captured from the ROM; make the capture on first use
[ -f vram_states.pkl ] || python3 gfxcap.py
python3 check_names.py 240 0 | tail -1
python3 check_screen.py 120 0 2 | tail -1
python3 check_sprites.py 60 0 3 | tail -1
MISSILE=1 python3 check_sprites.py 60 0 3 | tail -1
python3 test_keys.py | tail -1
python3 test_kempston.py | tail -1
python3 check_tiles.py 60 0 15 | tail -1
python3 test_convert.py | tail -1
NEM_PIN_R=1 python3 build.py > /dev/null
python3 lockstep_spec.py ${LOCK_TICKS:-3000} | tail -1
