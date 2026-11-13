# prof: an exact profile of the 128K build (11 November 2026)

The results are summarised in the development notes (1.2).  The scripts
find the repository from their own place (or from `NEM_ROOT`) and import
each other from their own folder, so they run where they are.

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
* prof.py, an.py, lines.py: the first versions, for a window of frames.
* stagecmp.py A.pkl B.pkl STAGE [N]: two profiles, one stage (0: the whole
  loop in play): T-states a tick by function, the biggest changes first.
  The two runs do not play the same game tick for tick (keys by the clock,
  random numbers from R), so a stage's figures carry a difference in play.
* persec.py SNA SYM (NEM_ALL=1): ticks in each second of play over the loop:
  the slow end, the median, and how many seconds run above 30, 33 and 40.
* an2.py and stagecmp.py stop at the end of the first loop: prof2.py runs to
  frame 80,000, which is into the second loop once a build is quick enough.

A wart: labels.py gives a platform label at C000 or above to every page, so
Konami code in a paged bank that no call names can come out under a platform
label of another page (the turret loop at 3:B42E showed as
nlb_st2_tiles_end, under "loads", in the 1.1.3 profile).
