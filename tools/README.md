# tools/

Tools for working on the port that are not part of the build
(`spec/build.py`) or of the regression checks (`spec/verify.sh`): the test
drivers for the Next build, the measurements against the MSX, the profiler,
the screenshot makers, and the tool that puts artwork into the Next build.

Each finds the repository from its own place (or from `NEM_ROOT`), and
needs what the build needs: `nem.rom` and the disassembly in `ref/`, and
usually a built `spec/nemesis.sna` and its `.sym`. Several keep working
copies and results in folders beside the repository (`work`, `night2`, and
ZEsarUX in `zes`); `NEM_SCRATCH` names the folder that holds those, by
default the one the repository is in.

The scripts that were used once and will not be needed again (the makers of
the committed artwork, the investigations and probes of earlier versions,
the one-time checks of 1.1, old measurement data) are not kept here. They
are in the repository's history: the last commit that holds them is
1ebf098 (12 November 2026).

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
* `l2png.py`: Layer 2 dumps as false-colour PNGs. `sheets.py`: contact
  sheets of `fulltest.py`'s screenshots.

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
  and by stage; and `nxdiff.py`, a Next build against 1.1.3N.
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
