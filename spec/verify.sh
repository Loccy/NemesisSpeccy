#!/bin/sh
# Regression checks for the Spectrum build (run after build.py).
#   check_names: map buffer tracking keeps name_shadow in step with Konami
#   check_screen: drawn cells match the converted tile set
#   check_sprites: sprites and their colours (MISSILE=1: the missile along the ground)
#   test_kempston: the Kempston interface (both buttons) and hold-to-select
#   lockstep_spec: Konami RAM against the MSX original (test build)
#   (the native build, branch no-msx: the tiles are converted when the game
#   is built, so check_tiles and test_convert have nothing to check; the
#   pictures are checked against 1.0 by screen_lockstep.py; the Next build
#   is not carried on this branch yet)
cd "$(dirname "$0")"
set -e
python3 check_names.py 240 0 | tail -1
python3 check_screen.py 120 0 2 | tail -1
python3 check_sprites.py 60 0 3 | tail -1
MISSILE=1 python3 check_sprites.py 60 0 3 | tail -1
python3 test_keys.py | tail -1
python3 test_kempston.py | tail -1
NEM_PIN_R=1 python3 build.py > /dev/null
python3 lockstep_spec.py ${LOCK_TICKS:-3000} | tail -1
echo "nxbuild: skipped (the Next is not carried on the native branch yet)"
