# tools/

Tools written while the port was made: test drivers for the Next build,
measurements against the MSX, profilers, and the scripts that made the
artwork. None of them is part of the build (`spec/build.py`) or of the
regression checks (`spec/verify.sh`); they are kept because the questions
they answer come back, and because some are the only record of how a piece
of artwork or a figure in the docs was produced.

They are working tools, not polished ones. Each finds the repository from
its own place (or from `NEM_ROOT`), and needs what the build needs: `nem.rom`
and the disassembly in `ref/`, and usually a built `spec/nemesis.sna` and
its `.sym`. Several keep working copies and results in folders beside the
repository (`work`, `night2`, `moai`, `v121`, and ZEsarUX in `zes`);
`NEM_SCRATCH` names the folder that holds those, by default the one the
repository is in.

## Testing the Next build

`nexttest/`: the Next build in ZEsarUX, headless, driven through ZRCP
(`$ZESARUX`, or `zes/src/zesarux` in the scratch folder).

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
  comparison. `nx_events.py` is too slow to use. `l2png.py`: Layer 2 dumps
  as false-colour PNGs.

The dumps compare memory, not the picture: a wrong scroll split, palette or
hardware sprite passes them.

## Checks of the no-msx 128K build against 1.0

`native/`: `allow_dissolve.py` and `allow_dissolve_shots.py` (the
differences `spec/screen_lockstep.py` is told to allow, through `ALLOW`),
`census_gfx.py`, `census_report.py`, `native_check.py`, `set_check.py` and
`msx_shots.py`.

## Measurements

* `perfprofile.py`, `scrollbench.py` (0.109): speed and smoothness of a
  build over stages 1-2 (screens, ticks per screen, motion evenness, input
  lag); a scroll tick's cost against an ordinary tick's, routine by routine.
* `measure/`: the MSX against the Spectrum. `msx50.py` (the MSX at 50 Hz,
  BIOS time charged), `specrun.py` (a Spectrum build, same play), `lag2.py`
  (Spectrum input lag), `msx_lag3.py` (the MSX's, measured the same way),
  `msx_loop.py` (the MSX through the whole first loop with every weapon;
  compare `perfprofile.py` with `NEM_ALL=1 LOOP=1 NOPRESS=1`).
  `INDEX-0.100.txt` lists the measurements of 0.95 to 0.100, with the data
  behind section 6.8 of the technical description in `data/`.
* `measure/feel/` (1.1.1 to 1.1.3; README there): how fast the game feels
  per displayed frame on the MSX, the 128K and the Next.
* `measure/prof/` (1.2; README there): an exact profile of the 128K build,
  every instruction's T-states by address and page.
* The loose scripts at the top of this folder (`winprof*.py`,
  `convcensus*.py`, `lineprof.py`, `fitprof.py`, `st8*.py` and the rest) are
  profilers and censuses from 0.9x and 1.0, kept as they were used. Some
  have no notes beyond their code.
* `natural.py` and `natural_win.py` made the website's screenshots;
  `shoot.py` takes a screenshot a second.

## Artwork

* `pool/` (the Next's character pool). `make_pool.py`, run once, made the
  pool (`spec/nxgfx/pool.bin`, `maps.bin`) the committed artwork and cut the
  stage files down; `nx_pack_v1.py` and `nx_art_v1.py` are the packer and
  the drawings it was made from. Running it again would start the
  characters over. `make_bonus.py`, run once, put the bonus stages (9-12)
  in; it refuses to run again over its own output.
* `pool/put_blocks.py STAGE MODULE.py` writes blocks into the pool and
  points the stage's map at them. MODULE gives `BLOCKS`, {(third,
  character): 64 pixel values}, and optionally `PALETTE`, the stage's
  scenery palette D1-DF. This is how the Next's scenery is changed.
* `pool/art/`: the modules applied that way and kept. `st2_caps_blank.py`
  (stage 2's end caps), `turrets_ours.py` (our turrets in stages 3, 5, 7 and
  8, worked out from `nem.rom`), `st5_scenery.py` (stage 5's bones
  reshaded), `st6_robots.py`, `st7_belts.py`, `st8_brain.py` (which also
  gave `spec/nx_st8.py`, the electricity's sprites) and the `hatch_light`
  modules; each `*_make.py` made the module beside it, and its docstring
  says how. `st5_scenery_make.py` and `st7_belts_make.py` read screens
  sampled in a run through the stage (`st5_screens.z`, `st7_screens.z`).
  Those two files record Konami's stage layouts and are not in the
  repository: sample the screens again to run either script.
* `arcade/`: the Next's redrawn sprite enemies. `gen_art.py OUT` remakes
  `spec/nx_art.py` from the arcade's sprite sheets (not in the repository;
  `ARCADE_DIR` names the folder they are unpacked in) and `nem.rom`.
  `final_base.py` and `final.py` hold the cutting and colouring;
  `orig_sprites.py` reads Konami's original sprites from the ROM.
  `vv_model.py` is the head-on model of the Vic Viper and `vv_zoom_make.py`
  makes `spec/nx_vvzoom.py`, the ending's zoom, from it; `bigcore_make.py`
  makes `spec/nx_bigcore.py`, the Big Core, from the arcade's bosses sheet.
* `art/moai_121/` (1.2.1; README there): how the 128K's stage 3 tiles
  (`spec/stage3_tiles.txt`) were made.
* `msx2/`: `msx2_extract.py IPS OUTDIR` remakes `spec/nxgfx/` from the MSX2
  patch's IPS as it was first made (with `msx2_ranges.txt`, the address
  ranges it compares). The files have changed since, so a remake starts
  them over.
