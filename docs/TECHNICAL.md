# Nemesis for the ZX Spectrum 128K: technical description

Version 1.2.1 (12 November 2026). 

## 1. What it is

A port of Konami's MSX cartridge Nemesis (RC-742, 1986) to the standard
128K Spectrum, running Konami's own game code.  The project's background,
its departures from the MSX original and how to play it are in the
[README](../README.md); this document describes how the port works.

The Z80 code of the cartridge is relocated to the Spectrum's memory by a
generator (`reloc/gen.py`), and a platform layer (`spec/`) stands in for
the hardware the code talks to: the memory mapper, the BIOS routines it calls,
the video chip (TMS9918), the sound chip (AY-3-8910, the same family as the
128K's) and the keyboard and joystick.  Konami's graphics are converted to
Spectrum tiles when the game is built, and each of Konami's graphics loads is
replaced by a load of the converted set (6.6, 6.11).

The game logic is Konami's, unchanged except where it meets the hardware.
A test build matches the MSX original byte for byte in Konami's RAM, tick by
tick, and its screens match those of 1.0, which converted the graphics as it
ran, apart from one intended difference (section 4).

## 2. Controls

| Action | Keys | Joystick |
|---|---|---|
| Move | Q A O P, or 9 8 6 7 | Kempston, or Sinclair (keys 6-0) |
| Fire | SPACE or 0 | fire |
| Select power-up | M, or hold fire | second fire button, or hold fire |
| Pause | H (MSX F1) | |
| Continue at game over | C (MSX F5), while the game-over tune plays | |

1 or 2 players is chosen on the title with the movement keys and started
with fire.  A Kempston joystick is detected at power-up (section 6.9).
Holding fire for about half a second (12 ticks; `NEM_HOLD` at build time)
selects the power-up too, once per hold, for one-button joysticks; Konami's
own repeat shot while fire is held is unchanged.

## 3. Building

The build has four stages, all driven by `build.py`:

1. **Relocation.**  `reloc/gen.py` reads the cartridge ROM and an annotated
   disassembly of it, and writes Konami's code back out as assembly source
   with every address symbolic, laid out for the Spectrum's memory
   (`konami_spec.asm`, plus `konami_spec_stubs.asm` for calls between
   memory banks and, for the 128K, `konami_spec_hot.asm` for the copies of
   hot routines).  Section 6.1 explains why and how.
2. **Generated tables.**  `tables.py` writes the sprite inks, the border
   colours, the keyboard decoder and the unpacker's input buffer
   (`tables.asm`); `gen_fullcmp.py` writes an unrolled comparison routine
   (`fullcmp_gen.asm`, 6.4).
3. **The graphics.**  `native_pack.py` makes the converted graphics of every
   load event (6.6, 6.11): `native_sets.py` replays each of Konami's
   graphics loads from the ROM in the MSX simulator (4.6) and converts every
   character it writes with `tilemodel.py`; `native_pack.py` packs each
   piece with ZX0 and places the pieces in the free room of the switched
   banks (5), with a search (largest first, best fit, backtracking).  It
   writes `native_data.asm`, `native_tables.asm` and the packed pieces in
   `native/`.  `build.py` runs it (about 15 seconds) only when one of its
   inputs (the scripts it uses, `native_moai.txt`, `msxsim.py`, the ROM) is
   newer than what it last wrote.  These files are Konami's graphics,
   converted, so like the relocated code they are generated and kept out of
   the repository (`.gitignore`).
4. **Assembly.**  sjasmplus assembles `plat_spec.asm`, the platform layer,
   which includes all of the above and the rest of the port's own code, into
   a 128K snapshot (`nemesis.sna`).  `build.py` then sets the snapshot's
   stack pointer to AEA0: sjasmplus leaves it at 6000, directly above
   Konami code at 5FFE-5FFF, which a loader that starts the snapshot through
   its stack (some hardware loaders may) would overwrite.  AD00-AE9F is zero
   at load and rebuilt by the boot code, which sets SP to AEA0 itself.

`make_tap.py` then turns the snapshot into a tape (6.13).

Requirements: Python 3, sjasmplus (1.21 used), SkoolKit (10.1 used: the
MSX simulator, which the graphics conversion uses, runs on its Z80
simulator, as do the simulator-based checks and the tape check), Pillow
(imported by the colour fit's model, and for screenshots), gcc (to build
the ZX0 compressor).  The scripts find the tree from their own
location (`spec/`, `reloc/` and `msxsim/` side by side under one
root); `NEM_ROOT` overrides it.  Inputs not in the package, relative to
that root:

* the cartridge ROM as `nem.rom` (SHA-256
  `3210f8a0f2309dd4b9a89fc2b24d0f178ce4393a0a1f2854fbce545c361261bc`, the
  dump the disassembly is checked against; `build.py` stops if the ROM or the
  disassembly is missing, or the ROM does not match);
* antxiko's annotated disassembly
  (https://github.com/antxiko/Nemesis-disassembly) in
  `ref/Nemesis-disassembly`, which `reloc/gen.py` parses, pinned to commit
  3e486bc2f39c65eb97a944cda246f85fd30218ec: `build.py` checks the SHA-256 of
  the files it reads (`src/nemesis_p00.asm` to `nemesis_p15.asm`) and stops
  if they differ, unless `NEM_ANY_DISASM=1`;
* the ZX0 compressor (https://github.com/einar-saukas/ZX0), built with
  `gcc -O2 -o zx0 zx0.c optimize.c compress.c memory.c` in its `src`
  directory, on the PATH as `zx0` or named by the environment variable
  `ZX0` (`native_pack.py` and `make_tap.py` use it).

```
python3 build.py              # nemesis.sna (+ .sym, .lst), the release build
python3 make_tap.py           # nemesis.tap from nemesis.sna
sh release.sh 1.2.1           # the release, tape, snapshot and .nex, in release/
NEM_PIN_R=1 python3 build.py  # nemesis_test.sna, the test build (section 4)
```

Build options (environment variables):

| Variable | Effect |
|---|---|
| `NEM_PIN_R=1` | The test build used by the lockstep (4.3): Konami's randomness from a fixed sequence, sound run once per tick. |
| `NEM_DRAW_EVERY=n` | Draw one tick in n (default 2, the fast edition; 0: the `NEM_EXTRA` scheme, the smooth edition; 6.8). |
| `NEM_FPT=n` | A tick takes at least n frames (default 1, as on the MSX; 2 before 0.99). |
| `NEM_FLIP=n` | With one tick in N drawn: screens at least n frames apart (default 3). |
| `NEM_EXTRA=n` | One undrawn tick after every n drawn (with `NEM_DRAW_EVERY` 0 or unset; default 4; 0 draws every tick). |
| `NEM_PACE=palmix` | Experimental 2,2,2,2,1 frame pacing. |
| `NEM_PACE=25` (`nxbuild.sh`) | The Next build at the earlier pacing, about 26.7 ticks a second instead of 30 (9.2). |
| `NEM_TAP_RAW=1` | (make_tap.py) an uncompressed tape. |
| `NEM_ANY_DISASM=1` | Build from a disassembly other than the pinned version. |
| `NEM_HOT=0` | The 128K build without the copies of hot routines in uncontended memory (6.1); `NEM_HOT=paged` for those of the switched banks alone. |
| `NEM_TRIM=0` | Sprites colour and mark their whole boxes, as in 1.1.1 and before (6.7). |
| `NEM_NEXT=1` | The Spectrum Next build (`nxbuild.sh` sets it): assembles with `NEXT` defined, writes `nemesis_next.sna`, and the title's letter is N (section 9). |

The version is kept in the file `VERSION`; `build.py` puts it at the top
right of the title screen, followed by A (adaptive, the default since
0.110), F (fast), S (smooth) or N (the Spectrum Next build), as
`version.inc` for `ctl_text`.  `release.sh` refuses a version that does not
match the file.

## 4. Checking

### 4.1 The problem

The port runs Konami's code, but not as Konami shipped it: every routine has
been moved to a new address, thousands of address references have been
rewritten, the hardware the code talks to has been replaced, and some
routines have been patched or reimplemented natively for speed.  Any one of
those changes can go wrong in a way that only shows twenty minutes into the
game (a boss's shots starting from the wrong place, a stage that crashes when
a particular enemy appears).  Playing the game catches some of this; it
cannot catch all of it, and it cannot say where a fault came from.

So the main check is mechanical: run the original and the port side by side
and compare them.

### 4.2 The lockstep

`lockstep_spec.py` runs two machines at once, each in a simulator (4.6):

* the **MSX original**: the untouched cartridge ROM in a minimal simulated
  MSX;
* the **Spectrum port**: the *test build* (`NEM_PIN_R=1`, below) in a
  simulated 128K.

The unit of comparison is the game *tick*: one pass of Konami's per-frame
routine (move everything, check collisions, update the screen buffers),
which the original runs every second video frame.  The lockstep advances
each machine by exactly one tick, gives both the same input for that tick,
and then compares their state.  If they differ, it stops and reports the
first tick and the bytes that differ.  If they never differ, the port did
exactly what the original did, tick after tick, for the whole run.

What is compared after every tick:

* **Konami's RAM** (MSX E000-F0FF; on the Spectrum the same 4,352 bytes,
  moved to AF00).  This is the whole game state: object positions, scores, the map
  buffer, timers, the sound driver's state.  Only the stack area is left
  out.
* **The name table.**  The Spectrum has no TMS9918, so the port keeps a
  copy ("shadow") of the name table (which character is in each cell),
  `name_shadow`, which is compared with the MSX's real video memory.  The
  port keeps no copies of the pattern, colour and sprite pattern tables:
  its graphics come converted, with its own loads (6.11).  So the lockstep
  compares the names only (it recognises such a build by its symbol
  `nl_count`), and the graphics are checked against 1.0 by the screen
  lockstep (4.7).

Two kinds of difference are expected and allowed.  The first is a byte
pair holding an *address*.  The port's code lives at different addresses,
so a pointer the game stores in RAM (to a routine, a table, a script)
legitimately differs.
The lockstep knows where everything moved (from the build's symbol
table) and accepts a difference when the two values are the same address
in each machine's layout.

The other is scratch RAM of Konami's loaders.  The port's loads and its
dissolve (6.6, 6.11) do not run Konami's loader code, whose scratch RAM
(E101-E102, the mirroring buffers at E300-E3FF and E700-E7FF, the
dissolve's chunk buffer EA00-EBFF) the game never reads before writing it
again (shown by the census of the original's graphics writes, 6.11).  A
byte there may differ from the MSX after a tick in which the port made a
load or a dissolve chunk (`nl_count` changed), and the difference is
allowed for as long as the MSX's value stays what it was then.  Anything
else is a mismatch.

### 4.3 Making the two machines comparable

Two real machines given the same input would still drift apart, for reasons
that have nothing to do with the port being wrong.  The lockstep removes
them:

* **Randomness.**  Konami's code takes random numbers from the Z80's R
  register, which depends on exactly how many instructions have run.  The
  port runs more instructions (paging, far calls), so the numbers would
  differ.  The *test build* replaces each `ld a,r` (22 sites, `LD_A_R` in
  `gen.py`) with a read from a fixed sequence, and the MSX simulator uses
  the same sequence.
* **Timing.**  On the MSX the tick runs in the frame interrupt; on the
  Spectrum it runs in the main loop while drawing happens around it (6.3).
  The lockstep ignores real time: it gives the MSX one interrupt per tick,
  only when the game is idle, and steps the Spectrum to the end of each
  tick.  The sound driver, which on both machines runs on its own rhythm,
  is run once per tick on both in the test build so that its state matches
  too.
* **Input.**  Both get the same scripted keys per tick (fire on a fixed
  rhythm).
* **Survival.**  The ship is made invulnerable on both (the death routine
  returns immediately), so a run goes on as long as asked rather than ending
  at the first collision.
* **The title's tune** (0.102).  The port plays Konami's tune A6 on the
  title and stops it when a game starts (6.12); Konami's title is silent.
  After each tick, if the Spectrum has requested A6 or the silence (CD) and
  the MSX has not, the MSX is given the same request through `pide_sonido`,
  so the sound records, which the lockstep compares, stay in step.

The test build is otherwise the release build: same code, same layout.

### 4.4 Reaching the whole game

A scripted ship firing on a rhythm gets through stage 1 and not much more of
interest.  `HYPER=1` makes both machines run the game's own cheat routines at
the start of play (MSX A0D8 and A110), giving every weapon, so the run
destroys what it meets and reaches every stage and boss.
`HYPER=1 lockstep_spec.py 70000` plays the whole first loop of eight stages,
the end-of-loop sequence and most of the second loop (about 47 minutes of
play).
`LASER=1` gives both the laser instead.
`HOLDFIRE=1` holds fire 20 ticks in 40 in play, so the Spectrum's
hold-to-select (6.9) presses power-up, and gives the MSX trigger B by the
same rule, as a second button would; before each press the power-up bar is
put on one of the six items on both machines, so every press takes one.
`TARGETS=1` puts the ship on every hidden target as soon as it appears, on
both machines alike, so each is touched and the bonus stages (9-12) are
played: `HYPER=1 TARGETS=1 lockstep_spec.py 36000` goes 1, 2, 9, 3, 10, 4, 11,
5, 6, 7, 12, 8 and the end of the loop.  `MORTAL_BONUS=1` as well lets the
ship die once in each bonus stage (on both machines; the life is given
back): dying in a bonus stage ends it, and the next normal stage starts from
its beginning.

The lockstep has found faults no amount of casual play would have pinned
down; for example three numbers in Konami's code that look like addresses
(a boss's shot position, two characters a boss writes into the map, the
ship's restart position after the loop) and had been "relocated" by the
generator as if they were (they are now listed in `CONST_IMM`, 6.1).

### 4.5 When they differ

The report names the tick and the differing bytes.  Two modes help find the
cause:

* `WATCH_AT=tick WATCH_ADDR=addr [WATCH_FROM=tick]` re-runs to that tick and
  reports every instruction that writes the byte, on both machines, with the
  MSX's last 40 instruction addresses and its stack.  The first divergent
  write is usually the bug, or close to it.
* `TRACE_AT=tick` shows the last instructions the Spectrum ran before
  leaving Konami's code, for crashes.

`SHOT_AT=tick SHOT=file.png` saves a screenshot of the Spectrum at a tick.

### 4.6 The simulators

Neither machine is an off-the-shelf emulator; both run on SkoolKit's Z80
simulator.

**MSX: `msxsim`** (`msxsim/msxsim.py`), a minimal MSX1 written for this
project, modelling only what Nemesis touches.  The build uses it too, to
run Konami's graphics loaders (6.6).

* the Konami cartridge mapper (8 KB banks at 6000, 8000 and A000; bank 0
  fixed at 4000), with no SCC;
* the TMS9918 as a port model: VRAM, registers, the address latch and the
  frame flag.  There is no display timing and no sprite limit or collision
  flag.  `msxsim/screen.py` renders VRAM to a PNG;
* no BIOS ROM: the 13 entry points Nemesis calls (RDSLT, ENASLT, WRTVDP,
  WRTVRM, SETWRT, FILVRM, LDIRMV, LDIRVM, WRTPSG, RDPSG, RSLREG, RDVDP,
  SNSMAT) are Python stubs.  RST 20h and the interrupt handler at 0038 run
  as real Z80; executing anything else below 4000 is an error;
* PSG register writes are recorded, not played;
* 60 Hz frames of 59,736 T-states with an approximation of the MSX's
  instruction-fetch wait state (not used by the lockstep, 4.3).

**Spectrum: SkoolKit 10.1's 128K simulator** (its C-accelerated simulator
with I/O), driven by `emu.py`: 128K paging, memory contention, AY register
writes (recorded, not played), keyboard input through its tracer, and
frames of 70,908 T-states with an interrupt at the start of each.
Screenshots are taken from whichever screen port 7FFD shows; there is no
beam-accurate display.  `tap2sna.py` simulates tape loading at signal level.

What neither covers, and so needs a full emulator or real hardware:

* display timing (tearing, flicker, anything raced against the beam);
* sound: the music has only been checked as register writes;
* the floating bus: SkoolKit returns 0xFF from unattached ports, the case
  the Kempston detection relies on, and real machines vary;
* the machines themselves: the game has run on a real 128K and a real +3
  (the +2A is the same machine without the disk drive), loaded as a tape
  from an SD card interface, and on a real 128K loaded as audio from a tape
  player stand-in with nothing else attached, which also confirmed the
  Kempston detection with no interface present.

### 4.7 What the lockstep cannot see, and the checks for it

The lockstep proves the game state is right.  It cannot prove the picture
is: the conversion of Konami's graphics and the drawing (turning the game's
character map and sprites into Spectrum pixels and attributes) are the
port's own and have no MSX counterpart to compare with.  They are checked
in two ways: the whole picture against 1.0's, and the parts against models.

**The screen lockstep** (`screen_lockstep.py`) runs two Spectrum test
builds, a reference (`REF`, a snapshot with its `.sym` beside it) and a
candidate (`CAND`, by default this tree's `nemesis_test.sna`), side by side
with the MSX original, all three given the same input, tick by tick.  Each
build's Konami RAM is compared with the MSX's as in 4.2, so both play
exactly the original's game, and both Spectrum screens of the candidate
(banks 5 and 7, pixels and attributes) are compared with the reference's
at the end of every tick.  Both are built as test builds that draw every
tick (`NEM_PIN_R=1 NEM_EXTRA=0`).  A tick whose differing cells all show
the same colours (an ink with no pixels set, bright black) is counted apart
and does not stop the run.  Options: `HYPER=1`, `TARGETS=1` (as in 4.4),
`DEATHS=1` (the ship dies once in each stage, `DEATH_AT` ticks into it,
default 900, and the life is given back), `GAMEOVER=1` (the lives are not
given back, so the run goes through game over, the title and a new game),
`ALLOW=file.py` (a function `allow(tick, msx_ram, ref, cand)` that skips
the comparison at ticks where a difference is intended), `KEEP_GOING=1`
(count the differences and go on) and `SHOTS=dir` (both screens and a map of
the differing cells saved as PNGs).

With 1.0's test build as the reference, the native build's screens are
identical to 1.0's on every tick of: the route through every hidden target
(`HYPER=1 TARGETS=1`, 40,000 ticks: stages 1-2-9-3-10-4-11-5-6-7-12-8, the
ending, into the second loop), with the first three ticks of the dissolve
allowed (6.6; `local/tools/native/allow_dissolve.py` in the linked clone);
a death in each stage (`HYPER=1 DEATHS=1`, 50,000 ticks), apart from 88
ticks in stage 3 after the restart, all of them the intended difference of
6.6 (the Moai); and game over five times (`GAMEOVER=1 DEATH_AT=300`, 20,000
ticks).  Konami's RAM matched the MSX's throughout.

**The models**, on the release build in the Spectrum simulator:

| Tool | Checks |
|---|---|
| `check_names.py 240` | Map tracking (6.4): after every tick the port's copy of the screen's character map equals Konami's map buffer, apart from regions still queued for comparison. |
| `check_screen.py 120 0 2` | After the cells are drawn, every cell of the hidden screen equals its character in the tile set. |
| `check_sprites.py 60 0 3` | After the sprites, the hidden screen equals the tiles plus Konami's sprites ORed in, with the sprite cells coloured by the rules of 6.7.  With `MISSILE=1` the ship has the missile and fires along the ground, for the missile's rule.  With `EDGE=1`, sprites crossing both edges (and just inside them) are added to Konami's list for each checked drawing, at every pixel position in turn, and taken out again. |
| `test_keys.py` | Keyboard decoding against the key map. |
| `test_kempston.py` | Kempston detection (both buttons), its decoding, and hold-to-select. |
| `test_tape_trap.py` | The tape loaded as a DivMMC-type interface loads it from its card (LD-BYTES trapped at 0562). |

With `NEM_ALL=1` the checkers (and `emu.py`) play the whole game instead of
the start of stage 1: the ship is invulnerable and, once play starts, the
game's own HYPER cheat and a second option are called, as the lockstep's
`HYPER=1` does.  `NEM_ALL=1 check_screen.py 3000 0 4` and the like then
cover every stage and boss on the release build.  With `NEM_TARGETS=1` as
well, the ship is put on every hidden target, so the bonus stages are
played, and `NEM_MORTAL_BONUS=1` lets the ship die once in each bonus
stage.  The renderer (`render.asm`) has not changed since 1.0, whose
checkers passed over such runs of the whole first loop and more (the
development notes have the figures); for 0.93 (sprites clipped at the
edges) `check_sprites` passed over 1,500 seconds of such a run, every tick
(2,382 sprites crossing an edge), and with `EDGE=1` over 240 seconds with
all weapons (3,363 edge sprites), 60 with the missile and 30 of ordinary
play.

The build checks some of its own assumptions: `native_pack.py` stops if
sprite patterns 0-39 are not the same after every stage's load, or if a
star character does not convert to its own pixel row in one attribute for
every position of the pixel (6.5).

Two blind spots, both learnt from the red stars of 0.97-0.99 (development
notes, 0.99a).  Code that exists only in release builds (the twinkle skipped
on undrawn ticks with a fixed one-in-N scheme, 6.5) is never run by either
lockstep, which use test builds.  And `check_screen` compares the screen
with the port's own tile set, so a wrong tile in the set passes it; the
screen lockstep catches that only by comparison with 1.0, so a tile 1.0
also had wrong passes both.  `check_route.py` counts the star tiles'
attributes by stage for that reason.  Also, when checking by screenshot:
the screen on display can be a tick or two behind Konami's sprite list, so
identify what is shown from the screen's own pixels.

The tape is checked separately: `tap2sna.py -c machine=128 -s <plat_boot>
nemesis.tap out.z80` simulates loading the whole tape at signal level, and
the resulting memory must match `nemesis.sna` byte for byte outside the
screens.

### 4.8 Running the checks

`./verify.sh` runs the model checks of 4.7 (`check_names`, `check_screen`,
`check_sprites` with and without `MISSILE=1`, `test_keys`,
`test_kempston`), builds the test build and runs a 3,000-tick lockstep
(`LOCK_TICKS` for another length), and finally builds the Spectrum Next's
`.nex` (`nxbuild.sh`, section 9), to show that it still assembles; run it
after any change.  The screen lockstep is not part of it: it needs a
reference build and long runs, so run it (the routes of 4.7) after any
change that could alter what is drawn.

How far a checker run gets (1.0's figures): in the all-stages mode with
every target touched (`NEM_ALL=1 NEM_TARGETS=1`), 600 seconds of play
reached stages 1-3 and the bonus stages 9-10; the fast edition reached
stage 8 at about 1,480 seconds and the second loop at 1,700, and 3,000
seconds took it to the second loop's stage 7 (the smooth edition about 14%
behind).  `check_route.py SECONDS OUT.json` times the route stage by stage,
counts the star tiles' attributes by stage, and measures the stack's
deepest use (a marker below Konami's stack, BF80-BFEF) and the IM2 table's
state.  Run the `HYPER=1` lockstep after changes that could affect later
stages (the generator's tables, memory layout, paging).

Other tools:

* `bench.py [TICKS] [skip]`: a deterministic speed benchmark (the test
  build with the lockstep's input, so two builds play the same game):
  logic and drawing T-states per tick and a pacing model.  It assumes a
  draw every tick, so compare builds made with `NEM_EXTRA=0`.
  `benchprof.py` profiles the same workload.
* `census.py none|hyper|double TICKS OUT.json` and `census_check.py`: run
  the MSX original alone, list every instruction that writes Konami's map
  buffer, and report any writer the port's map tracking does not cover
  (6.4).
* `bankreads.py`: which bytes of each MSX data bank the game reads.
* `native_sets.py OUT.pkl`: every load event's converted set, saved, with
  the size of each event's data packed.
* `pacing.py`, `breakdown.py`, `fncost.py`, `sample_prof.py`, `callers.py`:
  timing and profiling in the Spectrum simulator.
* `emu.py SECONDS [png_every] [prefix]`: run the build with scripted keys
  and save screenshots.

## 5. Memory

The 128K Spectrum has 48 KB of memory always visible at 4000-FFFF, but the
top 16 KB (C000-FFFF) is a window: any one of eight 16 KB banks can be
switched into it through port 7FFD.  Two of the banks hold screens (bank 5,
which is also fixed at 4000, and bank 7), and the same port chooses which
of the two is displayed.

The MSX cartridge is 128 KB in sixteen 8 KB banks, which the game switches
into 8 KB windows at 6000, 8000 and A000.  It does not all fit in the
Spectrum's fixed memory, so the port has to decide what lives where.  The
rules that shaped the layout:

* Code that runs every tick, and the platform's own drawing code, should be
  in fixed memory (5B00-BFFF), because switching banks costs time and the
  code that switches must itself be in fixed memory.
* Konami's code is about 40 KB.  Bank 0 (the cartridge's always-present
  bank) goes in fixed memory; the rest goes in switched banks, grouped so
  that code which calls itself a lot shares a bank.
* The port's drawing needs memory of its own: the tile set (every
  character, converted), the sprite patterns and the second screen.  The
  converted graphics of every load, packed, need room in the switched banks
  too.

Fixed memory:

```
4000-5AFF  screen 0 (bank 5)
5B00-760A  MSX bank 0 code, relocated (less the loaders the port leaves
           out, 6.11)
760B-7AE2  the graphics loads, their unpacker and the dissolve
           (native.asm), and the table of the packed pieces
           (native_tables.asm)
7B40-7BF2  sprites crossing the left and right edges (spr_edge, edge_pat)
7C00-7C57  data moved out of page A (MSX 1:7EE6, 88 bytes)
7C60-7E98  rarely run code (contended memory): BIOS stand-ins, keyboard,
           boot, the title text writer, Kempston, hold-to-select
8000-A60B  platform: paging, mapper emulation, the name table and sprite
           stand-ins, map tracking, interrupt, main loop, the tile set's
           bookkeeping and the star twinkle, renderer, the unpacker's
           input buffer (nl_buf, 9200-92FF), tables, far-call stubs, the
           ship's patterns, buffers (name_shadow, dirty bitmaps, region
           lists, star lists, DRAWN), the sprite patterns' extents (sp_ext)
A60C-ABEC  copies of Konami's hot routines (6.1, 1,391 bytes), then the
           adaptive pacing (pace_adapt) and stage 3's ring colour (st3_rings)
AD00-AE00  IM2 vector table; AEAE jp isr; stack below AEA0
AF00-BFFF  Konami's RAM (MSX E000-F0FF, displaced by -0x3100)
```

Banks switched in at C000 (the port's names for them in brackets):

```
A  bank 0  MSX banks 1 and 2 (game code) C000-FEDD
B  bank 3  packed graphics C000-F0D3 and F2E3-FFC3; MSX bank 5's object
           shapes (91D1-92E2) F1D1-F2E2
C  bank 4  MSX bank 3 (game code) C000-E061; the title's text E062-E0C6;
           packed graphics E0C7-E7FC and E800-FFED
D  bank 6  MSX banks 7 and 8 (sound driver and tunes, E000-E3DC); the
           full map comparison E400-E64D; packed graphics E680-E795; the
           work area a patch is unpacked into (6.11) E800-FBFF; packed
           graphics FC00-FFF3
E  bank 1  MSX bank 11 C000-DFFF; bank 12 A000-A2A7 (the scripts of stages
           1-8) E000-E2A7; at one displacement, bank 9's title panels
           (9B3F-9C56) E2A8-E3BF and bank 10's A000-A0DA E769-E843 and
           AAA6-AF28 F20F-F691; code moved from bank 2 (8290-839E, the
           boss pieces) FB04-FC12; bank 12's parts for the bonus stages:
           the scripts of stages 9 and 11 EEC1-F100, of stages 12 and 10
           F692-F9F1, and the bonus stages' ending table and records
           (B2E4-B64B) FC13-FF7A; packed graphics in the gaps (E3C0-E64C,
           E844-EEB5)
7  bank 7  screen 1 C000-DAFF; the tile set DB00-F5FF; star_check,
           spr_pmap, attrs_keep F600-F733; sprite patterns F800-FFFF
```

The packed graphics are 28 pieces, 27,362 bytes in all (6.11), in the room
that the MSX's graphics, the copies of its video memory and 1.0's colour
fit left.  `native_pack.py` places them (3), so their addresses above are
those of the current build and move when a piece changes;
`native_data.asm` asserts that the pieces of each region end within it,
and that the code before them in pages C and D ends by E0C7 and E680, and
in page A by FEE8.  Those limits hold for the test build too, whose Konami
code is longer (the fixed sequence that stands in for R costs a byte at
each read: 7 in MSX bank 3, 10 in banks 1 and 2).  Page A's region
therefore starts 10 bytes past the game build's end (FEDE), and a test
build keeps the title's lines (`ctl_text`, 101 bytes) in fixed memory,
after the copies, so that its page C ends with MSX bank 3, at E069.  The
packer tries first-fit placements, the largest
piece first, over many orders of the regions, before its exhaustive search,
which remembers the states it has found to fail (1.2.1: with the room tight,
the search alone ran for more than a quarter of an hour).

Only what the game reads is carried from the data banks, and every range
left out is identified.  Konami's graphics reach the game converted, in
the packed pieces, so bank 4 is not carried at all, bank 5 only for its
object shapes, bank 9 only for the name-table data of the title's two
panels, and bank 10 without the ending's graphics (A0DB-A757) and the
high-score table screen of the attract cycle (A758-AAA5).  Bank 12 is
carried to A2A7, and its parts for the bonus stages are placed separately
(6.1); past B64B it is padding.  Banks 6 and 13-15 are empty (all FF) and
never read.

Free space in the current build, about 3,150 bytes in all:

| Where | Bytes | |
|---|---|---|
| Fixed 8000-ACFF | 598 | ABED-ACFF (275, after the copies, the pacing and `st3_rings`), 911C-91FF (228, before `nl_buf`'s alignment), 9BC0-9BFF (64, after `spr_vis`), 9B23-9B3F (29, before `ship_pat`'s 32-byte alignment), 9CFE-9CFF (2) |
| Fixed AD00-AEFF | 93 | AEA0-AEAD (14), AEB1-AEFF (79) |
| Low fixed area | 473 | 7E99-7FFF (359), 7AE3-7B3F (93), 7BF3-7BFF (13, after `spr_edge`), 7C58-7C5F (8) |
| Bank 0 (page A) | 290 | FEDE-FFFF (a packer region from FEE8 since 1.2.1, unused in this build; it holds sjasmplus's default UDGs at FF58, which nothing uses) |
| Bank 1 (page E) | 972 | E64D-E768 (284), F9F2-FB03 (274), F101-F20E (270), FF7B-FFFF (133), EEB6-EEC0 (11) |
| Bank 3 (page B) | 313 | F0D4-F1D0 (253), FFC4-FFFF (60) |
| Bank 4 (page C) | 21 | FFEE-FFFF (18), E7FD-E7FF (3) |
| Bank 6 (page D) | 168 | E796-E7FF (106), E64E-E67F (50), FFF4-FFFF (12) |
| Bank 7 (page 7) | 237 | F734-F7FF (204), F65F-F67F (33, before `spr_pmap`'s 128-byte alignment) |

The room the packed pieces can use (`native_pack.py`'s regions) is about
1,700 bytes of that, in pieces of at most 284 bytes.  Where the pieces go
depends on their sizes, so a change to any stage's graphics can move every
piece and the free space with them.  Bank 3's padding (MSX
3:BE66-BFF4, 399 bytes, carried in bank C) could be dropped too, a
generator change.  The port's loads took Konami's loaders and the run-time
conversion out of fixed memory and left 2 KB free below the IM2 table (1.5
KB after 1.1.2).  Most of that now holds the copies of Konami's hot
routines (6.1), because 8000-BFFF is the fixed memory the 128K's video
circuit does not slow down; 302 bytes are left there.  Anything that need
not be fast still goes into a switched bank with a call from fixed code, or
takes over an existing instruction.

## 6. How it works

The MSX and the Spectrum share a CPU, so Konami's code can run on the
Spectrum unchanged in principle.  Everything around the CPU differs:

* **Memory.**  The game expects its cartridge banks in 8 KB windows and its
  RAM at E000; the Spectrum has a different map and 16 KB banks.
* **Video.**  The MSX's TMS9918 has its own 16 KB of video memory, reached
  through I/O ports.  Nemesis uses its Graphics II mode: the screen is a
  32 x 24 map of characters (the *name table*); each third of the screen has
  its own 256 character shapes (*pattern table*) and colours (*colour
  table*, two colours per 8-pixel row); and 32 hardware sprites, 16 x 16
  and one colour each, are drawn over the top by the chip.  The game only
  writes the map, the shapes and the sprite list; the chip composes the
  picture fifty or sixty times a second for free.  The Spectrum has a
  bitmap with one ink and one paper colour per 8 x 8 cell, no sprites, and
  nothing that composes anything.
* **System software.**  The game calls a dozen MSX BIOS routines (write to
  video memory, read the keyboard, write a sound register).
* **Sound and input.**  The sound chip is the same family as the 128K's AY;
  the keyboard matrix and joystick are wired differently.

So the port has two halves.  The first is Konami's code, moved to fit the
Spectrum's memory (6.1, 6.2).  The second is the platform layer, which
answers everything the code asks of the MSX hardware (6.3 onwards).  Most of
the platform is the picture: the port must do the TMS9918's job in
software, drawing the game's character map and sprites as Spectrum pixels
and colours, and doing it fast enough.  That is where nearly all the
design effort and running time goes (6.4-6.8).  The characters themselves
are converted to Spectrum tiles when the game is built, and Konami's
graphics loads are replaced by loads of the converted sets (6.6, 6.11).

### 6.1 Relocation (`reloc/gen.py`)

The cartridge's code cannot simply be copied: it would land on top of the
Spectrum's screen and system areas, and its banks do not fit the Spectrum's
bank size.  So the code is regenerated rather than copied.

`gen.py` parses an annotated disassembly of the cartridge into *items*
(instructions and runs of data), gives every item a label (`m<bank>_<addr>`,
for example `m0_4045` for bank 0, address 4045), and writes the code back out
as assembly source in which every address is one of those labels.  The
assembler then places the code wherever the port wants it, and every jump,
call and pointer follows.  Because addresses are symbolic, code can also
grow: a patch can replace a 2-byte instruction with a 3-byte call.  An
identity mode re-emits everything at the original addresses; it must
reassemble to the ROM byte for byte, which proves the parser.

The hard part is knowing which numbers are addresses.  A 16-bit value in the
code may be an address (relocate it), a number that happens to look like one
(a score, a screen position, a pair of characters: leave it), or an address
in a different bank from the one its value suggests.  `gen.py` decides from
the disassembly's annotations and from tables built up by tracing the game:

* `CODE_PTRS`, `DATA_PTRS`, `NOT_PTR_RANGES`: which words in tables are
  pointers;
* `SITE_BANK`: address constants that refer to a bank other than the default
  one for their address;
* `CONST_IMM`: values that look like addresses but are numbers (for example
  the stage 7 boss's shot position 0xA440 and the ship's restart position
  0x504A, both found by the lockstep, 4.4).

Code is grouped into sections, each assembled into one place: fixed memory
(MSX bank 0), bank A (MSX banks 1 and 2), bank C (MSX bank 3), bank D (the
sound driver) and bank E (a few routines that read bank E's data).  A call
or jump from one section to another goes through a *far stub*
(`call far_go / db bank / dw target`) that switches the target's bank in,
calls it and switches the caller's back on return.  Data banks are placed as
raw bytes, with the pointers inside them relocated; banks the game uses
together share a bank at one displacement, so pointer arithmetic inside the
data still works.  Where that will not fit, a bank's parts that are only
ever reached through their own pointers (the bonus stages' scripts, one per
stage) are placed separately (`DATA_PIECES`, with `DATA_SKIP` for ranges
left out and `DATA_ALIAS` for an operand that is a table's base declared
before the table).  A pointer just past a piece's end (where a script
pointer rests after its last row) maps to that end.  (1.0 also had to
relocate two of Konami's graphics tables with care, `graficos_por_fase` and
the per-stage table at 5:92E3; the port no longer carries either, 6.11.)
Konami's RAM moves from E000 to AF00.

The 128K build also has **copies of Konami's hot routines** in fixed memory
at 8000-BFFF (`HOT_CLONES`, written to `konami_spec_hot.asm`; 1.2).  There
are two reasons.  A small routine in a switched bank that is called across
banks many times a tick costs a bank switch there and back at every call
(about 520 T-states); in fixed memory it is a plain call from anywhere.
And Konami's bank 0 code, though fixed, sits at 5B00-760A, which the
128K's video circuit shares: while the picture is being sent the processor
is held up whenever it touches 4000-7FFF, and code there runs 20% to 31%
slower than above 8000.  The copies are five routines of banks 2 and 3
(241 bytes: one moves an object with the scroll, two save and restore what
is under the laser, the loop over the four turrets, and an enemy's unaimed
shot), and 1,146 bytes of bank 0, a sixth of it, in which the game spends
93% of the time it spends in bank 0: the dispatcher and its two adders, the
frame's call list, the sprite engine, the rectangle copy and clear, the
object loop, the map address helper and the speed and off-screen tests.
They were chosen from an exact profile of the first loop, as whole runs of
instructions that end in a `ret` or a jump.

They are copies, not moves.  Konami takes addresses relative to its code:
2:90D4 loads HL with 9262h, which is the table at 9264 less 2, and 9262 is
inside the routine before the table.  When that routine was moved, the
table's base moved with it and the lockstep stopped at stage 1's first
enemy.  So the original stays where it is, whole.  A copy has labels of its
own (`H_m<bank>_<addr>`); every call, jump and table entry that names an
instruction of a copied range goes to the copy, from whatever bank, with no
far stub; and nothing else in a copy is renamed, so an address it takes as
data is the original's.  Anything that still reaches an original (a jump
from beside it, the platform's own calls) finds it as it was.  `gen.py`
checks that each range is whole instructions and cannot run off its end.
0:4028-4059, the interrupt routine, is not copied: the checks stop at
0:4054 for the end of a tick.  The Next build has no copies.

The other tables in `gen.py` are changes to the code itself: `SPEC_PATCH`
(the hardware boundary: video writes, the map upload, the graphics loads,
the dissolve's chunks, the star twinkle, the sprite uploads, the front
end), `LEAVE_OUT` (items not carried at all: Konami's graphics loaders,
their decompressor and block routines, and their data, 6.11), `NM_SITES`
(map writers that report what they wrote, 6.4), `ITEM_PATCH`,
`ITEM_MOVES`, `CLONES`, `HOT_CLONES`, `DATA_MOVES` (single items replaced,
moved or copied),
`LD_A_R` (the randomness sites pinned in the test build, 4.3), and
`NEXT_PATCH` and `NEXT_KEEP` (the Next build's hooks, section 9).

### 6.2 Paging and the MSX mapper

The game switches cartridge banks by writing a bank number to 6000, 8000 or
A000.  In the port those writes are calls to `map_6000`, `map_8000` and
`map_a000`, which record what the game believes is mapped; `map_a000` then
calls `map_update`.  Every write to 6000 or 8000 in Konami's code is
followed, in straight-line code with no read through a window, by a write
to A000 (all 78 mapper writes were checked for 0.108), so the page is worked
out once, at that last write: about 13 mapper writes a tick in play, 5 of
them to A000.

Most of these switches need no action at all, because the code has already
been placed where it will run and the far stubs bring in the right bank.
What remains is data: when fixed code reads data through a window (tunes,
map pieces, the objects' shapes, the title's panels), `map_update` switches
in the Spectrum bank holding that data.  For bank 10 (the boss pieces' tables,
in page E with the code that reads them) it does so only when the write
comes from fixed code (the end-of-loop explosion, 0:4AFF); from paged code
(the stage 5 boss, 1:7FA9) the page already in stays.  `set_page` writes
port 7FFD, keeping the bit that chooses the displayed screen.

Every write to port 7FFD goes through `out_page`, which first notes the
value in `port_now`.  The interrupt pages in the sound driver and then puts
back exactly that value, so code that borrows a bank for a moment (to
write a star's row into the tile set, say) does not need to turn interrupts
off.  That matters more on the Spectrum than on the MSX: the MSX's video
chip holds its interrupt request until the game acknowledges it, so
Konami's code turns interrupts off freely (around every bank switch, for
instance) and loses nothing, while the Spectrum's interrupt is a pulse
about 36 T-states long that is simply lost if interrupts are off at that
moment.  So the relocated code replaces the `di` before Konami's 57 bank
switches with a `nop` (they only kept the MSX's own interrupt from paging
underneath them), as well as three others that only mattered on the MSX.
The few that remain guard the sound request queue, a stack trick and the
start-up code.  The port's own code does not test the interrupt state with
`ld a,i` either: on an NMOS Z80 it can report interrupts off when an
interrupt arrives during it.  An interrupt is now missed in about 1 frame in 2,000,
against 1 in 18 before (0.88), when the music ran about 6% slow and
unevenly and the pacing lost the same frames.

### 6.3 Boot, main loop and interrupt

On the MSX the whole game runs in the 50/60 Hz frame interrupt: every frame
the sound driver runs, and one game *tick* (move everything, check
collisions, update the map and sprite list) runs at each interrupt that
does not find the previous tick still running: every frame when the game is
light, every second frame in busy play (6.8).  Between ticks the CPU sits
idle.

The Spectrum cannot afford that.  Turning one tick's changes into a picture
takes about as long as the tick itself, and the two together take more than
two frames.  So the port splits them:

* **The interrupt** (`isr`, every frame) runs Konami's sound driver
  unchanged and shows the next drawn screen when it is due.
* **The main loop** (`plat_main`) does the rest: read the keyboard and
  joystick, run one game tick (Konami's interrupt routine, MSX 4045, minus
  its sound part), do the tile bookkeeping, then wait until the previous
  screen has been shown and draw the next one into the hidden screen.

`plat_boot` (entered from the tape loader) sets up the Z80's interrupt mode
2 with the vector table at AD00, looks for a Kempston interface, silences the
AY, clears both screens and runs Konami's own initialisation, which ends by
entering the main loop.

### 6.4 The play area: map tracking

Konami draws the play area into a 704-byte buffer in RAM (22 rows of 32
characters, MSX ED00) and, every tick, copies the whole buffer into the
video chip's name table.  On the MSX that copy is cheap and the chip does
the rest.  On the Spectrum, every cell whose character changed must be
redrawn by hand (8 bytes of pixels and an attribute), on both screens, so the
port needs to know exactly which cells changed, as cheaply as possible.

The copy is replaced by `plat_upload_map`, which compares the buffer with
`name_shadow` (the port's copy of the name table) and marks changed cells
*dirty* on both screens.  Comparing all 704 bytes every tick would be too
slow, so the routines in Konami's code that write the buffer report the
regions they touch (`NM_SITES`: 2 x 2 objects in `nm2_list`, other shapes in
`nm_list`), and only those regions are compared.  The writers were found by
recording every write to the buffer on the MSX side, through every stage with
every weapon (`census.py`, `census_check.py`); if a writer were missed, its
changes would not be drawn.  The big rewrites (start of play, a new stage,
the scroll) ask for a full comparison instead (`fullcmp_gen.asm`, an unrolled
routine generated by `gen_fullcmp.py`), and a full comparison also runs
every 64 ticks as a safety net.  In the comparison an unchanged cell, the
usual case, falls straight through; a changed one's work is out of line.

Text and the status lines are written to the name table directly, through
the stand-ins for the BIOS video routines, which update `name_shadow` and
mark the cells dirty.

### 6.5 The scroll and the stars

The scroll moves the whole map one character to the left every 8 ticks.  On
that tick nearly every non-empty cell changes and must be redrawn on both
screens, which makes it the most expensive tick in the game.  The row copies
of the shift are unrolled, and the shift asks for a full comparison.  The
new column that Konami then writes (`nm_r11_hl_a`) is not noted region by
region when a full comparison is already due (0.109): the comparison will
find it anyway, and the notes cost about 4,800 T-states a scroll.

Most of the cells that change on a scroll are stars.  Stars are characters
F6 and F7, and Konami's star "twinkle" (`parpadea_dos_caracteres`) is
really motion: between scroll steps the top row of those characters is
rewritten so that each star's single pixel steps across its cell.  The port
does this natively (`blink_native`, in place of Konami's routine at
0:475B): it works out the tick's row for F6 and for F7 as Konami does
(E062's rotating bit, blanked on some ticks by a mask chosen by E003) and
writes it straight into row 0 of F6 and F7 in each third of the tile set
(6.6), skipping a tile whose row has not changed (the last rows set are
kept in `bl_prev`, cleared by each stage load).

A star tile is blank when a stage loads (attribute 0).  The first time it
shows a pixel it takes its stage's attribute (`star_attr`, six bytes, one
for each of F6 and F7 in each third, which come with the stage's set) and
its cells are redrawn as a changed tile, as 1.0's conversion did.  The
attributes are worked out when the game is built, by the same conversion as
every other tile, and `native_pack.py` checks that a star converts to its
own row in that one attribute for every position of its pixel.  After that
only the star's row changes.

Rather than redraw every star cell as a changed character, the port treats
stars as a separate layer: `star_check` confirms that the star characters
differ from the empty character only in their top row and colour, the
rows' changes are kept out of the dirty bitmaps (`star_rows`,
`star_bytes`), and `draw_stars` erases the stars each screen showed (its
drawn lists) and draws the current ones from lists of star cells.  With a
fixed scheme of one tick in N drawn (`NEM_DRAW_EVERY`, 6.8),
`blink_native` runs only for a tick that will be drawn, except in test
builds, which run it every tick.

### 6.6 Tiles and colour

The game changes character shapes and colours as it goes (each stage loads
its own, and the stars move, 6.5), by writing to the video chip's pattern
and colour tables.  An MSX character has two colours per row, eight rows,
while a Spectrum cell has one ink and one paper for all eight.  So every
character is *converted* into a Spectrum tile (8 bytes of pixels and an
attribute) before it can be drawn.  The tiles are kept in a tile set in
bank 7 (DB00-F5FF): one set per screen third, as on the MSX, each nine
pages of 256 bytes (the eight pixel rows and the attributes), indexed by
the character.

The conversion is done when the game is built (3).  `native_sets.py` runs
each of Konami's graphics loads (6.11) from the cartridge ROM in the MSX
simulator and converts every character the load writes with
`tilemodel.convert`, a function of the character's pattern and colours, the
third, and Konami's state and stage.  It applies the rules 1.0 applied at
run time (1.0 converted a character the first time a cell needed it, with
a cache), so the screens are 1.0's (4.7).  Nothing is converted when the
game runs, and the port keeps no copies of the MSX's pattern and colour
tables.  In order:

* the colour fit (`fit_model.heur_q`, the model of 1.0's `convert_tile`):
  of the Spectrum ink, paper and brightness combinations made from the
  colours nearest those in the character, the one with the least colour
  error, each pixel then going to the nearer of the two;
* the power-up bar's design (below);
* on the title, the logo's own drawing (below), which ends the conversion
  of those characters;
* the stage colour rules (below);
* a tile with more than half its pixels set is stored inverted (pixels
  flipped, ink and paper swapped).  It looks the same, but its solid part is
  now paper, and a sprite passing over (which changes only the ink, 6.7)
  leaves the terrain's colour alone instead of turning a solid block of
  ground into the sprite's colour;
* the nuke capsule's characters (77-7A) are given bright cyan.  On the MSX
  both capsules are a white frame round a coloured core, which one colour
  per cell would make identical; the standard capsule (7B-7E) stays white.

On the title (Konami's state 0 or 1), the NEMESIS logo's characters (8D-FF
in thirds 0 and 1) are drawn by `logo_tile` instead.  On the MSX each pixel
line of the logo is one colour (white and grey for the frame and top band,
then cyan, light blue and dark blue stripes), which the colour fit turned
into a patchwork.  A cell with any cyan or light blue line is bright cyan
and the rest bright white; light blue lines, and dark blue ones in a cyan
cell, become a 50% stipple.  The letters' dark blue base shares its cells
with the frame's bottom edge, so both are white.  A stage's load replaces
these characters.  The title has one set, whatever stage a game ended in:
1.0 converted a few of its characters differently after a game over in
stages 2, 3, 7 and 8, none of them shown on the title.

The power-up bar (third 2, characters 15-42 and 0C) is drawn to its own
design (`bar_style`): white letters on blue, the lit box yellow on black.

In five stages, characters the colour fit drew badly are given hand-set
colours (`stage_rules.py`, the model of 1.0's rules).  A rule recognises
its characters by the MSX colours in them (for the stage 2 bricks and the
stage 8 ladder, the character number too) and either paints the tile afresh
from its MSX pixels or changes the colours the fit chose:

| Stage | Characters | Drawn as |
|---|---|---|
| 2, and the bonus stages 9-12 (the same characters) | The bricks (45-4B, only black, blues, grey, white) | Grey and white pixels solid, blue ones a 50% stipple; the left half of a 2x1 brick and of a flat bar, and the first and last thirds of a 3x1 brick, cyan, the rest bright white (the 3x1 brick's last third: the stipple only) |
| 10 (bonus) | Only the yellows, 8 or more pixels (the balls) | Yellow (not bright) on black, as the MSX's dark yellow |
| 3 | In the Moai section (the characters in `native_moai.txt`, below), a character whose main colour is a blue (the faces) or light red (the rocks) | The fit's white or grey becomes cyan, or magenta |
| 6 | Only the reds (the brain) | White or grey becomes magenta, and the cell is bright |
| 7 | The formations (blues, cyan and greens) | Bright green dots (greens and cyan) on bright blue; a mostly black edge bright blue on black |
| 7 | The band (dark blue with grey or white, nothing else but black, light blue, cyan) | White (cyan, grey, white, and black pixels just above or below a coloured one) on blue; mostly black cells white on black |
| 8 | The pipes (only black, blues, cyan, grey, white) | A cell with a line of 4 or more cyan, grey or white pixels: those white, light blue a stipple, on bright blue; the rest bright blue on black; the ladder (58) bright white on black |
| 8 | The brain (black, dark red, light red, the yellows) | Where the fit chose red or yellow: white becomes magenta, yellow red, and the cell is bright |

The power-up bar and the score (third 2, characters below 44) are never
touched.  The bonus stages keep stage 2's bricks rule, and stage 10 its
balls.

The Moai rule is the one place where the port's screens differ from 1.0's,
on purpose.  1.0 applied it to a character first drawn before distance
195h, the end of the Moai section.  Some characters appear both there and
later in the stage, so after a restart from a checkpoint past their Moai
appearance 1.0 drew them in the fit's white.  The port decides per
character: `native_moai.txt` lists the 561 characters 1.0 shows in the Moai
section (from a census of every pass through the stage), and those get the
rule, so they always have the Moai colours, as in an uninterrupted pass.
The Big Core's characters, which come later, never get it.

Since 1.2.1 the Moai heads, the rubble a destroyed head leaves and the
rocks they stand on are not converted at all: stage 3's load takes our own
tiles for them from `stage3_tiles.txt` (315 characters by third and number:
227 of the heads, 24 of the rubble piles, 64 of the rocks), in place of the
converted ones (`native_sets.py`).  The heads are yellow, their shading
yellow and black stippled, bright where the face is lit; the rubble the
same yellow; the rocks green, solid at their edges and stippled inside.
Every tile is ink on black paper, stored inverted when more than half its
pixels are set, as the conversion stores tiles.  The head and rubble
characters are those of Konami's drawings (pointers at 1:6370, sizes at
1:6283; drawings 4 to 11 the heads, 12 and 13 the rubble on the ground and
hanging from the ceiling), each with a tile in every third it can appear
in.  The rocks leave out the numbers of Konami's turret characters (from
the ROM's turret frame table, 2:9205, and shape table, 5:91D1), whose
barrels share the rocks' magenta and keep the Moai rule's colours; the
heads do not leave them out, because in stage 3 characters D2-D9 are head
pieces.  The laser's strip (FD) and the capsules (77-7E) are in no drawing
and so have no tile here.  The tiles were made once from 1.2's screens of
the section (`local/tools/art/moai_121/` in the linked clone); the file is
the art now, a line to a tile.  Stage 3's packed set grew by 147 bytes (the
stippling compresses less well than flat colour).  The Big Core's load
later in the stage puts its own tiles over some of these characters, as
before.

Konami's screen dissolve (MSX 3:A6C0, after the stage 8 brain and, when
stage 7's secret is not found, the stage 7 boss) ends a stage by eating the
screen: once through the colour table turning every background black, then
eight times through the pattern table taking one more bit of each byte
away, about 35 ticks.  Konami works in chunks (`come_un_trozo`, 3:A765) of
64 characters, 60 from 44 (sparing the score and the bar) and 54 from C0
(sparing F6-FF).  The port does each chunk on the tile set instead
(`dz_chunk`, fixed memory, in place of 3:A765):

* the colour pass (`dz_col`) gives every tile black paper, brightness kept.
  A tile stored inverted goes back to ink on paper first, its old paper
  becoming the ink; which tiles of stages 7 and 8 are stored inverted is
  known when the game is built (`nl_inv7`, `nl_inv8`);
* after the colour pass's last chunk (Konami does the whole pass in one
  tick, third 0's C0-F5 last), a patch for the stage (7 or 8) puts in 1.0's
  tile wherever that rule is not what 1.0 shows.  1.0 redrew a dissolving
  tile (`dz_tile`) with the colour that had shown its foreground as the
  ink on black, keeping the MSX's foreground pixels whose colour is
  strictly nearer that ink than black; `tilemodel.dz_post` models it, and
  `native_sets.dz_patch` keeps the tiles where it differs from the simple
  rule;
* each pattern pass ANDs the tile's rows with Konami's mask for the pass
  (E1A2, turned three bits a row after the first pass, as E1A0 says).  With
  the colour pass's tiles exact, this is what 1.0 shows, since 1.0's pixels
  were the MSX's pattern, masked row by row.

Each chunk has every cell redrawn at the end of the tick, as a load does
(6.11).  Konami's chunk buffer (EA00-EBFF) is not written: nothing reads it
after the dissolve (4.2).  The screens match 1.0's through the dissolve
except its first three ticks, where 1.0 converted the changed tiles a few a
tick and so caught up with the colour pass over several screens, while the
port shows it at once.

### 6.7 Renderer and sprites

The port draws into two screens: the hidden one is drawn while the other is
shown, then they swap (by flipping the display bit in port 7FFD), so the
player never sees a half-drawn picture.  Each screen has its own bitmap of
dirty cells, since each must catch up with every change.  Drawing a screen
(`render_frame`): update the star layer, redraw the dirty cells from the
converted tile set, then draw the sprites.  A sprite is erased by marking
its cells dirty in the screen it was drawn on, as it is drawn: that
screen's cells have just been redrawn, so the marks wait for its next
picture, which draws those cells again without the sprite.  (Until 1.2
each screen kept a list of the boxes drawn on it and marked them at its
next picture.)  Character 0, blank in every third and over a third of the
cells drawn, is written as eight zeros without reading the tile set.

The sprites come from the game's own sprite list (MSX EC80): the same
32 entries of position, pattern and colour the game would give the video
chip.  Each 16 x 16 sprite is ORed into the screen, shifted to its pixel
position (right by 1-4 bits, or for offsets 5-7 left by 3-1 into the same
three bytes, which halves the shifting; a sprite on a cell boundary is not
shifted at all).  The cells it touches take its colour
as their ink (over black paper they also take its brightness; over
coloured paper, an inverted tile, they keep their own).  Since 1.1.2 those
are only the cells its pixels reach, not its whole box of 2 or 3 by 2 or 3
cells: a table (`sp_ext`, indexed by the pattern number) holds each
pattern's first and last rows with pixels and its leftmost and rightmost
pixels (Konami's 64 patterns, worked out again by `sp_calc` at the first
drawing after each graphics load, which sets `spx_stale` in `nl_done`; the
ship's three frames).  `draw_sprite16` reads it before it draws: only the
rows from the first to the last are drawn (since 1.2; a 16-row pattern has
pixels in under 9 on average), a pattern with none is not drawn at all, and
the box is cut to the rows and columns the pixels reach at the sprite's
position.  The cut box is what is coloured and marked dirty, so fewer cells
are redrawn, and cells near a small sprite (a bullet, a shot) keep their
own colours.  The marking is one mask for every row of the box (`sp_mask`).
Build option `NEM_TRIM=0` for the whole boxes.  Sprites are drawn from the last to the first, so that
where two share a cell, the higher-priority one's colour wins.  Konami's list
is usually full, with most entries parked below the screen, so one pass
collects the entries on screen (up to an end marker) into `spr_vis`, and
the drawing works back through those (0.109).

A sprite's ink is chosen in `draw_sprites` from its MSX colour (`spr_ink`, in `tables.py`; the
MSX's light blue, light red and light yellow are mapped to bright cyan, red
and yellow rather than to the nearest Spectrum colour, white), unless
`spr_pmap.asm` gives its pattern a colour of its own: explosions go yellow
then red, and enemy bullets stay white.  The option uses the explosion's
last pattern (132; magenta on the MSX), so options show red.  Stage 3's
Moai rings (pattern 252 in MSX colour 8, medium red) are bright cyan since
1.2.1.  The same pattern and colour is a red enemy in stages 1, 4, 8 and
10, so `st3_rings` (fixed memory, called from `nl_stage`) writes the
pattern's entry at each stage load: cyan for stage 3, empty for the rest.

The ship is redrawn (0.100, `ship.asm`).  On the MSX it is two sprites at
the same place, Konami's patterns 0/4 (level), 8/12 (diving) and 16/20
(climbing): white, with a red canopy (a light blue belly when climbing) as
a second one-colour sprite, the only way an MSX1 sprite gets a second
colour.  Here the cells take one ink, so the second sprite cost a draw and
an erase for nothing.  Patterns 4, 12 and 20 are not drawn at all (since
0.109 `draw_sprites` drops them before looking up their colour), and 0, 8
and 16 come from `ship_pat` instead of Konami's table (`draw_sprite16`
for a sprite wholly on screen, `spr_patsel` for one at an edge).  Since 0.105 these are
Konami's own outlines with the second colour shown in one colour: on the
level and diving frames, the red canopy becomes a black line inside the
ship's white outline (the canopy's top edge white, the line beneath it);
on the climbing frame, the light blue belly becomes a checkerboard stipple
under the solid white top.  (0.100-0.104 used redrawn designs with seams and
an outlined canopy; in motion, frames that differed much from one another
looked like a different ship at each change of direction.)  Konami's
patterns stay in the sprite pattern table (bank 7, F800) as the MSX has
them.  Patterns 0-23 are the ship's alone: patterns 0-39 are the same after
every stage's load (`native_pack.py` checks it, and stores them once), and
over 900 seconds of play with the ship climbing
and diving (stages 1-5 and the bonus stages 9-11) no other sprite used
them.  `check_sprites.py` draws the ship by the same rule.

The player's missile (patterns 28 and 32) is flagged in `spr_pmap.asm`
instead: only the cells of its box that are empty or hold a star take its
colour (`attrs_keep`, bank 7, which looks each cell up in the name table).
Cells holding terrain keep their own colours, and the missile shows in the
terrain's colours there.  Without this, the missile rolling along the
ground recoloured up to nine cells of terrain around it, a yellow block
that followed it along the floor.

Konami hides all the sprites by writing an end-of-list marker straight into
the chip's sprite table (on the way back to the title, and while restarting
after a death), leaving its own list as it was.  The port notices that write
and draws no sprites until the game next uploads its list (`spr_on`), as the
chip would.

Sprites crossing the left or right edge are clipped as the chip would clip
them (`spr_edge`, in the low gap at 7B40).  The part on screen is shifted
into a 16 x 16 pattern of its own (`edge_pat`), which `draw_sprite16` draws
on a cell boundary: at x 0 for the left edge (a sprite with the early clock
bit, 1 to 15 pixels off), at x 240 for the right (X 241 to 255).  Only the
columns that show are coloured and marked, so with 8 or more pixels off
screen a single column is; all 16 rows are drawn, and the box is not cut.
Sprites are still drawn only when wholly below the top edge.

### 6.8 Pacing and speed

On the MSX the whole game runs in the interrupt (`interrupcion`, 4028): at
each interrupt Konami runs one tick, unless the previous tick is still
running (a lock at E005), in which case that interrupt is skipped.  So the
tick rate follows the cost of a tick: one a frame when a tick fits in a
frame, one every two frames when it takes between one and two, and so on.
On a 50 Hz machine that is 25 ticks a second in busy play and up to 50 in
light stretches (the starts of stages, the run from the volcanoes to the
stage 1 boss, parts of stage 2); a 60 Hz machine, with shorter frames,
fits a tick in one frame less often.  Versions up to 0.98 assumed a fixed
two-frame rhythm (measured from 60 Hz video) and never ran faster than 25
ticks a second.

The port runs Konami's ticks back to back in its main loop and draws some
of them into the hidden screen, which the interrupt shows (flips) when it
is due; the next tick's logic runs while a screen waits, so only drawing
waits for the flip.  Two limits keep it from running ahead of the MSX: a
tick may take no less than one frame (`FRAMES_PER_TICK`, 1; build option
`NEM_FPT`), as on the MSX, and screens are at least `FLIP_FRAMES` frames
apart.  Its ticks cost more than the MSX's (all the drawing the video chip
does there), so in busy play the CPU sets the rate and the limits rarely
matter; in light stretches the port speeds up as the MSX does.  One
difference remains: the MSX's rate moves in whole frames (a tick that just
misses one frame takes two), the port's does not, so where the MSX's ticks
are only just over a frame the port can run a little faster (the stage 2
boss: 30-33 ticks a second against the MSX's 27-29).

Not every tick is drawn.  Since 0.110 the release decides tick by tick
(`pace_adapt`, called after each tick; in fixed memory since 1.2, in bank C
through a far call before): every
tick is drawn while the game keeps up with a rhythm of 15 eighths of a frame
a tick (about 26.7 ticks a second, near the MSX's), and a tick is left
undrawn while the game is behind that rhythm by more than a frame, but never
two in a row.  The balance (`pace_debt`, in eighths of a frame) is clamped
to between 4 frames ahead and 8 behind, so a slow stretch does not leave a
debt that makes a quiet one skip.  Since 1.1.3 a tick in which the
directions differ from the last tick's (`kb_cache+9` bits 0-3: the keys
and a Kempston stick; fire does not count) is always drawn; the debt it
leaves makes the pacer skip a later one (`INPUT_DRAW`; `NEM_INPUTDRAW=0`
for 1.1.2's pacing).  Screens are at least one frame apart.  In
busy play this falls back to one tick in two, as the fast edition of
0.98-0.109 drew all the time; where there is room it draws every tick.  The
title shows the version ending in A.  Build options: `NEM_ADAPT=T,SLACK` for
another rhythm and slack (eighths of a frame), and the fixed schemes of
0.98-0.109, selected by setting either of:

* `NEM_DRAW_EVERY=N`: one tick in N drawn (`DRAW_EVERY`), screens at least
  `NEM_FLIP` frames apart (default 3; 2 would follow the MSX's bursts more
  closely, but ran the stage 2 boss 30% fast).  `NEM_DRAW_EVERY=2` is the
  former fast edition (title F); `NEM_DRAW_EVERY=0`, one undrawn tick after
  every four drawn, the former smooth edition (title S).
* `NEM_EXTRA=N`: one undrawn tick after every N drawn (`LOGIC_EXTRA`;
  `NEM_EXTRA=0` draws every tick, as `bench.py` wants).

An undrawn tick's changes are simply caught up by the next drawing, and the
game itself is unchanged (the lockstep still matches).  `release.sh
VERSION` builds the release into `release/`.

Measured for 1.0 (whose 128K game is 0.110's) against the MSX original,
simulated at 50 Hz with the same front end and the same scripted play
(invulnerable, fire tapped; its BIOS calls, stubs in the simulator,
charged an estimate of the real BIOS's time;
`local/tools/measure/msx50.py` and `specrun.py` in the linked clone), over
the first two stages (percentages: the MSX's time over the build's, so
speed against the MSX):

| | MSX 50 Hz | 0.110 | 0.109 fast | 0.109 smooth | 0.100 fast | 0.100 smooth |
|---|---|---|---|---|---|---|
| Stage 1 | 199 s | 209 s (95%) | 206 s (97%) | 230 s (87%) | 215 s (93%) | 238 s (84%) |
| Stage 2 | 199 s | 205 s (97%) | 199 s (100%) | 208 s (96%) | 208 s (96%) | 215 s (93%) |
| Both | 398 s | 414 s (96%) | 405 s (98%) | 438 s (91%) | 423 s (94%) | 453 s (88%) |
| Ticks a second | 26.9 | 25.8 | 26.5 | 24.5 | 24.1 | 22.3 |
| Screens a second | 25-50 | 16.1 | 12.6 | 18.5 | 12.0 | 17.9 |
| Input lag (frames, mean) | 3.15 | 6.0 | 6.4 | 5.5 | 6.6 | 6.0 |

That play is light: no power-ups, so few sprites.  Over the whole first
loop with every weapon (Konami's own cheat, as the checkers' all-stages
runs; `msx_loop.py` and `perfprofile.py`), where many more sprites are
drawn, every build falls further behind the MSX:

| Stage | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | Loop |
|---|---|---|---|---|---|---|---|---|---|
| MSX 50 Hz | 182 s | 196 s | 190 s | 204 s | 244 s | 156 s | 142 s | 183 s | 1,496 s |
| 0.110 | 83% | 91% | 83% | 90% | 87% | 80% | 86% | 85% | 86% |
| 0.109 fast | 84% | 94% | 82% | 89% | 88% | 84% | 86% | 87% | 87% |
| 0.109 smooth | 78% | 87% | 75% | 81% | 76% | 71% | 73% | 75% | 77% |
| 0.110: ticks not drawn | 41% | 31% | 44% | 41% | 44% | 44% | 47% | 35% | |

(The fast edition left 50% of ticks undrawn throughout, the smooth one
20%.)  The project's `performance-profile-0.109.md` has the screens a second
and motion evenness by stage, and the trial of the adaptive rule's settings.

The lag is counted from a press at the start of a frame to the frame whose
displayed screen first shows the ship moved, plus the beam's time to reach
the ship (`lag2.py`, 70 presses in each of three runs).  The MSX is measured
the same way (`msx_lag3.py`): the video chip's frame interrupt comes at the
end of the last active line (TI, VDP Programmer's Guide, p. 5-5), so with
313 lines a frame the beam reaches a sprite at Y (122 + Y) / 313 of a frame
after it.  (Versions up to 0.94a quoted
24.3 ticks a second, from 90 seconds that were mostly the quiet opening of
stage 1: 0.94a measures 19.8 over the stage.)  In busy play the CPU is
never idle.  In an earlier measurement, before the native build, a tick
cost about 189,000 T-states
against a budget of 141,816 for 25 a second: Konami's own code, sound
included, took about 76,000 (40%), the drawing about 38% (more than half of
it the sprites), and the map tracking, paging and video stand-ins most of
the rest.  The MSX gets its sprites and scrolling from the video chip.
Drawing one tick in three reached 23.1 ticks a second under the old
limits, but at 7.7 screens a second.

The native build, which converts nothing as it runs, was measured against
1.0.  `specrun.py` (120 seconds, stages 1-2, light play): 24.57 ticks and
14.7 screens a second, against 1.0's 24.16 and 13.7.  The whole-loop
profile (`perfprofile.py`, `NEM_ALL=1 LOOP=1 NOPRESS=1`, 1,500 seconds:
stages 1-6), with two figures for the spikes (gaps between screens, and the
fewest screens in any 50 frames):

| | 1.0 | Native |
|---|---|---|
| Ticks a second, by stage | 22.0-25.5 | 23.1-26.6 |
| Screens a second, by stage | 12.3-17.1 | 13.3-18.9 |
| Fewest screens in any second, by stage | 0-4 | 6-8 |
| Gaps of 9 frames or more | 247 | 38 |
| Longest gap | 90 frames | 28 frames |

1.0 had a second or more with no new screen in each of stages 2-6, while it
converted tiles; the native build never shows fewer than 6 screens in a
second.  In play the gain is less in the average than in consistency: no
obvious lags at the turrets and the like, where 1.0 converted tiles as they
scrolled in.

Where the 128K's input lag goes (1.1.2, first loop, all weapons, 779
presses; frames from the press): to the tick that reads it and moves the
ship, 1.40; to the end of that tick and the pacing decision, 1.98 (the
rest of the tick, and the next whole tick when the pacer leaves that one
undrawn: 0.55 ticks on average); waiting for the previous screen to be
shown, nil; drawing, 1.44; to the screen shown down to the ship's line,
0.98; 5.80 in all.  Waiting for the previous screen before the tick
instead of after was tried: 11% slower, no less lag.  Drawing the tick
after a change of direction (1.1.3) was measured with presses every 97
frames and every 17 (about four changes of direction a second):

| | 1.1.2, 97 | 1.1.3, 97 | 1.1.2, 17 | 1.1.3, 17 |
|---|---|---|---|---|
| Ticks a second | 24.67 | 24.47 | 24.48 | 23.81 |
| Screens a second | 15.23 | 15.38 | 14.98 | 15.49 |
| Input lag, median (frames) | 5.49 | 4.51 | 5.50 | 4.50 |
| Input lag, mean | 5.79 | 5.20 | 5.81 | 5.05 |
| Input lag, 90th percentile | 8.50 | 7.49 | 8.50 | 6.51 |

The speed work for 1.2 (11 November 2026) started from an exact profile of
1.1.3: SkoolKit's simulator calling a function for every instruction, over
the first loop with every weapon, which gives each instruction's T-states
by address and bank.  A tick cost 144,054 T-states over the loop and
188,100 in the busiest quarter of seconds: Konami's game logic 38%, sprites
19%, cells 12%, map tracking 10%, paging and far calls 9%.  The same play
run with and without the video circuit's contention showed bank 0's code
running 19% slower where it sits.  Three changes followed, none of which
alters what is drawn: the copies of hot routines (6.1), the sprite work
outside the pixel drawing (6.7: rows, the erasing, the extent's look-up,
the ink), and small ones (the pacer in fixed memory; blank cells; a dead
loop in the star redraw; and the dissolve no longer working out the sprite
extents again at every chunk, which had made each dissolve 0.8 of a second
longer since 1.1.2).  Measured over the same loop (`pp_feel.py` and the
profile):

| | 1.1.3 | 1.2 |
|---|---|---|
| Ticks a second, loop | 24.6 | 27.2 |
| Pictures a second, loop | 15.3 | 20.3 |
| Ticks a second, busiest quarter of seconds | 18.9 | 22.1 |
| Pictures a second, busiest quarter | 9.6 | 12.0 |
| T-states a tick, loop | 144,054 | 130,463 |
| A sprite, all in (T-states) | 5,700 | 3,900 |
| Ticks drawn | 62% | 75% |

Nothing holds the build back when it has time to spare, so part of the
gain is the lightest stretches running faster, as the MSX's do: 14% of
seconds run above 30 ticks, against 8% in 1.1.3 and 9% for the MSX at 50
Hz in the simulator (an older run of stages 1 to 3).  The slowest twentieth
of seconds run at 21 ticks or fewer, against 18.  The project's
`perf-review-1.1.3.md` has the method, every table and the candidates not
taken up.

### 6.9 Input

`read_keyboard` reads the Spectrum's eight keyboard half-rows, and
`kb_compute` (generated by `tables.py`) translates them into the nine rows of
the MSX keyboard matrix and the MSX joystick byte, which the game reads
through the stand-ins for its BIOS calls.  The Sinclair joystick (keys 6-0)
is just part of that key map.

A Kempston interface (port 0x1F) needs care: on a Spectrum without one, the
port returns whatever happens to be on the data bus, which could look like
joystick movement.  So the port looks once, at boot, just after an
interrupt: at that moment the bus is idle and reads 0xFF, which on a
Kempston would mean all four directions at once, which is impossible.  Any
other value means an interface is present, and from then on its bits are
added to the joystick byte each tick.  The detection patches `kempston`'s
first instruction (a `ret`) to a `nop`.

A second fire button reads as bit 5 on some Kempston interfaces and bit 7 on
others (the Retroleum SmartCard, from pin 9); either is the MSX's trigger B,
which Konami uses only for power-up (tried on a real Spectrum through the
SmartCard, with a Mega Drive pad: B fires, C takes the power-up, and through
a DivMMC Future).  Bits 5 and 7 are used only if they read 0 at the
boot-time look, so an interface that leaves them floating cannot select
power-ups by itself.

For one-button joysticks, `fire_hold` (after the keyboard and Kempston are
read) presses trigger B as well once fire has been held for `HOLD_TICKS`
ticks (12 by default; `NEM_HOLD`), until fire is let go.  Konami acts only
on the tick a button goes down (MSX E008, the new presses, from E009), so
that is one power-up per hold, and nothing else in the game reads trigger B.
Konami's own handling of a held fire button (a shot every 15 ticks) is
unchanged.  `test_kempston.py` checks the detection, the port decoding and
`fire_hold` against their rules, and `HOLDFIRE=1` (4.4) checks the game's
response against the MSX's.

### 6.10 Sound

Konami's sound driver (MSX bank 7) runs unchanged in the interrupt every
frame.  Its writes to the sound chip go through the stand-in for the BIOS
routine WRTPSG to the 128K's AY (ports FFFD and BFFD).  Registers 14 and 15,
the MSX's joystick port, are not passed on to the AY; reading register 14
returns the joystick byte.  A write of the value a register already holds
is skipped (about 12 of 19 a tick), except to the envelope shape, whose
write restarts the envelope; `plat_boot` clears the AY's registers so that
they match the copy (`psg_regs`).  The tempo depends on the interrupt
running every frame (6.2).  The Next plays the effects on a second AY
(9.3).

### 6.11 Graphics loads

Konami writes its graphics into the video chip's pattern, colour and sprite
pattern tables at a handful of events.  A census of the original
(`local/tools/native/census_gfx.py` in the linked clone: every graphics
write, over a route through every hidden target and a route with deaths,
game over and the title) found exactly these, and no other graphics writes
apart from the stars, the dissolve and the boot's clearing of the video
memory.  In 1.0 each load ran Konami's loaders and decompressor into copies
of the video memory, and the characters were converted as they were drawn.
In the port each is a load of what the build converted (6.6):

| Event | Konami's site | Load |
|---|---|---|
| Each stage (a new game, each new stage, after each life) | 0:422A, the whole routine | `nl_stage`: the stage's complete set; then E100 is set to 1 and the mapper left as Konami's routine leaves it |
| The Big Core (stages 1-6) | 0:4A8A, its call of `carga_fichas` | `nl_bigcore`: a patch for the stage |
| The screen before each life | 0:53D4, its call of `carga_la_fuente` | `nl_prestage` |
| Game over | 0:54DD | `nl_gameover` |
| The title | 0:5300, its call of `carga_el_marcador` | `nl_title` |
| The ending | 0:4B04 | `nl_ending` |
| The ending's status line | 0:4C2E | `nl_marcador` |

The rest of each loader that is game logic (the Big Core's clearing of the
objects, for instance) stays Konami's.  The loading routines themselves,
Konami's decompressor and block routines, the graphics tables and the
loads they replace are left out of the build (`gen.py`'s `LEAVE_OUT`); the
title's later loads (`presentacion`, 0:5A54) return at once, their
characters being in the title's set.

A stage's load is complete: its tiles unpacked straight into the tile set
(DB00, the layout of 6.6), sprite patterns 0-39 (the same in every stage,
stored once) to F800 and 40-63 to FD00, and the six star attributes (6.5).
Stages 10-12 are stage 9's set and a small patch of the characters that
differ, with stage 9's sprite patterns.  The other events load a patch:
a 96-byte mask (one bit for each character of each third), the 9 bytes of
each marked character, an 8-byte mask of sprite patterns and the 32 bytes
of each marked one.  A patch is unpacked into a work area in page D
(E800-FBFF) and copied into place a character at a time; the characters it
leaves out stay as the screen had them, as on the MSX.  The census showed
that no character a stage's load leaves alone is shown in that stage (two
harmless exceptions apart), and that the screens that are not play (before
each life, game over, the title) show what was there before; hence the two
kinds.

Each piece is packed with ZX0, the format the tape uses (6.13), and lies in
a switched bank (5).  The tile set is in bank 7, and only one bank can be
at C000 at a time, so the unpacker (`nl_unpack`) reads its input through a
256-byte buffer in fixed memory (`nl_buf`, 9100), refilled from the source
bank, and writes straight into the destination's bank.  After any load
every cell is redrawn on both screens at the end of the tick (`nl_done`),
as after a load in 1.0.  `nl_count` counts the loads and dissolve chunks
for the checks (4.2).

The video stand-ins keep only the name table's and the sprite attributes'
work (text, the status line, clearing the screen): a write to the pattern,
colour or sprite pattern tables is ignored, FILVRM fills only 3800-3BFF,
and LDIRMV, reached only from code that is left out, does nothing.

### 6.12 The front end

On the MSX the game starts with the Konami logo, then the title, then an
attract cycle (an illustration and demo play).  The port goes straight to
the title and stays there: `gen.py` patches estado_0 so that the title panel
is drawn instead of the logo (52D9 now calls `spec_title`, which draws
Konami's panel and then the controls and credit from `ctl_text` in bank C),
and estado_1 so that it keeps blinking the selection instead of counting
down to the attract cycle (530F).  Dropping the attract cycle freed the
space that the stage 6 boss's graphics needed.  Konami's title font has
letters and digits only, so the text has no punctuation, except the
version's full stop (the version is at the top right, row 0, from 0.101;
0.100 had it after the copyright): the font's blank character 0E, in the
top third, is a full stop, white like the rest of the text.  It is part of
the title's set, which `native_sets.py` makes with that character added
(1.0 wrote it in at run time, `title_dot`).  Row 0 is cleared when play
starts, and the title writes it again after a game over.  The title's
graphics are one load (6.11) at 0:5300, its call of `carga_el_marcador`;
the loads of Konami's title sequence after it are in the same set.

The title's tune (0.102).  On the MSX the logo and the title are silent;
the music that goes with them is the attract cycle's, Konami's tune A6,
which starts with the illustration about 11 seconds after the title
appears.  With the attract cycle gone, the title plays it: estado_1 (0:5308)
now goes through `title_tick`, which requests A6 (through Konami's own
`pide_sonido`, 0:49E9) when Konami's first music channel is silent and 150
frames (3 seconds) have passed since it fell silent, then does what
estado_1 did.  `title_start`, called when the title is drawn, makes the
first play start at once.  The gap is counted in frames because the
title's ticks run at different rates under different pacing.  When a game
starts, estado_3 (0:537F) goes through `title_end`, which stops A6 with
Konami's silence request (CD): otherwise the tune would play on into the
stage and hold the stage's music back, since Konami starts that only on a
silent channel.  The tune's notes were checked against the MSX's: the same
996 register states in the same order, the same 122 note changes.

### 6.13 The tape

`make_tap.py` writes, in order:

1. a BASIC program: `BORDER 0: PAPER 0: INK 0: CLS: CLEAR 24575: LOAD ""
   CODE: RANDOMIZE USR 16384` (zeros written as NOT PI);
2. a machine-code loader, loaded into screen memory at 4000, the only memory
   the game does not need loaded (it is drawn black on black, so it does not
   show);
3. the loading screen (`tape/loading.scr`), uncompressed so that it builds
   up on screen in the usual way;
4. the game, as ZX0-compressed blocks.

The loader clears the memory the game expects to be zero, then loads the
loading screen into bank 7, the second screen, and displays that screen while
everything else loads.  Each game block is loaded into memory that is free at
that moment and unpacked into place (`tape/dzx0_standard.asm`): the switched
banks through 8000, bank 2 through 5B00, bank 5 through bank 7 at DB00; each
borrowed area is cleared afterwards, and bank 7's own small block loads last,
uncompressed.  The loader reads blocks with the ROM's tape routine
(LD-BYTES).  It does the routine's set-up itself, pushing its own return
address rather than SA/LD-RET's, so that the routine comes back to the
loader rather than re-enabling interrupts and checking BREAK while the game
overwrites the system variables, and joins the ROM at 0562.  That address
matters: DivMMC-type interfaces load a .tap file from their card by trapping
the fetch at 0562, so a loader that joins later (as before 0.94a, at 056B)
waits for a real tape there and hangs.  In case such an interface returns
through SA/LD-RET all the same, the loader runs in interrupt mode 2 with a
table at BD00 whose handler is a bare RET: an interrupt then does nothing
and leaves interrupts off.  The table is rebuilt before each block (the
loader clears bank 2's area on the way) and cleared, being Konami's RAM,
before the jump.  Finally the loader displays screen 0 and jumps to
`plat_boot`.

0.94a loads on a real +3 through a DivMMC Future, where 0.94 hung.

`test_tape_trap.py ret|sald` loads the tape the way such an interface does:
each LD-BYTES is trapped at 0562 and its block put straight into memory, the
trap returning by RET or through SA/LD-RET (with the frame interrupt made due
around its EI, so the handler runs).  Both must reach `plat_boot` with the
snapshot's memory.

The tape is about 70 KB (1.0's was about 63 KB): about 40 seconds longer
to load at the ROM's speed than 1.0's.  The packed graphics (6.11) do not
compress again on the tape, where 1.0's MSX graphics and code did.  The
loading screen is the MSX attract illustration, converted by
`tape/make_loading.py` (two colours per cell, checkerboard dithering in the
ships).

## 7. Known limitations

* Sprites coming in from above the top edge appear only once wholly on
  screen.
* One colour per cell: sprites over sparse terrain (tree tops) recolour it,
  the ship's red canopy is a black line and its blue belly a stipple, and
  overlapping sprites share one colour.
* The attract cycle (the illustration and demo play) is not carried.

## 8. Files

In `spec/` unless shown otherwise.

| File | Contents |
|---|---|
| `plat_spec.asm` | The platform: BIOS stand-ins, paging, mapper, the name table and sprite stand-ins, map tracking, main loop, interrupt, boot, buffers; includes the rest. |
| `native.asm` | The graphics loads, the ZX0 unpacker and Konami's dissolve on the tiles (6.6, 6.11); the Next's loads into its store (section 9). |
| `convert.asm` | The tile set's bookkeeping: tiles that changed redrawn where they show, the star twinkle and the star rows (6.5).  (No conversion, despite the name.) |
| `render.asm` | The renderer: cells, stars, sprites and their erasing. |
| `pace.asm` | The adaptive pacing (6.8): in fixed memory on the 128K, in bank C on the Next. |
| `ship.asm` | The ship's own patterns and `spr_patsel` (6.7). |
| `VERSION` -> `version.inc` | The version, and the title's line for it (`build.py`). |
| `star_check7.asm`, `spr_pmap.asm` | Code and tables in bank 7. |
| `native_sets.py`, `tilemodel.py`, `native_moai.txt` | The build-time conversion: Konami's loads replayed in `msxsim` and converted by 1.0's rules (6.6); stage 3's Moai characters. |
| `stage3_tiles.txt` | Stage 3's Moai heads, their rubble and the rocks, our own tiles (6.6, 1.2.1). |
| `fit_model.py`, `stage_rules.py`, `convert.py`, `extract.py`, `gfxcap.py` | The colour fit's model, the stage colour rules' model, the colour conversion and palettes (also used by `tables.py`), Konami's palette and graphics read from the ROM, Konami's loaders run in `msxsim`. |
| `native_pack.py` -> `native_data.asm`, `native_tables.asm`, `native/` | The pieces packed and placed in the banks, and their tables (3, 5; generated, not in the repository). |
| `fullcmp_gen.asm` | The generated full map comparison (`gen_fullcmp.py`). |
| `tables.py` -> `tables.asm` | Sprite inks, border colours, keyboard decoder, the unpacker's buffer. |
| `emu_bench.py` | The simulator's screen grabs. |
| `konami_spec.asm`, `konami_spec_stubs.asm`, `konami_spec_hot.asm` | Konami's code, generated by `reloc/gen.py`; the last is the 128K's copies of hot routines (6.1). |
| `build.py`, `make_tap.py`, `verify.sh`, `release.sh` | Build, tape, regression checks, the release. |
| `lockstep_spec.py`, `screen_lockstep.py`, `check_*.py`, `test_*.py` | The checks of section 4. |
| `tape/` | Loader source (generated), loading screen and its converter, ZX0 unpacker and licence. |
| `../reloc/` | The relocator (`gen.py`) and its disassembly parser. |
| `../msxsim/` | The MSX simulator used by the build's conversion and the checks. |
| `../README.md`, `../LEGAL-NOTICE.md`, `../LICENSE` | The front page (background, playing, building); who owns what; the MIT licence for the port's own work. |
| `../docs/` | This description, the development notes, and screenshots. |
| `nx_low.asm`, `nx_l2.asm`, `nx_tur.asm` | The Spectrum Next's own code (section 9): Layer 2, hardware sprites, the smooth scroll, the MSX2 graphics. |
| `native_next.py` | The Next's graphics loads, made when the Next is built (section 9). |
| `nxbuild.sh`, `sna2nex.py` | The Next build, and the snapshot made into a `.nex`. |
| `nx_pack.py`, `nxgfx/`, `nx_art.py`, `enh_patch.py` | The Next's graphics and redrawn enemies packed for the `.nex`, and the data bytes of `nxgfx/patches.txt` put into it. |
| `nx_smoke.py` | A minute of the `.nex` in ZEsarUX (`release.sh`). |

## 9. The Spectrum Next build

The Next build is the same port with a different drawing end.  Konami's
code, the platform layer, its map tracking and the native graphics loads'
hooks are shared with the 128K build; what the Next has that the 128K lacks
(a fast CPU, a bitmap layer, hardware sprites, a hardware scroll and a large
memory) replaces the 128K's renderer and its two-colour tiles.  The Next
never draws the 128K's tiles: it draws from its own character artwork and
from a store of the MSX's character rows (9.2, 9.3).

### 9.1 How the build is made

`nxbuild.sh OUT.nex` first runs `native_next.py`, which replays Konami's
graphics loads in msxsim and writes the bytes they write as the Next's
pieces (`native_next.dat`) with their table (`native_tables_next.asm`, 9.5).
It then runs `build.py` with `NEM_NEXT=1`, `NEM_FPT=2` and
`NEM_ADAPT=14,8` (9.2).
The shared files (`plat_spec.asm`, `render.asm`, `convert.asm`,
`native.asm`) differ for the Next only inside `ifdef NEXT` blocks, and the
ten places where the Next build takes over one of Konami's instructions are
`reloc/gen.py`'s `NEXT_PATCH` (9.4), so the 128K builds are byte for byte
what they were without the Next.  The other way round, the 128K's renderer
(`render_frame` and all that only it calls: the cell, star and sprite
drawing), which the Next never calls, is left out of the Next build
(`ifndef NEXT`; until 1.2 it was assembled in, unused).  `NX_AT` after
each piece left out puts what follows at the address it had in 1.1.3N and
fills the gap with `di` / `halt`, so nothing in the Next build moved: its
`.nex` differs from 1.1.3N's only in those seven gaps, 2,872 bytes of
free room in all (7B40-7BF7, 89BD-89CE, 89FA-8BEE, 8CBC-8E11, 8E17-92FF,
9C2F-9DFF, and F700-F768 in bank 7).  The Next build has none of the 128K's
copies of hot routines, and its pacing stays in bank C.  One of those places, 0:544F, is in code
the native build leaves out (`LEAVE_OUT`); `NEXT_KEEP` keeps the Next's call
there.  The 128K's packed graphics (`native_data.asm`) are not part of the
Next build.  The result is `nemesis_next.sna` (never `nemesis.sna`,
so `release.sh` cannot package it by mistake).  sjasmplus then assembles
`nx_low.asm`, which includes `nx_l2.asm`, against that build's symbols
(`nx_syms.inc`), as a separate 16K block, and `nx_tur.asm` against
`nx_low.asm`'s symbols (`nx_lsyms.inc`) as the code of page 55 (9.2).
`nx_pack.py` packs the graphics (9.5): those in `spec/nxgfx/`, the stage
files completed with Konami's own stage loads, the pieces `native_next.py`
made, and the redrawn sprite enemies (9.6).  `sna2nex.py` packs the
snapshot, the block and the graphics into a `.nex` (format V1.2), and
`enh_patch.py` puts the data bytes of `spec/nxgfx/patches.txt` into it.  It
skips the 306 of them that lie in code the native build leaves out (the font
and its colours, in Konami's status-line loader): those reach the Next
through `native_next.py`'s replays, which run on a ROM with the patch's data
bytes in.  The build does not need the MSX2 patch.  Like the 128K build, it
replays Konami's loads in msxsim, so it needs SkoolKit as well as the ROM.
A build switch, read by `nx_pack.py`, leaves out the redrawn enemies drawn
as sprites: `NEM_ARC_SPR=0`.  (Those Konami draws with characters are part
of the character pool, 9.5.)

### 9.2 Memory and paging

* Port 7FFD is never written: on the Next it also puts the ROM back at
  0000-3FFF.  Paging goes through NEXTREG 56h/57h (MMU6/MMU7, C000-FFFF)
  instead, with the same page numbers.
* 16K bank 8 is mapped at 0000-3FFF (MMU0/MMU1) and holds `nx_low.asm`:
  its code and buffers, reached from the shared code only through a jump
  table at 0100.
* Layer 2's two screens are banks 9-11 and 13-15, flipped by NEXTREG 12h
  where the 128K flips its screens.
* **The store of character rows**, which the Next draws from wherever its
  character pool does not (9.3): pages C and D (banks 4 and 6) hold at
  E800-FFFF the colours and the patterns of the three thirds, laid out as
  the MSX's colour and pattern tables, and bank 7 holds at F800-FFFF
  Konami's 64 sprite patterns.  The graphics loads fill it (9.5).  On the
  128K, pages C and D's E800-FFFF hold packed graphics and their work
  area, which the Next build leaves out.  The renderer maps page D's and page C's E000-FFFF at
  4000-7FFF (MMU2 and MMU3) while it draws, so a variable it reads
  meanwhile must sit above 8000: `dz_on` is placed there, and asserted
  (`plat_spec.asm`).  `tile_cdirty` and `tile_pdirty` (fixed memory, Next
  only) hold a bit for each character of each third: changed since the
  stage load (9.3).
* Banks 16-31 hold the stage files of stages 1-8, the fire copies and the
  redrawn sprite enemies (9.5, 9.6), bank 32 the character pool's maps for
  stages 1-8 and banks 33-40 its blocks (pages 66-80, 9.3); bank 46 holds
  the bonus stages' stage file and bank 47 their maps (9.5).  Bank 41's
  first 8K (page 82) holds the Big Core's drawings in the arcade's style
  (9.3).  Banks 42-45 (pages 84-91) hold the pieces of Konami's other
  graphics loads (9.5): 28,320 bytes in pages 84-87.  Pages 81 and 83 are
  unused.
* Bank 27's second 8K (page 55) holds `nx_tur.asm`, the code that draws
  stage 5's turrets and skeletons, every stage's shots, stage 6's brains,
  the ghosts of pieces leaving at the left, stage 8's electricity, the
  ending's zoom and the Big Core's blocks (9.3), with its variables (code
  to 7514), and stage 6's tables from 7600 (its sprite drawings and the
  sizes and places of the brains' and chains' sprites, made by
  `nx_pack.py`); `lo_tur` and four short calls in bank 8 map it at 6000
  (a jump table at 6000-600E).  Its data are in the second 8K of other
  banks, which it maps at 4000 (MMU2) while it reads them and puts back
  after: page 57 (bank 28) holds our sprite drawings 65 on (9.6), page 59
  (bank 29) stage 8's electricity, pages 61 and 63 (banks 30 and 31) the
  ending's zoom.
* Bank 8's buffers sit above its code (which ends below 2000): Konami's
  sprite patterns as last sent and the character enemies' 4-bit patterns
  (2000-32FF), the scenery objects' flags (3300-333F), the boss pieces'
  positions and kind (3340-335C, 9.3), the number of sprites the ghosts
  and the Big Core's core add to them (335D), the changed-pattern flags,
  line-coloured sprites, the volcano rocks' pattern and the sprite
  attributes (3440-3A5F), the stage's table of our drawings (3B00-3B3F),
  the character enemies' palettes and frames (3C70-3CA5), our drawings'
  palette bytes (3CA6-3CFF), the character enemies' colour bytes
  (3D00-3FBF), and the stage's palette, the pool's working bytes and the
  fade's (3FC0-3FFA).  The code does not fit below 2000 whole: the pieces'
  pattern maker, their sprite writer with its tables, the call into
  `nx_tur.asm`, and a few short routines it and the sprite colours use, are
  assembled into four free parts of this map, 3360-3434, 3448-34E6,
  3A60-3AE3 (the dissolve's fade) and 3B40-3C38.  The code below 2000,
  with its buffers, ends at 1FFD.
* Bank 12's first 8K (page 24, otherwise unused and not in the `.nex`)
  holds the store of character enemies' patterns (1.1.3, 9.3): 32 patterns
  at 0000-0FFF, their keys at 1000-113F, mapped at 6000 (MMU3) only while
  it is read or filled.  Fixed memory (Next only) holds the slots' keys
  (`nx_ckey`) and the code that uses them (`nx_cchk`, `nx_cput`).
* Sprite patterns: 0-63 are Konami's; 64-85 the character enemies lifted
  out; 86-95 stage 8's bolts or the Big Core's core; 96-101 the MSX2
  patch's line-coloured sprites; 102 the volcano rocks; 103 takes the rest
  of a send the interrupt cut short; 104-127 the boss blocks, shared by
  the Big Core, stage 3's and stage 4's pieces, stage 6's brains, stage 8's
  bolts and the ending's zoom, never two of them at once.
* Sprite palettes 14 and 15 change with the stage: stage 5's enemies;
  stage 6's brains and stage 7's amoeba in 15; stage 8's bolts and the
  ending's zoom; the Big Core's colours while it is on screen, the stage's
  again after.
* The CPU runs at 28 MHz (NEXTREG 07h).  The game runs at 30 ticks a
  second, the original's rate on a 60 Hz MSX (two frames a tick at
  59.94 Hz): screens are at most 2, 2, 1 frames apart in turn (`lo_tick`,
  `PACE_30`), and the 128K's adaptive pacing (6.8) leaves a tick undrawn
  only when the game falls behind 14 eighths of a frame a tick (28.6 ticks
  a second).  The cap matters: without it a fast enough machine runs a
  tick every frame.  `NEM_PACE=25` builds the earlier pacing (screens at
  least two frames apart, the 128K's rhythm of 15 eighths, about 26.7 ticks
  a second).  Up to 1.1.2 a screen took about 1.3 frames to draw (ZEsarUX,
  stage 1), so the 1-frame slots were missed, the game ran right at the
  pacer's threshold and it left ticks undrawn (about 3% over the loop, 17%
  in stage 1's opening); 1.1.3 draws in about 0.7 of a frame (the sprite
  changes below) and leaves almost none undrawn.  ZEsarUX by
  default holds this `.nex` at 14 MHz (its turbo limit applies when the
  file is loaded); `--allowturbotbbluerom` lifts it.
* At 60 Hz (NEXTREG 05h bit 2, which the Next's NMI + 3 toggles; frames
  then have 262-264 lines and come 60 times a second) the game keeps its
  50 Hz speed (1.1.3, `nx_hz`, read each frame): screens are 2 frames
  apart (30 ticks a second), the pacer's rhythm is the same in 60 Hz
  frames (`pace_t`: 17 eighths instead of 14), and Konami's sound driver
  is left out one frame in six, so the music keeps its tempo.

### 9.3 Drawing

* **The background** is drawn on Layer 2, a byte a pixel, only the cells
  that changed, as on the 128K.  During a stage a cell is copied from the
  **character pool** (`lo_pcell`, `lo_cmap`): every character of every
  stage as an 8 by 8 block of Layer 2 pixels, each different block once
  (1,806 blocks in banks 33-40), with a map per stage (bank 32, and bank
  47 for the bonus stages: the block of each character of each third; bit
  7 of a block's number marks a block of our drawings).  The pool is the
  Next's character artwork (9.5).  A
  pixel is a Layer 2 palette entry: the stage's 16 colours at 0-15, our
  drawings of the enemies Konami draws with characters (9.6) their own
  palettes at 20h-CFh, and scenery redrawn in the arcade's colours the
  stage's scenery palette at D1h-DFh (9.6).  The status line (rows 22-23)
  is drawn from stage 1's map, whatever the stage, in entries F0h-FFh,
  which hold stage 1's 16 colours from the start (9.5).  A cell is drawn
  instead from the store of character rows (9.2), each pixel its MSX
  colour number, for a character a graphics load has changed since the
  stage loaded (its bit in `tile_cdirty`/`tile_pdirty`, set by the Next's
  native loads, 9.5, and by the stars' twinkle, and cleared by
  `lo_apply`), one the map has no block for (the stars, F6 and F7), and
  on screens that are not a stage.
  The ship's ordinary shot is characters F8-FB (one for each 2-pixel
  step), which Konami writes into the map and takes out again, so the pool
  draws it like the scenery.  In play the store changes only for the stars,
  the Big Core and the dissolve.  The stars: every tick, Konami's 0:475B
  (`blink_native`) writes the star's row into the pattern store (row 0 of
  F6 and F7 in each third, the star mid-cell, 10h, since the hardware
  scroll moves it) and marks them; `lo_render` compares those rows with the
  ones it last drew (`lo_starpat`) and draws every star cell again when
  they change.  The Big Core (stages 1-6): when it arrives, 1:7CBD calls
  0:4A6D, whose load (`nl_bigcore`, at 0:4A8A) puts its graphics over
  characters 44-67 and A1-DB (all but BE) in every third; those that change
  show Konami's boss from the store until the next stage load.  On the
  screen before each stage only the bottom third, the status line, comes
  from the pool (`lo_pool` 2); the other two thirds hold Konami's font for
  the turn message.
  Copying a block is 8 `ldi` a line, each line's address set afresh (in
  column 31 the copies carry into the next line's address).  `nx_smoke.py`
  checks that the pool is in use and that the Next's code bank still holds
  its code as built.
* **Konami's screen dissolve** (after the stage 8 brain and, when its
  secret is not found, the stage 7 boss; 6.6) eats the colour and pattern
  tables over about 35 ticks.  On the Next, Konami's chunks (3:A765,
  `dz_chunk`) are applied to the store as Konami applies them to the video
  chip's tables, and the screen is a fade to black instead
  (`lo_fadestep`): from the dissolve's first chunk, which sets `dz_on`, to
  the next graphics load, which clears it (every native load does:
  `nl_save`), the pool draws every character whatever the store holds,
  and the Layer 2 palette fades in 21 steps
  for the stage's 16 colours, palettes 2-12 and the stage's scenery
  palette.  The step follows how far Konami's dissolve has gone
  (`lo_fprog`: E1A0, the pass; E1A2, the mask; E1A1, the quarter of the
  table; 32 quarters in all, a quarter a tick), so the fade ends when
  Konami's dissolve does.  Each channel of each colour is scaled by
  (21 - step) / 21 and rounded (`LO_FMAP`, a level-to-level table for the
  step), so a colour keeps its hue and every colour reaches black at the
  same step; colours of different brightness change at different steps,
  so something on screen changes at nearly every step.  The first version
  (until 5 November) took one level off every channel every 4 screens
  drawn: seven steps, with the dim colours gone after two or three, which
  showed as a few separate steps.  Taking one level off one channel at a
  time gave 21 steps but shifted every pale colour's hue at each step, and
  was dropped.  What Konami's dissolve spares stays: the status line,
  in its own entries (F0h-FFh), which are not faded, and the stars
  (characters F6 on), which `lo_cell` draws in entries E0h-EFh, holding
  the stage's 16 colours unfaded.  Konami's logic runs as before, so the
  timing is unchanged; the next load puts the palette back (the next
  stage's, or after the stage 8 brain the ending's).
* **The smooth scroll.**  When Konami's map moves a character, the screen is
  shown 7 pixels to the right of it, and the gap closes by a pixel a tick
  through Layer 2's X scroll (NEXTREG 16h).  Layer 2 is used as a circular
  buffer: Konami's row moves (0:46A1) turn the port's copy of the map and
  its dirty bitmaps instead of redrawing.  The X scroll for the play area
  is the origin column * 8 less the fine offset (0-255); a line interrupt
  at line 176 resets it for the status rows (below), and the left 8 pixels
  are clipped.
* **The interrupts.**  The Next has two: the frame interrupt and a line
  interrupt at line 176 (`nx_regs`: NEXTREG 22h, 23h).  Both come to `isr`,
  which tells them apart only by alternation (`nx_tog`, flipped at each).
  The frame interrupt runs the sound (`lo_snd`, which keeps MMU2, MMU3,
  MMU6 and MMU7 and puts the ordinary map in for `run_sound`), and
  `nx_frame` sets Layer 2's X scroll for the play area (the shown screen's)
  and, when a new screen has been shown, sends its sprites (`lo_sprflip`).
  The line interrupt sets the scroll to 0 for the status rows.  The copper
  is not used.  On the Next an interrupt that comes while interrupts are
  off is lost.  A lost interrupt leaves the play area at scroll 0 for a
  frame (the whole scenery jumps sideways) or the status rows scrolled, and
  puts the alternation out of step until `nx_frame`, which reads the raster
  line (NEXTREG 1Eh, 1Fh), finds itself at lines 176-183 and puts it back.
  (ZEsarUX reads line 176 at the line interrupt; Xpeccy+ reads another, so
  on some machines that check may never act.)
  So nothing that runs during play may disable interrupts for long.  (The
  Big Core's patterns, sent from the main program, once did; see below.)
  Konami's sound request (`pide_sonido`, 0:4A02-0:4A11, on every shot and
  explosion) disables them while it puts a request in the sound queue; on
  the Next, `NEXT_PATCH` puts `call snd_hold` and `call snd_free` in place
  of its `di` and `ei` (they set and clear `snd_busy`), and while
  `snd_busy` is set `run_sound` leaves Konami's driver (`m7_8063`, which
  reads the queue) for that interrupt and still calls `nx_frame`.  Until 8
  November this `di` was the longest stretch in play with interrupts off,
  and the scenery jumped sideways for a frame now and then (1.0N too).
  The Next's code reads a Next register in two steps: it selects the
  register (an `out` to 243Bh) and reads it (an `in` from 253Bh).  The
  interrupt selects registers too (`lo_snd`, `nx_frame`), so one that
  comes between the two steps would make the read return another
  register.  The main program notes the register in `nx_sel` before it
  selects it, and the interrupt selects that register again before it
  returns (`isr`), as it puts back the 128K's paging from `port_now`
  (6.2).  The reads are `lo_apply` (MMU7) and, through `tu_rreg` in
  `nx_tur.asm`, `tu_bsend` and `tu_s8` (MMU2, put back after use),
  `tu_bcq` (MMU2 and the palette control) and `tu_s8pal` and `tu_znew`
  (the palette control).  All run with interrupts on.  Until 8 November
  the five in `nx_tur.asm` read with no guard; a bad read of MMU2 in
  `tu_bsend`, put back as MMU2, left another 8K page at 4000-5FFF over
  Konami's code, and the game crashed (1.0N too).  1.1 held interrupts
  off round each pair instead; an interrupt lost there left the status
  rows with the play area's scroll for a frame, seen in the Big Core
  fight.  The only `di` left in the Next's own code is on the title
  screen (`lo_logopal`).
* **Sound.**  Konami's driver plays the music on the first AY, as on the
  128K.  Its effects (sounds below 16h) go on Konami's channel C, under
  the music: a three-channel tune (sound 26h and over: the start tune,
  stage 1's theme, the boss tune) holds channel C, and a sound is played
  only if its number is not below the one already there, so effects were
  lost.  The Next has three AYs (TurboSound, NEXTREG 08h bit 1, set by
  `nx_init`; port FFFD written with FFh, FEh or FDh selects the first,
  second or third), and the effects play on the second.  `NEXT_PATCH`
  puts `call nx_pick` in place of `encola_sonido`'s choice of channel C
  (0:4A3C), so an effect goes into one of three channel records of the
  port's own (`snd_rec4`, laid out as Konami's at E010): one already
  playing the same sound, else a free one, else the one with the lowest
  sound number, which Konami's own comparison then replaces or keeps.
  After Konami's driver, `run_sound` calls `nx_sfx`, which selects the
  second AY, swaps in its mixer byte (`snd_mix2`, for Konami's E043) and
  runs Konami's channel routines (`m7_8181`, or `m7_8206` for a silent
  channel) over the three records, then puts the first AY back.  While
  `nx_ay` says another AY is selected, the WRTPSG stand-in skips its copy
  of the first AY's registers (`psg_regs`) and writes every time.  With
  the game paused (E047), the second AY's volumes are set to 0.  The
  third AY is not used.  Konami's stage themes from stage 2 on (16h-25h)
  use two channels and leave channel C to the effects; the sounds that
  take all three channels and cut the music (the ship lost, 47h; the
  explosion after stage 8's last boss, and the bonus target, 41h; the
  screen going dark after a boss, 3Eh; a core destroyed, 3Bh) do so on
  the MSX too, and the music starts again after them.
* **Sprites** are the Next's: Konami's 64 patterns as 4-bit patterns, each
  sprite's MSX colour as its palette offset, with attributes and changed
  patterns sent when the screen they belong to is shown.  Konami's
  patterns change only with a graphics load, so since 1.1.3 all 64 are
  compared with the copy last sent only after one (`spr_new`, set by
  `nl_done` and `nx_clear`), and one in turn on other screens as a
  safety net (`lo_sproll`).  Sprites are drawn
  the scroll's distance to the left so they stay where Konami puts them;
  objects Konami moves with the scenery (its helper at 2:9251, which the
  Next notes) move with it instead.  The sprite clip window (NEXTREG 19h,
  set in `nx_regs`) is lines 0-175, so no sprite is drawn over the status
  rows.
* **Enemies drawn with characters** (Konami's objects with byte 11 set) are
  taken out of the map copy, the background put back under them, and drawn
  as sprites at their pixel positions.  Only rows 0-21 are handled: the map
  has no background for the status rows.  An enemy four characters in size
  is made from the pool (`lo_pconv`): its frame (the object's byte 12; its
  characters on the screen can lag a tick behind it) gives its four
  characters (Konami's frame table, 5:91D1, copied into bank 26), and each
  character's block, in the third it is drawn in, becomes a quarter of a
  4-bit sprite pattern.  Where a block is one of our drawings, the
  enemy's pixels in the stage's colours are left transparent and the
  sprite takes the drawing's palette; otherwise each pixel keeps its value.
  An enemy whose top is on row 21 (Y A8h-AFh, as the hatch saucers of
  stage 1 can be) has its bottom half on Konami's row 22, which the MSX
  does not show either: only its top two characters are taken, and made
  from the pool the same way, the bottom of the sprite left transparent.
  A character a load has changed since the stage loaded, or one with no
  block, and Konami's two-character objects (byte 11 from 2 to 5:
  characters A1-A2, BF-C0, 58-59 or 60-61, which the Big Core's load
  supplies), are converted from the store instead (`lo_conv`).  The
  pattern made from the pool depends only on its four blocks, so since
  1.1.3 it is kept (`nx_cchk`, `nx_cput`): each of the 22 slots notes the
  blocks it was made from, and a slot whose enemy has the same blocks next
  time is left as it is; otherwise a store of the last 32 patterns made
  (page 24) is searched and a match copied in, and only a pattern in
  neither is made.  Both are emptied by each graphics load (`nx_cclr`).
  Enemies with two blocks (row 21) are made every time.  Stage 1's opening
  has 9 different patterns; making them took about 0.46 of a frame a
  screen, comparing Konami's patterns 0.19.
* **The Big Core** (the boss of stages 1-6) is drawn with characters,
  11 by 8, and Konami moves it a whole character at a time: in from the
  right one step every 8 ticks, then up or down a step every 3 to 5 ticks
  (by the difficulty) in runs.  `lo_boss` takes its characters out of the
  Next's copy of the screen the same way, keeps them as 24 sprites of
  16 by 16 (made again only where its characters change: a face, the eye),
  and shows them as far towards Konami's next step as the step's countdown
  has come (E78A in the run, E003 on the way in).  On the way in, Konami
  clips the boss at the right edge (0:48F7), so the columns still past it
  are in no screen copy; `lo_bfill` builds the whole boss from Konami's own
  tables (the body 1:7EE6, the eye 1:7F3E by E789, the mouth 1:7F62 by the
  face in E786, placed as 1:7E70 places them) and those cells are taken from
  it, so the gliding boss reaches the edge instead of stopping short of it
  by the glide.  Its patterns are made (in `lo_btmp`, its own buffer) and
  sent from the main program with interrupts on: the frame interrupt makes
  and sends patterns of its own (`lo_sprflip`, through `lo_tmp` and
  `lo_conv`, which keeps its row in its own code), so it sets `lo_brst` and
  the pattern is made and sent again; `lo_sprflip` leaves pattern 103
  (unused) selected, so the rest of an interrupted send lands there.  The
  next step is always
  known then, so the boss glides without falling behind the game; Konami's
  collisions still use its whole-character position.
  The blocks show the arcade's Big Core rather than Konami's characters
  (`local/tools/arcade/bigcore_make.py`, from the arcade's bosses sheet,
  kept as `spec/nx_bigcore.py`; page 82).  When a block's characters
  change, `lo_bconv` jumps to `lo_bart`, and `tu_bc` (in `nx_tur.asm`)
  sends the arcade's block instead of converting Konami's.  The body is
  trimmed to the 88 pixels of Konami's 11 characters, its cut edge shaded
  a step darker.  The four blocks of the mouth (6, 7, 12 and 13) show the
  arcade's wall strip, four bars and a ball, with as many bars as Konami's
  life / 4 (E789) gives walls, as Konami's own wall characters follow it
  (1:7E91).  The core is a sprite of its own (pattern 86, palette 14, 36
  pixels right and 24 down from the boss's corner, from `tu_bspr`): grey
  when the boss comes, a step bluer every two hits (Konami's life starts
  at 22), and gone once the core is destroyed (E155) or the face has gone
  (E786 2).  The blocks are in palette 15.  While the Big Core is there
  (stages 1-6, E151, E780 1) `tu_bcq` gives palettes 14 and 15 the
  arcade's colours, and the stage's again after (`lo_pal1415`).  Konami's
  collisions are unchanged.
* **Stage 3's boss pieces** (Konami's boss 1 in E152; boss 6, one piece,
  on later rounds) are up to eight round pieces in the slots at E780 (16
  bytes each: byte 0 alive, Y in byte 3 and X in byte 5, whole pixels,
  byte 6 which of two drawings).  Konami moves them a pixel at a time but
  draws each as 4 by 4 characters into the map at the character cell
  holding its position (2:86D9; 1:6936 saves what was there and 1:6A37
  puts it back after the map comparison), so they jumped 8 pixels at a
  time.  `lo_pieces` (from `lo_tick`, after `lo_chars`) takes their
  characters out of the Next's copy of the screen with the background put
  back, as the character enemies are, and records each piece's position
  and drawing; `lo_qspr` shows each as four 16 by 16 sprites there.  Their
  six patterns (the two drawings, 2:86F1 and 2:8701, share their right
  halves) are made once a boss from the pool (`lo_qmake`, third 0's
  blocks; the stage has the same in all three) into the Big Core's
  patterns, which is never on screen with them, and sent as the Big Core's
  are.  Without the pool the pieces stay in the map as before.  Konami's
  collisions use its own position, which is now the sprites'.
  Stage 4's mid-boss (boss 5) is the same machinery: up to eight flyers
  in the same slots, each moved 2 pixels a tick along a fixed route (2:8D7C
  on) and drawn by Konami as 4 by 3 characters (2:8E45, through 0:490C)
  in two drawings that alternate every 4 frames (2:8E5F, 2:8E6B; the
  middle row's first character, BC or C2, tells `lo_pieces` which).
  Konami writes the drawings' blank corners as character 00, blanking the
  background there; lifted out, the corners are transparent instead.  Its
  six patterns are the top halves of the two drawings and the shared
  bottom row; each kind has its own tables of characters and patterns
  (`lo_qch`, `lo_qpat`; `lo_qch5`, `lo_qpat5`).
  A piece that leaves at the left edge (bosses 1 and 6: 2:85C3, 2:8630,
  2:8520, its X gone below 0; boss 5: 2:8E1D, past F0h) is taken off by
  clearing only byte 0 of its slot, so it vanished as it touched the edge.
  `tu_qtick` (from `lo_qgh`, at the start of `lo_pieces`) watches each
  piece's steps, and one that goes this way glides on off the screen as a
  ghost, at the same step and rate, drawn as `lo_qspr` draws the pieces,
  until it is 32 pixels past the edge.  A piece that is shot keeps its X
  on the screen and is not ghosted.  The ghosts are only drawn: nothing
  collides with them.  `LO_QG` (335D) holds how many sprites they add, and
  `lo_qspr` adds them (through `lo_bspr`) after the pieces.
* **Stage 5's turrets and skeletons** slide out of the floor, the ceiling
  or a ledge, and Konami draws them a character row a step, so they rose
  8 pixels at a time.  `nx_tur.asm`, called after `lo_cells` (`lo_tur`),
  draws them again a pixel step at a time, with the pool for the whole
  stage only (`lo_pool` 1).  Each is a rectangle of Konami's characters, of
  which Konami draws only the rows that are out; it is shown as Konami has
  it in its map (blocks from the pool) moved back by what is left of the
  step, inside its rectangle, which is cleared first and its cells marked
  to be drawn again from the map (both screens), so it never shows where
  Konami has not put it.  The turrets (Konami's four of E880: 4 by 4
  characters, a step every 5 ticks, 3:B145, drawn by 3:B431) are shown
  back by 8, 6, 5, 3 and 2 pixels with 5 to 1 ticks to go; a turret
  sliding on takes in the row it has just left, if Konami has left it
  blank.  The skeletons (the small pieces of E700, types 1, 3 and 4: 5 by 5
  characters, Konami's next drawing every 8 ticks the same skeleton a row
  further out, 3:B2DA, 3:B3EA, drawings at 3:B537) are shown back by 8 to
  1 pixels.  Konami makes their last step as the skeleton is out and no
  longer counts ticks for it; the Next counts that one itself.  The
  skeleton's open mouth, once out, is Konami's change of drawing.
* **The shots and the laser.**  Konami writes the ship's shot and laser
  characters into its map over what it keeps, so on the MSX each such cell
  is a black 8 by 8 with the shot through it, which showed as black boxes
  over the scenery and over the enemies drawn from the pool.  In every
  stage `nx_tur.asm` (`tu_shots`, after stage 5's work) draws each of their
  cells again: what was under it, as `lo_cells` draws a cell (`lo_tcell`),
  then the shot's lit lines over it as `lo_cells` draws the shot's
  character, with a black line above and below them so the beam stays
  visible.  What was under a cell is what Konami saved (Konami's six shot
  slots at E260: a shot's covered character at byte 8, the laser's from
  byte 17 on; Konami's map no longer has stage 5's turrets and skeletons
  by then); a cell that stage 5's smooth drawing painted this screen is
  overlaid as it is.  An ordinary shot's cell is found from its Y, in byte
  3 of its slot, and its X, in byte 5, as Konami's 0:571B makes its map
  address from them (3:A299; `tu_shots`, `tu_find`).  Until 8 November the
  two were taken the other way round, so the shot was looked for in the
  wrong cell and kept Konami's black box, which showed over scenery (1.0N
  too).  Enemies drawn with characters and lifted out as
  sprites have the scenery under them, which Konami's lifting already
  gives.
* **Stage 6's brains** (Konami's boss 2; its step 1:7F74, its drawing
  2:8290) are two brains, at E790 and E7C0, each with up to two chains of
  seven balls (2:8308 places them from the brain).  Konami draws them with
  characters at the cell of their position, and moves a brain only in
  steps: every 10 ticks, 8 pixels left and 8 up or down towards the ship
  (2:8144); a chain aims at the ship, Konami choosing its next drawing
  every 5 to 8 ticks (2:8113, 2:81D5).  `tu_btick` (from `lo_pieces`,
  through `lo_brain`) takes their characters out of the screen copy with
  the background put back, and shows them as sprites (`lo_qspr`,
  `lo_bspr`): a brain as far towards its next step left as its count has
  come, its rise or fall gliding over the ten ticks after the step that
  made it, and each ball moving from its place in the chain's old drawing
  to its place in the new over 6 ticks, relative to the brain shown.  The
  drawings (13 patterns: the big brain's two frames, the small ones, the
  two balls) and the sizes and places of each drawing's sprites are
  stage 6's tables in page 55 (7600 on); they are sent to the boss blocks'
  patterns once a boss.  A brain Konami takes off at the left edge, and
  any left when the boss ends, glides on off the screen as a ghost with
  its chains (`tu_ghost`, a copy of its state in `tu_gh0` or `tu_gh1`, so
  that a new brain in the same slot does not cut it short).  Konami's
  collisions use its own positions.
* **Stage 8's electricity.**  The brain at the end of stage 8 is drawn
  with characters in the arcade's style (9.6), and Konami's tendril
  characters are blank; the electricity is six bolts of sprites from the
  brain to Konami's six sockets (its type 11h objects, 2:88D3, placed by
  the boss script at 2:88F8), 29 sprites in all (patterns 104-127 and
  86-90), made by `local/tools/pool/art/st8_brain_make.py` and kept as
  `spec/nx_st8.py` (page 59).  `tu_s8` shows them from 40 columns before
  the scroll stops (distance 19Fh) and moves them with the scenery.  Each
  bolt is shown 5 ticks in 8, at random, and swaps its cyan and green
  (palettes 14 and 15) now and then, so the bolts flicker and arc
  throughout.  When a socket is shot (its object no longer of type 11h
  where it was), its bolt flickers sparsely for 16 ticks and goes.  The
  fight ends on Konami's timer, or when no objects are left (2:889C); in
  Konami's dissolve the bolts' palettes fade with the room (`tu_s8pal`,
  through `LO_FMAP`), and they go when the dissolve clears the map.  Only drawn:
  Konami's game is unchanged.
* **The ending's zoom.**  In steps 4 and 5 of Konami's ending (E1D1;
  0:4BD8, 0:4C16) the Vic Viper flies from the exploding base towards the
  camera in 6 drawings of characters (A1h-EAh, rows 6-11, columns 10-21,
  table 0:4EDA), shown for 64, 40, 16, 12, 8 and 4 ticks.  `tu_zoom`
  takes those characters out of the screen copy (blanked in
  `name_shadow`, their cells marked) and shows the ship as sprites in 16
  sizes instead, drawn from a head-on model
  (`local/tools/arcade/vv_model.py`, `vv_zoom_make.py`; kept as
  `spec/nx_vvzoom.py`, pages 61 and 63), palette 15.  The size follows
  Konami's own timing: the tick of the zoom is the start of Konami's
  drawing (E1D9) plus that drawing's length less the ticks it has left
  (E1D2), and a table gives the size for each of its 176 ticks.  Each
  size's drawings are sent as it comes, to patterns 104-114 and 116-126
  in turn, so the size on screen keeps its own.

### 9.4 Konami's instructions the Next build takes over

| Site | Konami's | The Next's | Why |
|---|---|---|---|
| 0:46A1 | `ldir` (the scroll's row moves; the 128K's `nm_ldi31_full`) | `lo_shiftrow` | The circular buffer (9.3). |
| 2:9251 | `ld a,(E100)` (se_corre_con_el_scroll_ocho) | `lo_gnd`, which notes the object and does the same | Objects moved with the scenery. |
| 0:4100, 0:414B | `call 422A` (carga_los_graficos_de_la_fase, which the native build makes `nl_stage`) | `lo_stage`, which calls it, then copies the stage file into the store (`lo_apply`) and, in bonus stages 10-12, puts in character 44's colours (`nx_bonusfix`) | 9.5. |
| 0:544F | `call 5874` (the screen before each stage, 0:53C8; left out of the native build, kept for the Next by `NEXT_KEEP`) | `lo_prestage`, which puts in the coming stage's palette and bottom third | 9.5. |
| 2:99A1, 2:99C3, 3:A19B | `ld a,(E200)` (the ship's state, choosing its sprites and where its second goes) | `lo_shipst`: with the MSX2 graphics, always the plain ship, as the patch's code does | 9.5 (the shield). |
| 0:4A02, 0:4A11 | `di`, `ei` (pide_sonido, round its request into the sound queue) | `call snd_hold`, `call snd_free`: `snd_busy` set and cleared, and the interrupt leaves Konami's sound driver meanwhile | An interrupt that comes while they are off is lost (9.3). |
| 0:4A3C | `ld l,34h` (encola_sonido: an effect to channel C's record, E034) | `call nx_pick`: one of the port's three records, played on the second AY | Effects not lost under three-channel music (9.3). |

Each runs Konami's own instruction or routine where the build keeps it, so
the game's logic is unchanged: Konami's 0:5874 is left out of both builds
(the native load at 0:53D4 puts in its graphics), and while a request goes
into the sound queue the interrupt leaves alone the driver that reads it.
`gen.py` checks Konami's bytes at each site and stops if one has moved or
changed.  Konami's status-line loader (0:5851), where `lo_marcador` was
hooked before, is left out of the native build; the native loads of the
title, the ending and its status line call `lo_marcador` instead (9.5).
`lo_marcador` gives those two screens Konami's original look (the TMS9918's
colours, none of our drawings, the status line from the copies; `lo_enh`
0, which means only that no stage's graphics are loaded).  Nothing else
uses it: game over keeps the stage's graphics and gives its text stage
1's colours (`nx_gopal`, 1.1.3).

### 9.5 The graphics

The Next's graphics began as those of the MSX2 patch "Nemesis - Gradius
ENHANCED" V1.01, which keeps Konami's game and its stage loader and changes
the data: new characters per stage (the play area is still the MSX's
Graphic mode 2 layout, two colours per row of 8 pixels, so the Next draws
it the same way), new sprites, a 16-colour palette per stage, a new status
bar font, colour changes, and sprite colours set line by line by its own
code (it runs the MSX2's sprite mode 2).  They were read from the patched
ROM once (3 November 2026, `local/tools/msx2/msx2_extract.py`: it applies
the IPS to `nem.rom` and replays the patched cartridge's stage loader for
each of the 8 stages with `extract.py`'s replay of Konami's, plus the
patch's status-bar font routine and its sprite load, recording which bytes
of video memory the load writes) and kept in `spec/nxgfx/`.  Later the
same day the characters became a single set of artwork, the character
pool (9.3): `local/tools/pool/make_pool.py`, run once, made it from the
stage files and our drawings of the character enemies (9.6), exactly as
the build had been making it, and cut the stage files' characters down to
those Konami rewrites in play.  `spec/nxgfx/` holds, ours to change:

* `pool.bin`: the character pool, 8 by 8 blocks of Layer 2 pixels, a byte
  a pixel (a stage colour 0-15, palette * 16 + colour for our drawings, or
  D1h-DFh, a colour of the stage's scenery palette), each different block
  once (1,806 blocks);
* `maps.bin`: 2K a stage (1-8), two bytes for each character of each
  third: the 8K page of its block in the `.nex` (66 on: bank 33 on, 128
  blocks a page) and its number in that page; page 0: none;
* `scenery.bin`: 32 bytes a stage (1-8), the stage's scenery palette:
  Layer 2 entries D1h-DFh as Next 9-bit colours (entry D0h unused), for the
  scenery redrawn in the arcade's colours (9.6);
* `bonus.bin`, `maps_bonus.bin`, `scenery_bonus.bin`: the bonus stages'
  stage file, maps (2K a stage, 9-12) and scenery palettes (below);
* `stageN.bin` (N = 1-8, 16K each): video memory 0000-37FF as the patch's
  stage load leaves it, now only for the sprite patterns and the stars
  (characters F6 and F7, which Konami rewrites in play), the palette as
  Next 9-bit colours, the sprite line-colour tables, and a
  write mask, a bit per byte (the bytes outside it are filled in when the
  game is built, below);
* `logo.bin`: the title logo and its palette;
* `patches.txt`: data bytes in Konami's own ranges (the font and its
  colours, object and shot colours, the bosses' colour tables, map
  pieces), as bank, address, Konami's byte and ours.

`nx_pack.py` packs them into banks 16-41, 46 and 47 with each stage's
sprites in fire colours (9.6) and the redrawn sprite enemies, marking the
maps' blocks of our drawings (bit 7 of the number), and puts each stage's
scenery palette in its tables (9.6); it also puts `native_next.py`'s
pieces in banks 42-45 (below).  A `.nex` built from the stage files
was checked byte for byte against one built from the patch's IPS before
the IPS was dropped from the build, and the pool and maps against the
build that made them before they became the artwork.  The pool is changed
with `local/tools/pool/put_blocks.py STAGE MODULE.py`, where the module
gives blocks for characters of the stage's thirds (and optionally its
scenery palette): each block is stored once and the stage's map pointed at
it, other stages untouched.

**Konami's own loads.**  The native build leaves Konami's graphics loaders
out, so the Next gets what they wrote when the game is built, and puts it
into its store (9.2) at the same hooks as the 128K's native loads:

* *Stage loads.*  `nx_pack.py` completes each stage file with Konami's own
  stage load, replayed in msxsim after the stage before it in play
  (`native_next.stage_files`, through `native_sets.stage_vram`): a byte the
  mask leaves out takes what Konami's load writes there, or else what the
  stage before it left (such bytes are never shown).  At a stage load
  Konami's 0:422A is `nl_stage`, which on the Next loads nothing itself;
  `lo_stage` then has `lo_apply` copy the stage file's colour, sprite
  pattern and pattern tables whole into the store.  The bonus stages share
  stage 9's file.  Konami's loads of stages 10-12 differ from stage 9's
  only in character 44's colours in each third (24 bytes, outside the
  mask), which `nx_bonusfix` puts in after `lo_apply`.
* *The other loads* (the title, the Big Core in stages 1-6, the screen
  before each life, game over, the status line in the ending's step 6, and
  the ending).  `native_next.py` replays Konami's loaders in msxsim, on a
  ROM with the data bytes of `patches.txt` in, and records the bytes they
  write, which are always whole characters.  The pieces are stored raw in
  8K pages 84-91 (banks 42-45): 13 pieces, 28,320 bytes, the Big Core's the
  same in all six stages.  A piece of colours or patterns is a 96-byte mask
  (a bit for each character of each third) and the 8 bytes of each marked
  character; a piece of sprite patterns, an 8-byte mask and the 32 bytes of
  each marked pattern.  The Next's entries in `native.asm` (`nl_title`,
  `nl_bigcore`, `nl_prestage`, `nl_gameover`, `nl_marcador`, `nl_ending`)
  map each of the event's pieces at 4000 and copy it into the store
  (`nx_chars`, `nx_sprites`), marking in `tile_cdirty` or `tile_pdirty`
  each character whose bytes change, so that the pool leaves it to the
  store (9.3).  The title, the ending and its status line also call
  `lo_marcador`, which puts the TMS9918's colours back (for the title, the
  logo's colours too).
* *Boot.*  The boot's clearing of video memory (FILVRM from 0000) clears
  the store too (`nx_clear`).

**The bonus stages** (9-12) were at first left out: the patch has
graphics for them (Konami's loader puts them in, as for the other stages)
but no palettes, and the pack covered stages 1-8, so they showed Konami's
own characters and sprites in the palette and sprite line colours of the
stage before.  Their graphics were read from the patched ROM in the same way
(`local/tools/pool/make_bonus.py`, run once; the replay checked against
openMSX captures of the patched cartridge for all four: every byte it
writes matches, apart from characters Konami animates).  The four loads
differ only in character 44's colours, the balls, so they share one stage
file (`bonus.bin`, bank 46: the patch's sprites, among them the bonus
stages' own score sprites at patterns 56-63, stage 2's palette, which the
characters suit, and the patch's line-colour tables).  Each character
became a block in the pool, with our art on top from stage 2, whose
characters the bonus stages share: where a bonus character is (pattern and
colours) one of stage 2's and stage 2's block for it is ours, the bonus
stage takes that block, matched by content because the patch draws some
of them under other numbers (AE and AF are its 45 and 46; AA-AD and B0-B5
the turrets' 02-05 and 08-0D).  The balls are our arcade sphere (stage 2's
character 44) in each stage's colours: green, yellow, blue and magenta,
in its own scenery palette entries (DAh-DDh).  `lo_apply` takes stages
1-12: for 9-12 it maps the shared stage file, the stage's map in bank 47
and its tables (`TAB_BONUS`, after Konami's frame table), and stage 2's
fire copies.

**The status line and the ship keep stage 1's colours.**  The patch draws
the status line with each stage's characters and palette, so it looked
different from stage to stage; on the Next it is drawn as in stage 1
throughout the game, bonus stages included: `lo_cell` takes the bottom
two rows from stage 1's map (`lo_cm1` makes `lo_cmap` use it) and puts
their pixels in Layer 2 entries F0h-FFh, which `lo_init` fills with stage
1's 16 colours once.  The ship's line-coloured pattern took the stage's
palette in the same way (stage 3's turned its red canopy brown); `lo_init`
also puts stage 1's colours in sprite palette 13 (entry D2h stage 1's
colour 1, D3h-DFh its colours 3-15: entry D1h, like entry 1 of every
palette, is a Konami sprite colour's), and `lo_mship` builds the ship's
pattern in that palette, its colour 1 as entry 2, which its line colours
do not otherwise use.

After each stage load, `lo_apply` also sets the palette and the sprite
line-colour tables, loads our drawings' tables and turns the pool on.  The
screen before each stage (at a new game and after a life is lost) shows
only the status line, which the native load at 0:53D4 (`nl_prestage`)
puts in as Konami's loaders wrote it; `lo_prestage` (at 0:544F) then gives
it the coming stage's palette, puts in the stage file's own bytes for the
bottom third (those its mask marks), and draws that third from the coming
stage's pool (the status line itself as in stage 1, above), so the status
line is not shown in the TMS9918's graphics until the stage loads.  It
leaves the other two thirds alone: they still hold the font for the
two-player turn message.

The patch's title logo is not made of characters: it is a 16-colour
bitmap (256 by 48 pixels, stored as it is in the patched ROM at 30000h,
its palette at 2E520h), which the patch shows by switching the top of its
title screen to a bitmap mode.  On the Next, the title's native load
(`nl_title`) calls `lo_marcador` with A = 1, and `lo_logopal` gives the
logo's palette Layer 2 entries 10h-1Fh; `lo_logocell` then draws the
logo over rows 3-8 in place of Konami's (rows 4-8), and the text is
Konami's, unchanged.  A column of the logo shows while any of Konami's
logo cells in that column is not blank, so the logo leaves column by
column with Konami's curtain at the start of a game.

The shield: Konami draws it by replacing the ship's second sprite, its
white layer, with the barrier, 8 pixels ahead.  The patch changes that code
(2:99A1, 2:99CF, and 3:A19B, which with the shield puts the second sprite
8 pixels right) so the ship always keeps its own two sprites, and draws
the barrier as a separate sprite, white and grey on alternate screens.  With
the MSX2 graphics the Next does the same: `lo_shipst` gives Konami's code
the plain ship's state, and `lo_shield` adds the barrier (Konami's pattern
for it, by the stick and the blink, at the ship's Y and X + 8).  Without
them the shield is Konami's.  The replay was checked against video memory
captured from the patched cartridge in openMSX at the end of each stage
load: every byte it writes matches, apart from characters Konami animates
in play.  Sprite colours follow the patch's: fixed colours for most of
Konami's entries (alternating screen by screen where the patch's two
sprite lists differ), Konami's colour for enemies, and line-by-line colours
for the ship and some capsules, drawn as 4-bit patterns.  The patch marks
the line-coloured ones by colour bytes 60h, 70h and 80h (its tables of
line colours); 80h, which it gives the stars stage 5's skeletons release
(Konami's object type 1Ch, colour 9 in the original), is not the MSX's
early clock bit with colour 0, so for Konami's objects (sprite entries
10-21) it takes table 80h and no 32-pixel shift (`lo_isec`, `lo_lcod`).
Read as the early clock, it showed the stars 32 pixels to the left of
where Konami puts them, away from the skeletons' mouths.

### 9.6 Departures from the patch

* The options and the ship's explosion are drawn in red, orange and
  yellow, after the arcade game: the patch's green and brown options, and
  its explosion in the ship's colours, were not liked.  The fire copies
  colour each sprite pixel by its depth: the edge red, the next pixel in
  orange, deeper yellow.
* The stars still twinkle; the patch stops them.
* The rocks the volcanoes throw in stages 1 and 4 are drawn in the same
  fire colours (`lo_rock`: Konami's objects of type 0Fh with sprite pattern
  CCh, all sharing one converted pattern).  The patch instead switches to
  a red palette for the volcano sections, which recolours the terrain as
  well; that is not done.
* **Stage 1's enemies are redrawn** after the arcade game's sprites, which
  the patch's single-coloured sprites (one colour a line) cannot match.
  Each drawing is Konami's MSX frame (from the original ROM, not the
  patch's), 16 by 16, redrawn or recoloured after the arcade sprite that
  plays its part, 4-bit, in sprite palettes 2-10 (entries 2-15; entry 1 of
  every palette is a Konami sprite colour's).  The sprites: the explosion
  (Konami's patterns 30-33), the shot (34), the pod (35-39: Konami plays
  its frames forwards then back), the robot (40-43), the jet (44-46) and
  the walking cannon (52-63: three drawings, each also upside down, mirrored,
  and both; the gaps inside its outline are drawn in colour 11, opaque
  black in palettes 2 and 3, so the scenery does not show through them).
  The enemies Konami draws with characters (frames of its table
  at 5:91D1, four characters each): the fans, the hatch saucers, the
  turrets on the ground and on the ceiling (six aims each), and the two
  capsules.  Those that leave a capsule are red, as in the arcade: a sprite
  of the pod, jet, robot or walker with byte 14 set (Konami's colour 8)
  takes the next palette, its red twin; Konami draws such turrets with red
  characters of its own (a second set of frames), which take the ordinary
  turret's drawing in the red palette.  Stage 2 adds the enemy that
  materialises in columns (Konami's type 8, patterns 47-50, after the
  arcade's growing ring) and its turrets, whose frames have the pixels of
  stage 1's, in a blue tint (palette 11).  Stage 3 adds its spinning disc
  (its own patterns 47-50, after the arcade's frame for frame) and its
  spoked wheel (55-58), which the arcade has no match for: Konami's shapes,
  shaded in palette 4 and lit from the top left so that the light stays
  put as the spokes turn.  Stage 5's own enemies have no match in the
  arcade either: Konami's shapes are shaded, lit from the top left, the
  holes inside the MSX pattern as darker shading.  The crescents (its
  patterns 40-43) are salmon and orange, with a red twin for those that
  leave a capsule; the balls (52-59: clusters of three and the single balls
  they break into) are pink, their inner ring of dots a band one step
  darker; the bone claws (60-63) are gold and the stars (51) ice blue.
  They use two more sprite palettes, 14 and 15 (13 is the ship's), which
  `lo_pal1415` loads with the others.  Stage 6's robots (Konami's type 0Ch,
  frames 29-2C, characters EC-F5, in the pool) are the arcade's, in
  palette 4; Konami's four frames share their left half, so all four take
  the arcade's first frame's left half (`local/tools/pool/art/
  st6_robots_make.py`).  Stage 6's brains and their balls are the arcade's
  brain (its second frame the first a quarter turn round, the small brains
  reduced from it) and two of its balls, purple and grey-brown, drawn as
  sprites (9.3).  Stage 7's amoeba (Konami's type 0Dh: patterns 56-59 as it
  wobbles, 55 when it has stopped, the doughnut; type 14h bursts through
  60-63) is the arcade's pink cell.  Stage 6 and stage 7 each give palette
  15 colours of their own (`TAB_PAL6`, `TAB_PAL7`).  Up to 90 drawings now
  (`NART`): 1-64 in page 51, 65 on in page 57.
  `local/tools/arcade/gen_art.py` made the sprite drawings from the arcade
  sprite sheets once; they are kept as data in `spec/nx_art.py`, so the
  build does not need the sheets.  `nx_pack.py` stores them in bank 25's
  second 8K (page 51) and their tables in bank 26's (page 53): the
  palettes, Konami's frame table (9.3), and for each stage a map of
  Konami's patterns to our drawings, for stages 1-12.  A drawing is of one
  of Konami's patterns as a stage loads it (stage 1's, or a later stage's
  own: `nx_art.STAGED`); a stage gets it in every slot whose pattern, in
  Konami's own load, has that content, and an enemy's drawings only when
  all that enemy's patterns are there (so no enemy is drawn half ours,
  half Konami's).  The drawings of the enemies Konami draws with
  characters are in the character pool (9.5): the quarters of each
  frame's drawing, in its palette, as the blocks of that frame's
  characters, with the character's own background where the drawing is
  transparent, in each stage and third where the characters were stage
  1's.  The turrets follow Konami's table of their frames (2:9205: for
  each stage four sets, the capsule ground, ground, capsule ceiling and
  ceiling turrets; bits 5 and 6 of the turret's byte in the stage's turret
  script, 2:9262, pick the set).  Konami draws every turret with one
  design, stage 1's ordinary turret on the ground and on the ceiling, and
  the same in red characters for those that leave a capsule.  The first
  placement took a set only where its characters were stage 1's in all
  three thirds, which gave stages 1, 2 and 4 our turrets and left stages
  3, 5, 7 and 8 with the patch's: their middle thirds hold other turret
  pieces under the same numbers, or the red turret throughout.  Those four
  were then placed by content (`local/tools/pool/art/turrets_ours.py`): a
  set takes our pieces in each third where every frame's image in Konami's
  own load is stage 1's ordinary turret, either as it is (our drawing as
  stage 1 has it) or with the colours stage 1's red turret gives it (our
  drawing in palette 7, as stage 1's and stage 2's red turrets are).  The
  colour decides, not the set: stage 7's capsule turrets on the ceiling in
  the top third share the ordinary ones' characters and stay blue, as
  Konami draws them.  Stage 2's ordinary turrets keep their blue tint.  On
  the Next, `lo_apply` loads the palettes and the stage's tables
  (`LO_OVR`, `LO_APAL`, in bank 8 at 3B00-3B3F and 3CA6-3CFF);
  `lo_sprflip` sends our drawing in place of a mapped Konami pattern, and
  `lo_arc` (from `lo_ecol`) gives any sprite showing one its palette.
  Character enemies Konami moves with the scenery (the turrets, the
  capsules) stay in the map and are drawn from the pool as the scenery is;
  those lifted out are made from the pool too (`lo_pconv`, 9.3), and `.co`
  gives them their palette (`LO_OPAL`).  So an enemy looks the same in the
  map and lifted out, including frames Konami builds from other frames'
  characters (frames 29-2C, from the fans').  `lo_marcador` clears the
  tables for the title, the ending and its status line.  Konami's colour
  changes (a flash) do not show on our drawings, and the capsules' glint
  (Konami animates their characters) is not drawn.
* **Scenery in the arcade's colours.**  Stage 2's bricks, balls, neck and
  hanging clusters (characters 44-4F, A2, A3 and A5) are the arcade sheet's 8
  by 8 tiles, and stage 3's Moai heads and stone are Konami's characters
  recoloured in the arcade's style, shapes kept (each drawing assembled
  and shaded as a whole: the heads in the arcade's yellows, lit from the
  top left, the darker parts in its golds, the rubble in its creams).
  These need more colours than the stage's 16, so each such stage has a
  scenery palette of its own, up to 15 Next 9-bit colours in Layer 2
  entries D1h-DFh (`spec/nxgfx/scenery.bin`; `nx_pack.py` puts it in the
  stage's tables at + 40h, `lo_apply` loads it, `lo_fadestep` fades it).
  The bonus stages take stage 2's, their balls recoloured (9.5).
  Stage 5's bones, which the patch draws in cream, grey-beige and black and
  shades by stippling, are shaded instead on a 9-step ramp from ivory to a
  warm brown in the stage's scenery palette (D1h-D9h), lit from the top
  left by each shape's outline, the stippling smoothed and the patch's
  black shading inside the bone turned into dark steps of the ramp; the
  eggs keep their blues.  `local/tools/pool/art/st5_scenery_make.py` made
  the blocks from every screen sampled in a run through the stage (each
  character takes, pixel by pixel, the result it gets most often).
  Stage 7's conveyor belts are in the arcade's style: a lilac band with a
  darker rim, and white hollow rings, the arcade's links, in place of the
  patch's green beads (`local/tools/pool/art/st7_belts_make.py`, from the
  screens of a run through the belt section, `st7_screens.z`; each
  character takes a ring where most of its appearances have one).
  Stage 8's brain is the arcade's (the bosses sheet), put at full size in
  Konami's 8 by 8 characters (rows 7-14, columns 12-19 where the scroll
  stops) a pixel right and three down from their middle, where none of it
  falls outside them, in the stage's scenery palette; its sockets (one
  character each) take the arcade's socket, and Konami's tendril
  characters (A1-BF on that screen) are blank, the electricity being
  sprites (9.3).  Each of these characters is used once on that screen
  and nowhere else in the stage (`local/tools/pool/art/st8_brain_make.py`).
* **The enemy hatches** (Konami's background objects of types 1 and 2,
  each drawn as 4 by 4 characters from the table at 1:6370, a second set
  of characters once it has been shot, 1:7AB0) keep the patch's drawing,
  but their darkest colours are lighter, since they merged into the black
  background: in stages 1, 2 and 4 the blue hatch's dark navy (stage
  colour 4) is (1,3,3) and the shot hatch's dark brown (stage colour 6)
  (4,3,0), in the stage's scenery palette (D2h, D3h); stage 8's ceiling
  hatch's dark olive is (2,3,1) (DDh).  The arcade's hatch was tried in a
  mock-up and not taken.  `local/tools/pool/art/hatch_light_make.py` made
  the blocks.
* **Stage 2's brick-row end caps** (characters A1 and A4) are blank.  In
  play Konami puts them at the two ends of each row of bricks (the map
  dumped from the running game: A1 45 46 ... 45 46 A4, A4 47 48 49 ...
  49 A1); on the MSX they are tips a few pixels wide, and the patch draws
  them as short slabs, which showed as bricks cut off.  They are not wall
  (characters 77 and above never collide in stage 2 or the bonus stages,
  2:9857), so blank matches what collides.
* The status line and the ship keep stage 1's colours throughout (9.5).
* Konami's screen dissolve is a fade to black (9.3).
* The patch recolours the Big Core at each boss (it switches pattern
  table and rewrites colours there); the Next shows the arcade's Big Core
  in the arcade's own colours at every boss, with its wall strip in the
  mouth and its core a separate sprite that turns bluer as it is hit
  (9.3).
* Stage 8's brain is the arcade's, with electricity from it to the
  sockets that flickers, arcs and goes with each socket shot (9.3); the
  patch keeps Konami's characters there.
* The ending's zoom has 16 sizes of a new drawing of the Vic Viper for the
  patch's 6 (9.3).
* Stage 3's and stage 4's boss pieces and stage 6's brains glide off at
  the left edge instead of vanishing as they touch it (9.3).
* Konami's objects of colour 0 flash between two colours, as in the patch
  (8 and 0Ah; 5 and 0Ah in stage 3).  Stage 3's Moai rings (type 0Eh)
  flash between 5 and 0Dh instead, blue and purple (`lo_c0`); the stage's
  palette has no red.

### 9.7 Checks

`verify.sh` ends by building the `.nex`.  `release.sh` builds the `.nex`
as well as the tape and snapshot, and, if ZEsarUX is available, plays it
for a minute (`nx_smoke.py`: the game must start, its scroll must move, the
stage graphics must be in, the background must be drawn from the character
pool, and the Next's code bank must still hold its code as built).  It
plays a copy made invulnerable (Konami's 1:75F0, the ship's death, made a
RET, found by its bytes in the listing) at 28 MHz: before 1.0 it played the
`.nex` as it was, and the ship usually died before the second scroll
sample, so the check failed on every build.

The whole game is played in ZEsarUX, headless and driven through its
remote protocol, by the tools in `local/tools/nexttest/`.  `fulltest.py`
plays an invulnerable copy through the game (the route with every bonus
stage, the ship put on each hidden target, or the plain route; one loop or
two).  At every stage change it checks that bank 8's code, `nx_tur.asm`'s
page and the read-only data pages (the native loads' pages 84-91 among
them) still hold what the `.nex` has, and that the pool is on; it dumps the
store, the marks, the name table and both Layer 2 screens at each stage
start, through each boss and through the ending.  `nx_ftcmp.py` compares
two runs' dumps at the points both reach: the characters on show, the
sprite patterns, the marks, Layer 2's pixels, and the colour entries one
run uses and the other does not (which points to a drawing fault rather
than timing).  `hunt.py` is `fulltest.py` with breakpoints on a stray write
(to 01B1 in the code bank, or a stage number above 12), and `replay.py`
adds ZEsarUX snapshots to start attempts from.  `nx_poll.py` dumps at
each change of Konami's state or stage, and `nx_pollcmp.py` compares two
such runs.  These compare memory, not the picture: a wrong scroll split, palette or hardware sprite
passes them, and ZEsarUX's timing is not the hardware's.  An earlier
`fulltest.py` was run on 1.0 before its release; the native Next build was
run through the bonus route and through two loops of the plain route and
compared with 1.0N.  The lockstep checks of section 4 cover Konami's logic,
which the two builds share.

### 9.8 Known limitations

* Konami's collisions with the scenery work on whole characters, while the
  scenery is shown up to 7 pixels to the right of where Konami has it, so a
  collision can look up to 7 pixels off.
* Objects Konami moves 8 pixels at a time by its own code, rather than
  through its scroll helper, still move in steps (the Big Core, stage 3's
  and stage 4's boss pieces, stage 5's turrets and skeletons and stage 6's
  brains excepted, 9.3).
* Stage 8's electricity is only drawn: touching it does nothing, as
  touching Konami's tendrils did nothing (characters 77h and above
  collide only in stages 3 and 4).
* A second Konami cartridge (F0F4) is not supported, so its extra sprites
  are not loaded.
