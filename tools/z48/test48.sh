#!/bin/sh
# The 48K tapes' checks in the simulator (z48tap.py), as run for each
# preview.  Build the tapes first (spec/release48.sh).  About 4 minutes on
# two cores; the logs go to $OUT (default /tmp/test48).
#   1. the test tape and the plain tape (ship safe): four full loops of the
#      eight stages, every stage block loaded and unpacked over and over;
#   2. for each stage N: safe up to N, then mortal: the first game over must
#      come in stage N, and C must carry on in stage N (and every later game
#      over too, to the end of the run);
#   3. a game over in stage 2 and R: the rewind, stage 1 and the title;
#   4. pause (H) in stage 1: paused, then playing again.
# No run may reach the trap (z48_trap: Konami's code the 48K left out) or
# the ROM.  Prints PASS or FAIL for each, and exits 1 if any failed.
HERE=$(cd "$(dirname "$0")" && pwd)
SPEC=$HERE/../../spec
OUT=${OUT:-/tmp/test48}
mkdir -p "$OUT"
cd "$HERE"
run() {   # name, then env assignments and z48tap.py's arguments
    n=$1; shift
    env "$@" > "$OUT/$n.log" 2>&1
}
P=$SPEC/nemesis48h.tap; C=$SPEC/nemesis48hc.tap
(run loop_test SUF=hc timeout 600 python3 z48tap.py "$C" 7000 &
 run loop_plain SUF=h INV=99999 timeout 600 python3 z48tap.py "$P" 7000; wait)
for pair in "1 2" "3 4" "5 6" "7 8"; do
    for N in $pair; do
        run stage$N SUF=h INVST=$((N-1)) GOKEY=C GODELAY=150 timeout 600 python3 z48tap.py "$P" 3000 &
    done
    wait
done
(run rewind SUF=h INVST=1 GOKEY=R GODELAY=100 timeout 300 python3 z48tap.py "$P" 300 &
 run pause SUF=h PAUSEAT=1000 timeout 300 python3 z48tap.py "$P" 60; wait)
bad=0
ok() { echo "PASS $1"; }
no() { echo "FAIL $1: $2"; bad=1; }
traps() { grep -ciE 'TRAP|RESET|ROM \(PC' "$OUT/$1.log"; }
for t in loop_test loop_plain; do
    seq=$(grep -o "state [0-9] stage [0-9]" "$OUT/$t.log" | awk '{print $4}' | uniq | tr '\n' ' ')
    case "$seq" in
        *"1 2 3 4 5 6 7 8 1 2 3 4 5 6 7 8 1 2 3 4 5 6 7 8 1 2 3 4 5 6 7 8"*) [ "$(traps $t)" = 0 ] && ok "$t" || no "$t" "trap";;
        *) no "$t" "fewer than four loops";;
    esac
done
for N in 1 2 3 4 5 6 7 8; do
    l=$OUT/stage$N.log
    first=$(grep -m1 "^  game over at" "$l" | sed 's/.*(stage \([0-9]\)).*/\1/')
    wrong=$(grep "^  game over at" "$l" | grep -vc "(stage $N)")
    cont=$(grep -m1 "left game over" "$l" | grep -c "state 4, stage $N")
    if [ "$(traps stage$N)" != 0 ]; then no "stage $N" "trap"
    elif [ "$first" != "$N" ]; then no "stage $N" "first game over in stage ${first:-none}"
    elif [ "$cont" != 1 ]; then no "stage $N" "C did not carry on in stage $N"
    elif [ "$wrong" != 0 ]; then no "stage $N" "$wrong game overs in another stage"
    else ok "stage $N ($(grep -c '^  game over at' "$l") game overs, each continued)"; fi
done
l=$OUT/rewind.log
if [ "$(traps rewind)" = 0 ] && grep -q "game over at frame .* (stage 2)" "$l" && \
   sed -n '/game over at frame/,$p' "$l" | grep -q "state 5 stage 1"; then ok "rewind (R in stage 2, then stage 1 played)"; else no rewind "no return to stage 1"; fi
l=$OUT/pause.log
if [ "$(traps pause)" = 0 ] && grep -q "paused E10B=01 E047=01" "$l" && grep -q "E047=00" "$l"; then ok "pause"; else no pause "not paused and resumed"; fi
exit $bad
