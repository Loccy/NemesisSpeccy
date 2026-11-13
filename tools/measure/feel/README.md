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

pp_feel.py takes LAG_EVERY (frames between presses) to measure input lag as
it goes.
