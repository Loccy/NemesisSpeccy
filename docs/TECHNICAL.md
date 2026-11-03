# Nemesis for the ZX Spectrum 128K: technical description

Version 0.110 (1 November 2026). 

## 1. What it is

A port of Konami's MSX cartridge Nemesis (RC-742, 1986) to the standard
128K Spectrum, running Konami's own game code.  The project's background,
its departures from the MSX original and how to play it are in the
[README](../README.md); this document describes how the port works.

The Z80 code of the cartridge is relocated to the Spectrum's memory by a
generator (`reloc/gen.py`), and a platform layer (`spec/`) stands in for
the hardware the code talks to: the memory mapper, the BIOS routines it calls,
the video chip (TMS9918), the sound chip (AY-3-8910, the same family as the
128K's) and the keyboard and joystick.

The game logic is Konami's, unchanged except where it meets the hardware.
A test build matches the MSX original byte for byte in Konami's RAM, tick by
tick (section 4).

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

The build has three stages, all driven by `build.py`:

1. **Relocation.**  `reloc/gen.py` reads the cartridge ROM and an annotated
   disassembly of it, and writes Konami's code back out as assembly source
   with every address symbolic, laid out for the Spectrum's memory
   (`konami_spec.asm`, plus `konami_spec_stubs.asm` for calls between
   memory banks).  Section 6.1 explains why and how.
2. **Generated tables.**  `tables.py` writes the colour-matching tables and
   the keyboard decoder (`tables.asm`); `gen_fullcmp.py` writes an unrolled
   comparison routine (`fullcmp_gen.asm`, 6.4).
3. **Assembly.**  sjasmplus assembles `plat_spec.asm`, the platform layer,
   which includes all of the above and the rest of the port's own code, into
   a 128K snapshot (`nemesis.sna`).  `build.py` then sets the snapshot's
   stack pointer to AEA0: sjasmplus leaves it at 6000, directly above
   Konami code at 5FFE-5FFF, which a loader that starts the snapshot through
   its stack (some hardware loaders may) would overwrite.  AD00-AE9F is zero
   at load and rebuilt by the boot code, which sets SP to AEA0 itself.

`make_tap.py` then turns the snapshot into a tape (6.13).

Requirements: Python 3, sjasmplus (1.21 used), SkoolKit (10.1 used; the
simulator-based checks and the tape check), Pillow (screenshots), gcc (to
build the ZX0 compressor).  The scripts find the tree from their own
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
  `ZX0` (only `make_tap.py` needs it).

```
python3 build.py              # nemesis.sna (+ .sym, .lst), the fast edition
python3 make_tap.py           # nemesis.tap from nemesis.sna
sh release.sh 0.110           # the release, tape and snapshot, in release/
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
| `NEM_INVERT=0` | Dense tiles stored as converted, not inverted (6.6). |
| `NEM_PACE=palmix` | Experimental 2,2,2,2,1 frame pacing. |
| `NEM_PACE=25` (`nxbuild.sh`) | The Next build at the earlier pacing, about 26.7 ticks a second instead of 30 (9.2). |
| `NEM_TAP_RAW=1` | (make_tap.py) an uncompressed tape. |
| `NEM_ANY_DISASM=1` | Build from a disassembly other than the pinned version. |
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
* **The video memory the game wrote.**  The Spectrum has no TMS9918, so the
  port keeps copies ("shadows") of the parts of the MSX's video memory the
  game uses: the name table (which character is in each cell), the
  pattern and colour tables (what each character looks like) and the sprite
  patterns.  Each shadow is compared with the MSX's real video memory.

One kind of difference is expected and allowed: a byte pair holding an
*address*.  The port's code lives at different addresses, so a pointer the
game stores in RAM (to a routine, a table, a script) legitimately differs.
The lockstep knows where everything moved (from the build's symbol
table) and accepts a difference when the two values are the same address
in each machine's layout.  Anything else is a mismatch.

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
project, modelling only what Nemesis touches:

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
is: the drawing (turning the game's character map and sprites into Spectrum
pixels and attributes) is the port's own code and has no MSX counterpart to
compare with.  Those parts are checked against models instead, on the
release build in the Spectrum simulator:

| Tool | Checks |
|---|---|
| `check_names.py 240` | Map tracking (6.4): after every tick the port's copy of the screen's character map equals Konami's map buffer, apart from regions still queued for comparison. |
| `check_screen.py 120 0 2` | After the cells are drawn, every cell of the hidden screen equals its character in the converted tile set. |
| `check_sprites.py 60 0 3` | After the sprites, the hidden screen equals the tiles plus Konami's sprites ORed in, with the sprite cells coloured by the rules of 6.7.  With `MISSILE=1` the ship has the missile and fires along the ground, for the missile's rule.  With `EDGE=1`, sprites crossing both edges (and just inside them) are added to Konami's list for each checked drawing, at every pixel position in turn, and taken out again. |
| `check_tiles.py 60 0 15` | Every converted tile is a faithful two-colour version of its MSX pattern and colours (the power-up bar and the nuke capsule, which are designed by hand, excepted; the title logo is checked against `logo_tile`'s rule, and the stage colour rules of 6.6 against their model, `stage_rules.py`). |
| `test_convert.py` | The tile converter against an independent Python model, on 1,381 real tiles. |
| `test_keys.py` | Keyboard decoding against the key map. |
| `test_kempston.py` | Kempston detection (both buttons), its decoding, and hold-to-select. |
| `test_tape_trap.py` | The tape loaded as a DivMMC-type interface loads it from its card (LD-BYTES trapped at 0562). |

With `NEM_ALL=1` the checkers (and `emu.py`) play the whole game instead of
the start of stage 1: the ship is invulnerable and, once play starts, the
game's own HYPER cheat and a second option are called, as the lockstep's
`HYPER=1` does.  `NEM_ALL=1 check_screen.py 3000 0 4` and the like then
cover every stage and boss on the release build: 3,000 seconds is the whole
first loop of eight stages, the end of the loop and the second loop to
stage 4.  All five checkers pass over that run (0.89); for 0.90, `check_tiles`
and `check_screen` pass over 2,450 seconds (the first loop and the start of
the second).  With `NEM_TARGETS=1` as well, the ship is put on every hidden
target, so the bonus stages are played: for 0.91 `check_tiles`,
`check_screen`, `check_names` and `check_sprites` pass over 2,300 seconds of
that (the whole route, bonus stages included, to the second loop's stage
1), and `check_tiles` and `check_screen` over 2,300 seconds without it.
`NEM_MORTAL_BONUS=1` lets the ship die once in each bonus stage; the four
checkers pass over 1,500 seconds of that (a death in each).

For 0.93 (sprites clipped at the edges) `check_sprites` passes over 1,500
seconds of that every tick (2,382 sprites crossing an edge), and with
`EDGE=1` over 240 seconds with all weapons (3,363 edge sprites), 60 with
the missile and 30 of ordinary play.

Two blind spots, both learnt from the red stars of 0.97-0.99 (development
notes, 0.99a).  Code that exists only in release builds (the twinkle skipped
on undrawn ticks, 6.5) is never run by the lockstep, which uses the test
build.  And `check_tiles` checks each pixel against the tile's own ink and
paper, not whether that ink and paper were the right choice, while
`check_screen` compares the screen with the port's own tile set: a wrong
colour choice passes both.  `check_route.py` counts the star tiles'
attributes by stage for that reason.  Also, when checking by screenshot:
the screen on display can be a tick or two behind Konami's sprite list, so
identify what is shown from the screen's own pixels.

The tape is checked separately: `tap2sna.py -c machine=128 -s <plat_boot>
nemesis.tap out.z80` simulates loading the whole tape at signal level, and
the resulting memory must match `nemesis.sna` byte for byte outside the
screens.

### 4.8 Running the checks

`./verify.sh` runs the checks of 4.7 and a 3,000-tick lockstep (about 40
seconds on the machine it was developed on); run it after any change.  The converter test reads Konami's
graphics as loaded into VRAM, which `gfxcap.py` captures from the ROM into
`vram_states.pkl`; `verify.sh` makes the capture if it is missing, and it
stays out of the repository.

How far a checker run gets: in the all-stages mode with every target
touched (`NEM_ALL=1 NEM_TARGETS=1`), 600 seconds of play reaches stages 1-3
and the bonus stages 9-10; the fast edition reaches stage 8 at about 1,480
seconds and the second loop at 1,700, and 3,000 seconds takes it to the
second loop's stage 7 (the smooth edition is about 14% behind).
`check_route.py SECONDS OUT.json` times the route stage by stage, counts
the star tiles' attributes by stage (which `check_tiles` does not judge: it
checks the pixels against the tile's own ink and paper), and measures the
stack's deepest use (a marker below Konami's stack, BF80-BFEF) and the IM2
table's state.  Run the `HYPER=1` lockstep after changes
that could affect later stages (the generator's tables, memory layout,
paging).

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
* The port's drawing needs memory of its own: a converted copy of every
  character the game uses, copies of the MSX video memory, and the second
  screen.

Fixed memory:

```
4000-5AFF  screen 0 (bank 5)
5B00-7B30  MSX bank 0 code, relocated
7B40-7BFB  sprites crossing the left and right edges (spr_edge, edge_pat)
7C00-7C58  data moved out of bank 0
7C58-7C5D  far_dz_pat (the dissolve's far call)
7C60-7FFF  rarely run code (contended memory): BIOS stand-ins, keyboard,
           boot, the title text writer, Kempston, hold-to-select
8000-ACFF  platform: paging, mapper emulation, VDP stand-ins, map tracking,
           interrupt, main loop, pacing, tile conversion, renderer, bulk
           VRAM writes, tables, far-call stubs, the
           ship's patterns, buffers (name_shadow, dirty bitmaps, region
           lists, star lists, DRAWN)
AD00-AE00  IM2 vector table; AEAE jp isr; stack below AEA0
AEB4-AEF3  dc_buf (bulk VRAM writes)
AF00-BFFF  Konami's RAM (MSX E000-F0FF, displaced by -0x3100)
```

Banks switched in at C000 (the port's names for them in brackets):

```
A  bank 0  MSX banks 1 and 2 (game code)
B  bank 3  MSX bank 4 (graphics source) C000-DFFF and bank 5's used part
           (8000-98B8) E000-F8B8; the colour fitter F900-FD03; conversion
           cache FE00-FFFF
C  bank 4  MSX bank 3 (game code) C000-E061; the title's full stop and
           text E062-E0EE; the stage colour rules, the dissolve's colour
           chunks and logo_tile E0EF-E75C; the adaptive pacing (pace_adapt,
           0.110) E75D-E79D; copy of the MSX colour table E800-FFFF
D  bank 6  MSX banks 7 and 8 (sound driver and tunes, E000-E3DC); the
           full map comparison E400-E7FF; copy of the MSX pattern table
           E800-FFFF
E  bank 1  MSX bank 11 C000-DFFF; bank 12 A000-A2A7 (the scripts of stages
           1-8) E000-E2A7; bank 9's used part (9B3F-9FFF) E2A8-E768 and
           bank 10's (A000-AF28 less A758-AAA5) E769-F691, contiguous;
           code moved from bank 2 (8290-839E, the boss pieces) FB04-FC12;
           and in the gaps, bank 12's parts for the bonus stages: the
           scripts of stages 9 and 11 EEC1-F100 (where bank 10's
           A758-AAA5 would be), of stages 12 and 10 F692-F9F1, and the
           bonus stages' ending table and records (B2E4-B64B) FC13-FF7A
7  bank 7  screen 1 C000-DAFF; the converted tile set DB00-F5FF; star_check,
           spr_pmap, spr_colour, tile_post, stage_seen, attrs_keep F600-F7CE;
           sprite patterns F800-FFFF
```

Banks 5, 9, 10 and 12 are only partly carried: only what the game reads
now the attract cycle is gone (measured with `bankreads.py` over whole
games, and for the bonus stages with every target touched), and every range
left out identified.  Bank 5's 98B9-9BE3 is loaded only when the game finds
Konami's TwinBee cartridge (RC-740) in another slot, which it cannot here
(the slot read stand-in answers FF); 9BE4-9FFF is padding.  Bank 10's
A758-AAA5 is the high-score table screen of the attract cycle.  Bank 12
past B64B is padding.  Banks 6 and 13-15 are empty (all FF) and never read.

Free space (0.110), about 1,540 bytes in all:

| Where | Bytes | |
|---|---|---|
| Fixed 8000-ACFF | 63 | padding before page-aligned tables and buffers: 96D5-96FF (43, after `dz_flag`, before `tables.asm`), A173-A17F (13, before `ship_pat`'s 32-byte alignment), AAFD-AAFF (3, after the two 3-instruction ways into bank C), A2FE-A2FF (2), A8FE-A8FF (2, after `conv_dz`) |
| Low fixed area | 38 | 7B31-7B3F (15), 7FF3-7FFF (13), 7BF8-7BFF (8, after `spr_edge`), 7C5E-7C5F (2) |
| Bank 0 (page A) | 290 | FEDE-FFFF (it holds sjasmplus's default UDGs at FF58, which nothing uses) |
| Bank 1 (page E) | 677 | F101-F20E (270), F9F2-FB03 (274), FF7B-FFFF (133) |
| Bank 3 (page B) | 130 | F8B9-F8FF (71), FDC5-FDFF (59) |
| Bank 4 (page C) | 98 | E79E-E7FF |
| Bank 6 (page D) | 232 | E718-E7FF |
| Bank 7 (page 7) | 0 | `dz_flag7` fills it to F7FF |

Bank 3's padding (MSX 3:BE66-BFF4, 399 bytes, carried in bank C) could be
dropped too, a generator change.  Fixed memory is where space is tight: what
it has is in pieces between aligned tables, so new code there has to be
placed by address around them (the 43 bytes before `tables.asm` are now
the largest piece).  The 0.94 count (505 bytes in fixed memory) had gone stale: 0.95 to
0.99 used 94 of the bytes before `tables.asm`, and 0.100 took 191 (the
ship's selector and patterns, with 13 bytes lost to their alignment, and
the title's full stop); 0.102 took 87 more (the title's tune), and 0.107
94 (the dissolve: `conv_dz`, `far_dz_pat`, `dz_flag` and the hooks in
`ensure_tile`, `tick_tiles` and the decompressor), with about 770 more in
banks B, C, D and 7.  0.109 moved the title's full stop (46 bytes) to bank C
and `far_dz_pat` to the low area, and spent the room on the scroll and sprite
changes and `spr_vis` (the 32 bytes at A1E0).  0.110's adaptive pacing is
in bank C (65 bytes) with a 6-byte stub in fixed memory; the fast edition's
counter, no longer assembled, gave back 3 bytes more than that cost.  Anything that need not be fast
goes into a switched bank with a call from fixed code, or takes over an
existing instruction.

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
software, converting the game's character map and sprites into Spectrum
pixels and colours, and doing it fast enough.  That is where nearly all the
design effort and running time goes (6.4-6.8).

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
pointer rests after its last row) maps to that end.  Two traps only the
bonus stages reach: stage 12 reads the per-stage graphics table (5:92E3)
one word past its twelve entries, into the next table, so that word must be
relocated as stage 12's graphics list; and one entry of the bank-5 pointer
table `graficos_por_fase` is 0:42FB, an empty stream in bank 0, which must
be relocated as a bank 0 address (left as a number, it pointed into the
Spectrum's screen).  Konami's RAM moves from E000 to AF00.

The other tables in `gen.py` are changes to the code itself: `SPEC_PATCH`
(the hardware boundary: video writes, the map upload, the decompressor, the
star twinkle, the sprite uploads, the front end), `NM_SITES` (map writers
that report what they wrote, 6.4), `ITEM_PATCH`, `ITEM_MOVES`, `CLONES`,
`DATA_MOVES` (single items replaced or moved), and `LD_A_R` (the randomness
sites pinned in the test build, 4.3).

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
map pieces, graphics sources, the title graphics), `map_update` switches in
the Spectrum bank holding that data.  For bank 10 (the boss pieces' tables,
in page E with the code that reads them) it does so only when the write
comes from fixed code (the end-of-loop explosion, 0:4AFF); from paged code
(the stage 5 boss, 1:7FA9) the page already in stays.  `set_page` writes
port 7FFD, keeping the bit that chooses the displayed screen.

Every write to port 7FFD goes through `out_page`, which first notes the
value in `port_now`.  The interrupt pages in the sound driver and then puts
back exactly that value, so code that borrows a bank for a moment (to
update a copy of the video memory, say) does not need to turn interrupts
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
does this natively (`blink_native`).  Rather than redraw every star cell as a
changed character, the port treats stars as a separate layer: `star_check`
confirms that the star characters differ from the empty character only in
their top row and colour, those changes are kept out of the dirty bitmaps,
and `draw_stars` erases the stars each screen showed (its drawn lists) and
draws the current ones from lists of star cells.  With one tick in two
drawn, `blink_native` runs only for a tick that will be drawn (except in test
builds, whose pattern copy the lockstep compares every tick).

### 6.6 Tiles and colour

The game changes character shapes and colours as it goes (each stage loads
its own, and some animate), by writing to the video chip's pattern and
colour tables.  The port keeps copies of both (in banks D and C).  It cannot
draw from them directly: an MSX character has two colours per row, eight
rows, while a Spectrum cell has one ink and one paper for all eight.  So
every character is *converted* into a Spectrum tile (8 bytes of pixels and
an attribute) before it can be drawn, and kept in a converted tile set in
bank 7 (one set per screen third, as on the MSX).

Converting is slow (tens of thousands of T-states per character), so it is
done lazily: a changed character is flagged and converted the first time a
cell needs it (`ensure_tile`).  The conversion (`convert_tile`, bank B)
tries the Spectrum ink, paper and brightness combinations and keeps the one
with the least colour error, then maps each pixel to the nearer colour.  A
character takes about 32,000 T-states on average and up to about 94,000
(0.106; the development notes have the profile).  A 16-entry cache in bank
B catches characters that switch back and forth.
When only a character's pixels change, `recolour_tile` keeps its ink and
paper (read from the converted set) and just maps the new pixels; a
character whose ink and paper are the same (it was blank when converted)
gets a full conversion instead.  In practice only the star characters take
this path (6.5; the 0.99a fix in the development notes).

After conversion (`tile_post`, bank 7):

* a tile with more than half its pixels set is stored inverted (pixels
  flipped, ink and paper swapped).  It looks the same, but its solid part is
  now paper, and a sprite passing over (which changes only the ink, 6.7)
  leaves the terrain's colour alone instead of turning a solid block of
  ground into the sprite's colour;
* the nuke capsule's characters (77-7A) are given bright cyan.  On the MSX
  both capsules are a white frame round a coloured core, which one colour
  per cell would make identical; the standard capsule (7B-7E) stays white;
* on the title (Konami's state 0 or 1), the NEMESIS logo's characters
  (8D-FF in thirds 0 and 1) are drawn by `logo_tile` (bank C) instead.  On the MSX
  each pixel line of the logo is one colour (white and grey for the frame
  and top band, then cyan, light blue and dark blue stripes), which the
  colour fit turned into a patchwork.  A cell with any cyan or light blue
  line is bright cyan and the rest bright white; light blue lines, and dark
  blue ones in a cyan cell, become a 50% stipple.  The letters' dark blue
  base shares its cells with the frame's bottom edge, so both are white.
  These characters get new patterns when the stage loads, so the game
  converts them normally again.

The power-up bar (third 2, characters 15-42 and 0C) is drawn to its own
design instead of converted (`barstyle.asm`): white letters on blue, the lit
box yellow on black.

In five stages, characters the colour fit drew badly are given hand-set
colours (`rules.asm`, bank C, reached from `tile_post` through
`stage_rules`).  A rule recognises its characters by the MSX colours in
them (for the stage 2 bricks and the stage 8 ladder, the character number
too) and either paints the tile afresh from its MSX pixels or changes the
colours the fit chose:

| Stage | Characters | Drawn as |
|---|---|---|
| 2, and the bonus stages 9-12 (the same characters) | The bricks (45-4B, only black, blues, grey, white) | Grey and white pixels solid, blue ones a 50% stipple; the left half of a 2x1 brick and of a flat bar, and the first and last thirds of a 3x1 brick, cyan, the rest bright white (the 3x1 brick's last third: the stipple only) |
| 10 (bonus) | Only the yellows, 8 or more pixels (the balls) | Yellow (not bright) on black, as the MSX's dark yellow |
| 3 | In the Moai section (to distance 0x195), a character whose main colour is a blue (the faces) or light red (the rocks) | The fit's white or grey becomes cyan, or magenta |
| 6 | Only the reds (the brain) | White or grey becomes magenta, and the cell is bright |
| 7 | The formations (blues, cyan and greens) | Bright green dots (greens and cyan) on bright blue; a mostly black edge bright blue on black |
| 7 | The band (dark blue with grey or white, nothing else but black, light blue, cyan) | White (cyan, grey, white, and black pixels just above or below a coloured one) on blue; mostly black cells white on black |
| 8 | The pipes (only black, blues, cyan, grey, white) | A cell with a line of 4 or more cyan, grey or white pixels: those white, light blue a stipple, on bright blue; the rest bright blue on black; the ladder (58) bright white on black |
| 8 | The brain (black, dark red, light red, the yellows) | Where the fit chose red or yellow: white becomes magenta, yellow red, and the cell is bright |

The power-up bar and the score (third 2, characters below 44) are never
touched.  A rule's result depends on the stage, but a character keeps its
conversion until its pattern or colours change, and a new stage often loads
the same characters again unchanged; so when Konami's stage number changes
(`stage_seen`, run with every full map comparison) every tile is flagged
for a full conversion and every cell redrawn.  `stage_rules.py` is the
rules' model, which `check_tiles` checks the converted tiles against.

Konami's screen dissolve (MSX 3:A6C0, after the stage 8 brain and, when
stage 7's secret is not found, the stage 7 boss) ends a stage by eating the
screen: once through the colour table turning every background black, then
eight times through the pattern table taking one more bit of each byte
away, about 35 ticks.  Each tick changes about 190 characters, more than
the list of changed tiles holds, which the port treats as a load: every
changed character fully converted and the whole screen redrawn, at 1 to 2
ticks a second (18 seconds for the brain, 43 for the stage 7 boss, against
about 3.4 on the simulated MSX).  Since 0.107:
* each chunk is done natively (`dz_chunk`, page C, and `dz_pat`, page D,
  in place of come_un_trozo at 3:A765): the shadow is masked in place,
  EA00 is left as Konami leaves it, and each changed tile's dirty bit is
  set, its attribute flagged once at the end of the tick (`dz_flag7`);
* from the dissolve's first tick (`dz_mark`, at 3:A6C0) to the next
  graphics load or stage change (`dz_on`), a tile whose MSX rows all have
  a black background is redrawn by `dz_tile` (page B) instead of the
  colour fit: its foreground keeps the colour that showed it (the old ink,
  or the paper of a tile stored inverted), as ink on black, each row's
  pixels going to the ink if its colour is strictly nearer it, as in
  `cv_pixels`.  The stage colour rules leave these tiles alone (a hand-set
  stipple, for instance, goes solid as it fades), and `check_tiles`
  accepts them on their own ink and paper.

The dissolve now takes about 6 seconds after the brain and 7.5 after the
stage 7 boss on the fast edition (7 and 8.5 on the smooth), still about
twice the MSX: every changed tile on screen is redrawn and the whole screen
drawn on each drawn tick.

### 6.7 Renderer and sprites

The port draws into two screens: the hidden one is drawn while the other is
shown, then they swap (by flipping the display bit in port 7FFD), so the
player never sees a half-drawn picture.  Each screen has its own bitmap of
dirty cells, since each must catch up with every change.  Drawing a screen
(`render_frame`): redraw the cells under the sprites last drawn on that
screen (which erases them), update the star layer, redraw the dirty cells
from the converted tile set, then draw the sprites.

The sprites come from the game's own sprite list (MSX EC80): the same
32 entries of position, pattern and colour the game would give the video
chip.  Each 16 x 16 sprite is ORed into the screen, shifted to its pixel
position (right by 1-4 bits, or for offsets 5-7 left by 3-1 into the same
three bytes, which halves the shifting).  Erasing marks each row of a
sprite's cells in the dirty bitmap with one mask.  The cells it touches take its colour as their ink (over black
paper they also take its brightness; over coloured paper, an inverted tile,
they keep their own).  Sprites are drawn from the last to the first, so that
where two share a cell, the higher-priority one's colour wins.  Konami's list
is usually full, with most entries parked below the screen, so one pass
collects the entries on screen (up to an end marker) into `spr_vis`, and
the drawing works back through those (0.109).

A sprite's ink is chosen from its MSX colour (`spr_ink`, in `tables.py`; the
MSX's light blue, light red and light yellow are mapped to bright cyan, red
and yellow rather than to the nearest Spectrum colour, white), unless
`spr_pmap.asm` gives its pattern a colour of its own: explosions go yellow
then red, and enemy bullets stay white.  The option uses the explosion's
last pattern (132; magenta on the MSX), so options show red.

The ship is redrawn (0.100, `ship.asm`).  On the MSX it is two sprites at
the same place, Konami's patterns 0/4 (level), 8/12 (diving) and 16/20
(climbing): white, with a red canopy (a light blue belly when climbing) as
a second one-colour sprite, the only way an MSX1 sprite gets a second
colour.  Here the cells take one ink, so the second sprite cost a draw and
an erase for nothing.  The renderer gets every pattern's bytes from
`spr_patsel`: patterns 4, 12 and 20 are not drawn at all (since 0.109
`draw_sprites` drops them before looking up their colour), and 0, 8 and 16
come from `ship_pat` instead of Konami's table.  Since 0.105 these are
Konami's own outlines with the second colour shown in one colour: on the
level and diving frames, the red canopy becomes a black line inside the
ship's white outline (the canopy's top edge white, the line beneath it);
on the climbing frame, the light blue belly becomes a checkerboard stipple
under the solid white top.  (0.100-0.104 used redrawn designs with seams and
an outlined canopy; in motion, frames that differed much from one another
looked like a different ship at each change of direction.)  Konami's patterns stay in the copy of the video memory as the MSX
has them, so the lockstep is unaffected.  Patterns 0-23 are the ship's
alone: the same in the video memory after every stage's loader (12 stages,
`vram_states.pkl`), and over 900 seconds of play with the ship climbing
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
columns that show are coloured and recorded, so with 8 or more pixels off
screen a single column is.  Sprites are still drawn only when wholly below
the top edge.

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
(`pace_adapt`, bank C, called after each tick through `far_pace`): every
tick is drawn while the game keeps up with a rhythm of 15 eighths of a frame
a tick (about 26.7 ticks a second, near the MSX's), and a tick is left
undrawn while the game is behind that rhythm by more than a frame, but never
two in a row.  The balance (`pace_debt`, in eighths of a frame) is clamped
to between 4 frames ahead and 8 behind, so a slow stretch does not leave a
debt that makes a quiet one skip.  Screens are at least one frame apart.  In
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

Measured against the MSX original, simulated at 50 Hz with the same front
end and the same scripted play (invulnerable, fire tapped; its BIOS calls,
stubs in the simulator, charged an estimate of the real BIOS's time;
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
never idle.  A tick costs about 189,000 T-states against a budget of
141,816 for 25 a second: Konami's own code, sound included, takes about
76,000 (40%), the drawing about 38% (more than half of it the sprites),
and the map tracking, paging and video stand-ins most of the rest.  The MSX
gets its sprites and scrolling from the video chip.  Drawing one tick in
three reached 23.1 ticks a second under the old limits, but at 7.7 screens
a second.

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
running every frame (6.2).

### 6.11 Bulk video writes and decompression

When the game loads a stage's graphics it decompresses them straight into
video memory, writing each byte to the video chip's data port.  On the
Spectrum every one of those writes became a call into the port's video
stand-in, which made restarting after a death take 2.5 seconds.  So the
decompressor (`descomprime`) is reimplemented natively and writes through a
64-byte buffer (`dc_buf`), which brought the restart down to about a
second.  The
BIOS block routines (FILVRM, LDIRVM, LDIRMV) likewise work in runs, with one
bank switch per run.

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
0.100 had it after the copyright): `title_dot` gives the font's blank tile
0E, in the top third, a full stop, white like the rest of the text (in bank C
since 0.109, written through the LDIRVM stand-in, which copies via a buffer
in fixed memory, because its source is paged).  Row 0
is cleared when play starts, and the title writes it again after a game
over.

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

The tape is about 60 KB, about 6.5 minutes at normal speed.  The loading
screen is the MSX attract illustration, converted by `tape/make_loading.py`
(two colours per cell, checkerboard dithering in the ships).

## 7. Known limitations

* Sprites coming in from above the top edge appear only once wholly on
  screen.
* One colour per cell: sprites over sparse terrain (tree tops) recolour it,
  the ship's red canopy is a black line and its blue belly a stipple, and
  overlapping sprites share one colour.
* At a stage change, for at most one tick (until the next full map
  comparison notices the new stage), a cell redrawn then can show its tile
  in the previous stage's colours.
* Konami's screen dissolve (after the stage 8 brain, and the stage 7 boss
  when its secret is not found) takes about twice as long as on the MSX
  (6.6).
* Restarting after a death pauses for about a second while Konami's code
  decompresses graphics.
* The attract cycle (the illustration and demo play) is not carried.

## 8. Files

In `spec/` unless shown otherwise.

| File | Contents |
|---|---|
| `plat_spec.asm` | The platform: BIOS stand-ins, paging, mapper, video, map tracking, main loop, interrupt, boot, buffers; includes the rest. |
| `convert.asm`, `convert_e.asm` | Tile conversion, the cache, the star twinkle, tile flags, the dissolve's tiles (`dz_tile`). |
| `render.asm` | The renderer: cells, stars, sprites, erasing. |
| `vbulk.asm` | Bulk video writes and the native decompressor. |
| `barstyle.asm` | The power-up bar's design. |
| `ship.asm` | The ship's own patterns and `spr_patsel` (6.7). |
| `VERSION` -> `version.inc` | The version, and the title's line for it (`build.py`). |
| `star_check7.asm`, `spr_pmap.asm` | Code and tables in bank 7. |
| `rules.asm`, `stage_rules.py` | The stage colour rules (bank C) and their model; the dissolve's colour-table chunks (`dz_chunk`, `dz_mark`). |
| `fullcmp_gen.asm` | The generated full map comparison (`gen_fullcmp.py`). |
| `tables.py` -> `tables.asm` | Colour tables, sprite inks, keyboard decoder. |
| `convert.py`, `extract.py`, `emu_bench.py` | The colour fit's Python model (used by `tables.py` and the checks), Konami's graphics read from the ROM, and the simulator's screen grabs. |
| `konami_spec.asm`, `konami_spec_stubs.asm` | Konami's code, generated by `reloc/gen.py`. |
| `build.py`, `make_tap.py`, `verify.sh`, `release.sh` | Build, tape, regression checks, the release. |
| `lockstep_spec.py`, `check_*.py`, `test_*.py` | The checks of section 4. |
| `tape/` | Loader source (generated), loading screen and its converter, ZX0 unpacker and licence. |
| `../reloc/` | The relocator (`gen.py`) and its disassembly parser. |
| `../msxsim/` | The MSX simulator used by the checks. |
| `../README.md`, `../LEGAL-NOTICE.md`, `../LICENSE` | The front page (background, playing, building); who owns what; the MIT licence for the port's own work. |
| `../docs/` | This description, the development notes, and screenshots. |
| `nx_low.asm`, `nx_l2.asm` | The Spectrum Next's own code (section 9): Layer 2, hardware sprites, the smooth scroll, the MSX2 graphics. |
| `nxbuild.sh`, `sna2nex.py` | The Next build, and the snapshot made into a `.nex`. |
| `nx_pack.py`, `nxgfx/`, `nx_art.py`, `enh_patch.py` | The Next's graphics and redrawn enemies packed for the `.nex`, and the data bytes of `nxgfx/patches.txt` put into it. |
| `nx_smoke.py` | A minute of the `.nex` in ZEsarUX (`release.sh`). |

## 9. The Spectrum Next build

The Next build is the same port with a different drawing end.  Konami's
code, the platform layer and its map tracking are shared with the 128K
build; what the Next has that the 128K lacks (a fast CPU, a bitmap layer,
hardware sprites, a hardware scroll and a large memory) replaces the
128K's renderer and its colour fit.

### 9.1 How the build is made

`nxbuild.sh OUT.nex` runs `build.py` with `NEM_NEXT=1`, `NEM_FPT=2` and
`NEM_ADAPT=14,8` (9.2).
The shared files (`plat_spec.asm`, `render.asm`, `convert.asm`) differ for
the Next only inside `ifdef NEXT` blocks, and the nine places where the
Next build takes over one of Konami's instructions are `reloc/gen.py`'s
`NEXT_PATCH` (9.4), so the 128K builds are byte for byte what they were
without the Next.  The result is `nemesis_next.sna` (never `nemesis.sna`,
so `release.sh` cannot package it by mistake).  sjasmplus then assembles
`nx_low.asm`, which includes `nx_l2.asm`, against that build's symbols
(`nx_syms.inc`), as a separate 16K block.  `nx_pack.py` packs the graphics
(9.5) from `spec/nxgfx/` and the redrawn sprite enemies (9.6),
`sna2nex.py` packs the snapshot, the block and the graphics into a `.nex`
(format V1.2), and `enh_patch.py` puts the data bytes of
`spec/nxgfx/patches.txt` into it.  The build needs only the ROM.  A build
switch, read by `nx_pack.py`, leaves out the redrawn enemies drawn as
sprites: `NEM_ARC_SPR=0`.  (Those Konami draws with characters are part of
the character pool, 9.5.)

### 9.2 Memory and paging

* Port 7FFD is never written: on the Next it also puts the ROM back at
  0000-3FFF.  Paging goes through NEXTREG 56h/57h (MMU6/MMU7, C000-FFFF)
  instead, with the same page numbers.
* 16K bank 8 is mapped at 0000-3FFF (MMU0/MMU1) and holds `nx_low.asm`:
  its code and buffers, reached from the shared code only through a jump
  table at 0100.
* Layer 2's two screens are banks 9-11 and 13-15, flipped by NEXTREG 12h
  where the 128K flips its screens.
* Banks 16-31 hold the stage files, the fire copies and the redrawn sprite
  enemies (9.5, 9.6), bank 32 the character pool's maps and banks 33-37 its
  blocks (9.3).
* Bank 8's buffers sit above its code (which ends below 2000): Konami's
  sprite patterns as last sent and the character enemies' 4-bit patterns
  (2000-32FF), the scenery objects' flags (3300-333F), the changed-pattern
  flags, line-coloured sprites, the volcano rocks' pattern and the sprite
  attributes (3440-3A5F), the stage's tables for our drawings and the
  character enemies' palettes and frames (3B00-3CA5), the character
  enemies' colour bytes (3D00-3FBF), and the stage's palette and the
  pool's working bytes (3FC0-3FF1).
* The CPU runs at 28 MHz (NEXTREG 07h).  The game runs at 30 ticks a
  second, the original's rate on a 60 Hz MSX (two frames a tick at
  59.94 Hz): screens are at most 2, 2, 1 frames apart in turn (`lo_tick`,
  `PACE_30`), and the 128K's adaptive pacing (6.8) leaves a tick undrawn
  only when the game falls behind 14 eighths of a frame a tick (28.6 ticks
  a second).  The cap matters: without it a fast enough machine runs a
  tick every frame.  `NEM_PACE=25` builds the earlier pacing (screens at
  least two frames apart, the 128K's rhythm of 15 eighths, about 26.7 ticks
  a second).  In ZEsarUX at 28 MHz the game keeps up only with some ticks
  undrawn (about 22 screens a second); JNEXT runs it faster.  ZEsarUX by
  default holds this `.nex` at 14 MHz (its turbo limit applies when the
  file is loaded); `--allowturbotbbluerom` lifts it.

### 9.3 Drawing

* **The background** is drawn on Layer 2, a byte a pixel, only the cells
  that changed, as on the 128K.  During a stage a cell is copied from the
  **character pool** (`lo_pcell`, `lo_cmap`): every character of every
  stage as an 8 by 8 block of Layer 2 pixels, each different block once
  (1,261 blocks in banks 33-37), with a map per stage (bank 32: the block
  of each character of each third; bit 7 of a block's number marks a block
  of our drawings).  The pool is the Next's character artwork (9.5).  A
  pixel is a Layer 2 palette entry: the stage's 16 colours at 0-15, and
  our drawings of the enemies Konami draws with characters (9.6) their own
  palettes at 20h-CFh.  A cell is drawn instead from the port's copies of
  the MSX pattern and colour tables, each pixel its MSX colour number, for
  a character Konami has written to since the stage loaded (its bit in
  `tile_cdirty`/`tile_pdirty`, cleared by `lo_apply`; the Next leaves out
  the shared code's marking of every tile at a stage change, and its row
  hook marks rows Konami updates), one the map has no block for (the
  stars, F6 and F7, which twinkle), and on screens that are not a stage.
  The ship's ordinary shot is characters F8-FB (one for each 2-pixel
  step), which Konami writes into the map and takes out again, so the pool
  draws it like the scenery.  On the screen before each stage
  only the bottom third, the status line, comes from the pool (`lo_pool`
  2); the other two thirds hold Konami's font for the turn message.
  Copying a block is 8 `ldi` a line, each line's address set afresh (in
  column 31 the copies carry into the next line's address).  `nx_smoke.py`
  checks that the pool is in use and that the Next's code bank still holds
  its code as built.
* **Konami's screen dissolve** (after the stage 8 brain and, when its
  secret is not found, the stage 7 boss; 6.6) eats the colour and pattern tables over about 35 ticks.  On
  the Next it is a fade to black instead (`lo_fadestep`): from its first
  tick (`dz_on`) to the next stage load the pool draws every character
  whatever Konami has written, and every 4 screens drawn the Layer 2
  palette goes a step darker, each colour component less one (seven steps
  to black), for the stage's 16 colours and palettes 2-12.  What Konami's
  dissolve spares, the status line (rows 22-23) and the stars (characters
  F6 on), `lo_cell` draws in entries E0h-EFh, which hold the stage's 16
  colours unfaded.  Konami's logic runs as before, so the timing is
  unchanged; the next stage's load puts the palette back.
* **The smooth scroll.**  When Konami's map moves a character, the screen is
  shown 7 pixels to the right of it, and the gap closes by a pixel a tick
  through Layer 2's X scroll (NEXTREG 16h).  Layer 2 is used as a circular
  buffer: Konami's row moves (0:46A1) turn the port's copy of the map and
  its dirty bitmaps instead of redrawing.  A line interrupt at line 176
  resets the scroll for the status rows, and the left 8 pixels are clipped.
  The frame and line interrupts are told apart by alternation, so nothing
  that runs during play may disable interrupts for long: an interrupt that
  comes then is lost on the Next, the alternation goes out of step, and the
  status rows take the play area's scroll.  (The Big Core's patterns, sent
  from the main program, once did; see below.)
* **Sprites** are the Next's: Konami's 64 patterns as 4-bit patterns, each
  sprite's MSX colour as its palette offset, with attributes and changed
  patterns sent when the screen they belong to is shown.  Sprites are drawn
  the scroll's distance to the left so they stay where Konami puts them;
  objects Konami moves with the scenery (its helper at 2:9251, which the
  Next notes) move with it instead.
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
  A character Konami has written to since the stage loaded, or one with no
  block, and the two-character enemies, are converted from the copies
  instead (`lo_conv`).
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

### 9.4 Konami's instructions the Next build takes over

| Site | Konami's | The Next's | Why |
|---|---|---|---|
| 0:46A1 | `ldir` (the scroll's row moves; the 128K's `nm_ldi31_full`) | `lo_shiftrow` | The circular buffer (9.3). |
| 2:9251 | `ld a,(E100)` (se_corre_con_el_scroll_ocho) | `lo_gnd`, which notes the object and does the same | Objects moved with the scenery. |
| 0:4100, 0:414B | `call 422A` (carga_los_graficos_de_la_fase) | `lo_stage`, which calls it and then puts in the MSX2 graphics | 9.5. |
| 0:5851 | `ld de,5906` (carga_el_marcador) | `lo_marcador`, which restores the TMS9918 colours and does the same | Screens that are not a stage. |
| 0:544F | `call 5874` (the screen before each stage, 0:53C8) | `lo_prestage`, which calls it and then puts in the coming stage's palette and bottom third | 9.5. |
| 2:99A1, 2:99C3, 3:A19B | `ld a,(E200)` (the ship's state, choosing its sprites and where its second goes) | `lo_shipst`: with the MSX2 graphics, always the plain ship, as the patch's code does | 9.5 (the shield). |

Each runs Konami's own instruction or routine, so the game's logic is
unchanged.  `gen.py` checks Konami's bytes at each site and stops if one
has moved or changed.

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
  a pixel (a stage colour 0-15, or palette * 16 + colour for our drawings),
  each different block once;
* `maps.bin`: 2K a stage, two bytes for each character of each third: the
  8K page of its block in the `.nex` (66 on: bank 33 on, 128 blocks a page)
  and its number in that page; page 0: none;
* `stageN.bin` (N = 1-8, 16K each): video memory 0000-37FF as the stage
  load leaves it, now only for the sprite patterns and the stars
  (characters F6 and F7, which Konami rewrites in play), the palette as
  Next 9-bit colours, the sprite line-colour tables, and a
  write mask, a bit per byte;
* `logo.bin`: the title logo and its palette;
* `patches.txt`: data bytes in Konami's own ranges (the font and its
  colours, object and shot colours, the bosses' colour tables, map
  pieces), as bank, address, Konami's byte and ours.

`nx_pack.py` packs them into banks 16-37 with each stage's sprites in fire
colours (9.6) and the redrawn sprite enemies, marking the maps' blocks of
our drawings (bit 7 of the number).  A `.nex` built from the stage files
was checked byte for byte against one built from the patch's IPS before
the IPS was dropped from the build, and the pool and maps against the
build that made them before they became the artwork.

After each stage load, `lo_stage` copies the masked bytes into the port's
tables, as the patch's own load would have written them, sets the palette
and turns the pool on; bytes the load does not write keep what earlier
screens left, as they do on the MSX2.  The screen before each stage (at a
new game and after a life is lost) shows only the status line, which
Konami loads there; `lo_prestage` gives it the coming stage's palette and
draws its bottom third from the coming stage's pool, so the status line is
not shown in the TMS9918's graphics until the stage loads.  It leaves the
other two thirds alone: they still hold the font for the two-player turn
message.

The patch's title logo is not made of characters: it is a 16-colour
bitmap (256 by 48 pixels, stored as it is in the patched ROM at 30000h,
its palette at 2E520h), which the patch shows by switching the top of its
title screen to a bitmap mode.  On the Next, `lo_marcador` recognises the
title screen by its caller (0:5B4D) and, when the logo is in the `.nex`,
gives its palette Layer 2 entries 10h-1Fh; `lo_logocell` then draws the
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
for the ship and some capsules, drawn as 4-bit patterns.

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
  and both).  The enemies Konami draws with characters (frames of its table
  at 5:91D1, four characters each): the fans, the hatch saucers, the
  turrets on the ground and on the ceiling (six aims each), and the two
  capsules.  Those that leave a capsule are red, as in the arcade: a sprite
  of the pod, jet, robot or walker with byte 14 set (Konami's colour 8)
  takes the next palette, its red twin; Konami draws such turrets with red
  characters of its own (a second set of frames), which take the ordinary
  turret's drawing in the red palette.  Stage 2 adds the enemy that
  materialises in columns (Konami's type 8, patterns 47-50, after the
  arcade's growing ring) and its turrets, whose frames have the pixels of
  stage 1's, in a blue tint (palette 11).
  `local/tools/arcade/gen_art.py` made the sprite drawings from the arcade
  sprite sheets once; they are kept as data in `spec/nx_art.py`, so the
  build does not need the sheets.  `nx_pack.py` stores them in bank 25's
  second 8K (page 51) and their tables in bank 26's (page 53): the
  palettes, Konami's frame table (9.3), and for each stage a map of
  Konami's patterns to our drawings.  A stage has an enemy's sprite
  drawings where all that enemy's patterns are stage 1's in both Konami's
  load and ours (so no enemy is drawn half ours, half Konami's).  The
  drawings of the enemies Konami draws with characters are in the
  character pool (9.5): the quarters of each frame's drawing, in its
  palette, as the blocks of that frame's characters, with the character's
  own background where the drawing is transparent, in each stage and third
  where the characters were stage 1's.  The turrets were placed by Konami's
  table of their frames (2:9205), a set taking stage 1's drawings where
  its frames had their pixels, in stage 1's colours, the stage's tint, or
  red for those that leave a capsule (red only where the stage's ordinary
  turrets were ours).  On the Next, `lo_apply` loads the palettes and the
  stage's tables (`LO_OVR`, `LO_APAL`, in bank 8 at 3B00-3C67);
  `lo_sprflip` sends our drawing in place of a mapped Konami pattern, and
  `lo_arc` (from `lo_ecol`) gives any sprite showing one its palette.
  Character enemies Konami moves with the scenery (the turrets, the
  capsules) stay in the map and are drawn from the pool as the scenery is;
  those lifted out are made from the pool too (`lo_pconv`, 9.3), and `.co`
  gives them their palette (`LO_OPAL`).  So an enemy looks the same in the
  map and lifted out, including frames Konami builds from other frames'
  characters (frames 29-2C, from the fans').  `lo_marcador` clears the
  tables for screens that are not a stage.  Konami's colour changes (a
  flash) do not show on our drawings, and the capsules' glint (Konami
  animates their characters) is not drawn.
* Konami's screen dissolve is a fade to black (9.3).
* The patch recolours the Big Core at each boss (it switches pattern
  table and rewrites colours there); the Next keeps the stage's colours
  for it, which were liked better.

### 9.7 Checks

`verify.sh` ends by building the `.nex`, which takes seconds.  `release.sh`
builds the `.nex` as well as the tape and snapshot, and, if ZEsarUX is
available, plays it for a minute (`nx_smoke.py`: the game must start, its
scroll must move, the stage graphics must be in, the background must be
drawn from the character pool, and the Next's code bank must still hold
its code as built).  The
lockstep checks of section 4 cover Konami's logic, which the two builds
share.

### 9.8 Known limitations

* Konami's collisions with the scenery work on whole characters, while the
  scenery is shown up to 7 pixels to the right of where Konami has it, so a
  collision can look up to 7 pixels off.
* Objects Konami moves 8 pixels at a time by its own code, rather than
  through its scroll helper, still move in steps (the Big Core excepted,
  9.3).
* A second Konami cartridge (F0F4) is not supported, so its extra sprites
  are not loaded.
