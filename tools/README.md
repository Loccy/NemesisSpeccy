# tools/

Tools for working on the port that are not part of the build
(`spec/build.py`) or of the regression checks (`spec/verify.sh`): the test
drivers for the Next build, the measurements against the MSX, the profiler,
the screenshot makers, and the tool that puts artwork into the Next build.

Each finds the repository from its own place (or from `NEM_ROOT`), and
needs what the build needs: `nem.rom` and the disassembly in `ref/`, and
usually a built `spec/nemesis.sna` and its `.sym`. Some keep results or
look for ZEsarUX in folders beside the repository (`night2`, and ZEsarUX in
`zes`); `NEM_SCRATCH` names the folder that holds those, by default the one
the repository is in.

The scripts that were used once and will not be needed again (the makers of
the committed artwork, the investigations and probes of earlier versions,
the one-time checks of 1.1, old measurement data) are not kept here. They
are in the repository's history: the last commit that holds them is
1ebf098 (12 November 2026).

## The 48K version (`z48/`)

Unlike the rest of `tools/`, these are part of the 48K build.
`spec/release48.sh` runs `keep48.sh`, and the keep lists in `reloc/` come
from the scripts here.

* `keep48.sh`: remakes the keep lists (`reloc/z48_keepc_1.txt` to
  `z48_keepc_8.txt`, `z48_feonly.txt`, `z48_reads.txt`) from the census
  and gen.py, and checks them against `reloc/` (about 90 seconds); `sh
  keep48.sh write` writes them.  It runs `keep1.py`, `keepN.py`,
  `keepC.py` (twice for each stage) and `tabread.py`, which use `reach.py`
  (the static pass over the relocator's items) and `report48.py` (the
  census by stage).
* `census48.py`, `cA.pkl`, `cB.pkl`: the census of the MSX original the
  lists are made from, and its two recorded routes.  Rerun only if the
  census has to change (`keep48.sh` says how; about five minutes a route,
  after a test build of the 128K, `NEM_PIN_R=1 python3 build.py`).
* `test48.sh`: the 48K checks: both tapes through four loops, each stage's
  game over and continue, a rewind and the pause, in a simulator (about 4
  minutes; build the tapes first).
* `z48tap.py`: plays a 48K tape in SkoolKit's 48K simulator, loading each
  stage from the tape as the game asks (its options are in its docstring);
  `fbus.py` gives it a 48K's floating bus.
* `run128.py`: runs the 128K build from a chosen stage, for comparing
  screens with the 48K's.

## Testing the Next build

`nexttest/`: the Next build in ZEsarUX, headless, driven through ZRCP
(`$ZESARUX`, or `zes/src/zesarux` in the scratch folder). The Next has no
simulator, so these are its only automatic tests beyond `verify.sh`
assembling it.

* `fulltest.py NEX OUT PORT` plays the whole game with an invulnerable copy
  (the bonus route unless `NOTARGET`; `LOOPS=2` for the second loop) and
  checks the code and read-only pages at every stage, dumping the store, the
  name table and both Layer 2 screens.
* `nx_ftcmp.py A B` compares two runs' dumps (characters on show, sprite
  patterns, marks, Layer 2 pixels and colour entries).
* `hunt.py` is `fulltest.py` with a breakpoint on writes to 01B1 (the crash
  in 1.0N). `replay.py` adds ZEsarUX snapshots (`SNAPDIR`/`SNAPAT` to save
  at a loop, stage and distance; `FROM` to replay attempts from one, with
  `JITTER`).
* `nx_poll.py`, `nx_pollcmp.py`: dumps at points of a run, and their
  comparison.
* `l2png.py`: Layer 2 dumps as false-colour PNGs.

The dumps compare memory, not the picture: a wrong scroll split, palette or
hardware sprite passes them.

## Measurements

* `measure/`: the MSX against the Spectrum, the scripts behind section 6.8
  of the technical description. `msx50.py` (the MSX at 50 Hz, BIOS time
  charged), `specrun.py` (a Spectrum build, same play), `msx_loop.py` (the
  MSX through the whole first loop with every weapon), `lag2.py` (Spectrum
  input lag) and `msx_lag3.py` (the MSX's, measured the same way).
* `measure/feel/` (README there): how fast the game feels per displayed
  frame, on the MSX (`msx_feel.py`), the 128K (`pp_feel.py`) and the Next
  (`nx_feel.py`), and their analysis (`feel_an.py`).
* `measure/prof/` (README there): an exact profile of the 128K build, every
  instruction's T-states by address and page, with its analysis by routine
  and by stage.
* `perfprofile.py` (0.109): speed and smoothness of a build over stages
  1-2. `pp_feel.py` is its successor.

## Screenshots

`natural.py` and `natural_win.py` made the website's screenshots (the ship
steered along a weaving path); `shoot.py` takes a screenshot a second.

## Artwork for the Next build

`pool/put_blocks.py STAGE MODULE.py` writes blocks into the Next's
character pool (`spec/nxgfx/pool.bin`, `maps.bin`) and points the stage's
map at them. MODULE is a Python file giving `BLOCKS`, {(third, character):
64 pixel values}, and optionally `PALETTE`, the stage's scenery palette
D1-DF. This is how the Next's scenery is changed.
