# prof: an exact profile of the 128K build (11 November 2026)

The results are summarised in the development notes (1.2).  The scripts
find the repository from their own place (or from `NEM_ROOT`).  They were
written in a folder `work` beside the repository and import each other from
there: copy them to it before running them (`NEM_SCRATCH` names the folder
that holds `work`, by default the one the repository is in).

SkoolKit's C simulator calls a Python function for every instruction when
`trace` is given one (about 220 frames a second with it, 4,600 without), so
the profile is exact: every instruction's T-states by address and page.

* prof2.py SNA SYM FRAMES OUT.pkl (NEM_ALL=1): the whole run.  Per address:
  T-states and executions; per second of play: T-states by function, ticks,
  pictures.  The first loop takes about 6 minutes.  prof3.py: the same with
  SIM=plain (SkoolKit's uncontended simulator, emu_nc.py) and STOPSTAGE /
  STOPAFTER, for the cost of memory contention by function (cmp.py A B).
* labels.py: an address and page to a function (platform labels; Konami's
  code grouped by call targets) and a category.
* an2.py OUT.pkl: by category and function, per tick: the loop, the busiest
  quarter of seconds, each stage.
* lines2.py OUT.pkl FROM TO [page] [per-label] [min]: one routine,
  instruction by instruction (executions and T-states per tick or picture).
* sites.py OUT.pkl ROUTINE...: who calls a routine, how often.
* hot0.py: Konami's bank 0 code by time per byte (what is worth moving out
  of contended memory).
* sprcensus.py spr|cell FRAMES: every sprite drawn (rows with pixels,
  columns, shift) or every cell drawn (blank or not), by stage.
* static.py FRAMES: sprites unchanged from the same screen's last picture.
* prof.py, an.py, lines.py: the first versions, for a window of frames.
* stagecmp.py A.pkl B.pkl STAGE [N]: two profiles, one stage (0: the whole
  loop in play): T-states a tick by function, the biggest changes first.
  The two runs do not play the same game tick for tick (keys by the clock,
  random numbers from R), so a stage's figures carry a difference in play.
* dissolve.py SNA SYM SECS (NEM_ALL=1, NEM_SPEC for the build's emu.py):
  each dissolve's length, first dz_chunk to last.
* nxdiff.py SPEC OUT.nex: the Next build against the 1.1.3N reference in
  `work/ref113n` beside the repository: symbols moved or gone, the holes left by NX_AT,
  and whether the snapshot, nx_low.bin, nx_tur.bin, nx_gfx.dat and the .nex
  differ anywhere outside the holes.
* chunks0.py OUT.pkl [BYTES]: Konami's bank 0 code as runs of instructions
  that end in a ret or a jump (what gen.py's HOT_CLONES can copy), by time
  per byte, and how much of bank 0's time a budget of bytes takes.
* persec.py SNA SYM (NEM_ALL=1): ticks in each second of play over the loop:
  the slow end, the median, and how many seconds run above 30, 33 and 40.
* feelcmp.py NAME JSON [NAME JSON ...]: pp_feel.py results side by side, by
  game stage and over the loop.
* blankcheck.py SNA SYM (NEM_ALL=1): every time draw_cells takes its
  blank-cell path, character 0 of that third must be eight zero rows.
* pausetest.py SNA SYM: H pressed in play and again 400 frames later: the
  scroll must stop and go on (the pause routine is one of the hot copies).
* an2.py and stagecmp.py stop at the end of the first loop: prof2.py runs to
  frame 80,000, which is into the second loop once a build is quick enough.

A wart: labels.py gives a platform label at C000 or above to every page, so
Konami code in a paged bank that no call names can come out under a platform
label of another page (the turret loop at 3:B42E showed as
nlb_st2_tiles_end, under "loads", in the 1.1.3 profile).
