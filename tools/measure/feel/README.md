# feel: how fast the game feels per displayed frame (10 November 2026)

The results are summarised in the development notes (1.1.2, 1.1.3).  The
scripts find the repository from their own place (or from `NEM_ROOT`);
their outputs went to a folder `night2` beside the repository
(`NEM_SCRATCH` names the folder that holds it).

* msx_feel.py MAX_SECONDS OUT: the MSX in the simulator, first loop.
* pp_feel.py SNA SYM SECONDS OUT.json (NEM_ALL=1 LOOP=1): the 128K,
  perfprofile.py with a per-frame timeline.
* nx_feel.py NEX OUT PORT MAX_FRAMES (SPECDIR for another tree's syms,
  DELAY to shift the start): the Next in ZEsarUX through ZRCP. Checks the
  code at nx_frame's address on each stop: Konami's code in other banks
  runs at that address too (stage 8), which first gave a false slowdown.
  ZRCP needs TCP_QUICKACK on the client or each command takes about 45 ms.
* feel_an.py: the analysis of the three timelines.
* cheatdiff.py: the RAM effect of Konami's all-weapons cheat, from the
  simulator (used by nx_feel.py).
* s8cmp.py: stage 8's ticks a second, run against run.

Added later on 10 November:

* pp_cat.py: pp_feel.py with the PC sampled every 300 T-states and each
  slice put in a category (Konami, sprites, cells, stars, tracking, paging,
  ...); cat_an.py: where a tick's time goes, loop and busiest quarter.
* cellcause.py: cells redrawn per picture by cause (map changes, sprite
  erasure) and sprite boxes against the cells their pixels touch.
* pp_cspr.py, cspr_an.py, cspr_cmp.py: compiled sprites in the simulator
  (code generated at a stop on each sprite and put over the ROM at 2000h),
  and comparisons of runs with the slow seconds; cspr.diff: the simulator
  build's change. cspr_gen.py, cspr_real.diff, cspr_check.py: the real
  build (ship's level frame and the round bullet in fixed memory, V1.1.1C),
  not kept.
* trim.diff, trim_check.py: the trimmed sprite boxes as first tried (the
  change that went into 1.1.2, before its `.cols` fix), and the checker
  (it watches draw_sprite16's entry only, so it missed spr_edge's path).

1.1.3 (10 November):
* lagbreak2.py: the 128K's input lag press by press (to the tick that reads
  it, to the pacing decision, the wait for the previous screen, drawing,
  to shown). pp_feel.py takes LAG_EVERY (frames between presses).
* flipprobe.py, partprobe.py, sprprobe.py: the Next in ZEsarUX through ZRCP
  breakpoints with get-tstates: ticks, drawing time, flips; the drawing's
  parts; lo_sprites' parts. keylog.py: the character enemies' pattern keys
  (for the cache sizing). cachecheck.py: the 1.1.3 pattern cache checked
  (each hit forced to remake, compared; the one-a-picture safety net).
* farcount.py: Konami's far calls on the 128K by target, switching or not.
