# Nemesis for the ZX Spectrum 128K: development notes

The history of the port's Spectrum build, in order: what was measured,
tried, kept and rejected, and the bugs found on the way.  For how the port
works as it stands, see `TECHNICAL.md`; where the two disagree, `TECHNICAL.md` is
current.

The initial project was started in ChatGPT. It was later shifted to Claude.

The objective was to attempt to run something as close to the original
Konami MSX Nemesis as was possible on the Spectrum, running Konami's MSX
code, and replacing MSX hardware dependencies with Spectrum equivalents.

The early stages saw ChatGPT start by extracting the MSX graphics and stage
information, and attempt to establish whether the Spectrum could reproduce the
scrolling playfield satisfactorily. 0.1 had a native Spectrum renderer displaying
all 456 columns of Level 1, scrolling in 8-pixel increments using the Spectrum
128's two display buffers.

Subsequent versions added the Vic Viper, player movement and shooting. However,
ChatGPT drifted from the original objective and began creating original routines
for ship movement, keyboard handling, firing and projectile movement. When this became
apparent to me as the human, I objected, and on my insistence ChatGPT began transplanting
the corresponding routines from Konami's MSX version. However, the overall architecture
remained a newly written Spectrum game engine which called selected Konami routines,
rather than the original vision for the project, i.e.: Konami's original game engine
running through a Spectrum hardware compatibility layer.

The initial migration into Claude continued in this vein for several iterations, partly
because the original vision had been slightly muddled in the transition; Claude started
off with ChatGPT's amalgamation of original Spectrum glue code calling transplanted Konami
routines as its primary context, without the opening brainstorming that ChatGPT had had.
It was only when Claude surveyed what Konami's code actually did and how little of the MSX
the game touches that it independently decided to "go further than porting more routines"
and produced version 4c, which coincidentally happened to be a return to the original
vision: run the original MSX code in full and translate MSX hardware calls into Spectrum
equivalents.

Version 4c took the project from "Vic Viper flying around something that looked a bit
like Stage 1 with an occasional enemy to shoot at" to "the MSX version of the game actually
now runs on the Spectrum, albeit with many rough edges". Given it was in a single increment
it was something of a jaw-dropping moment.

## Version 4c: the first complete build

The name comes from the plan it grew out of.  A survey of Konami's code
found the game frame (`un_cuadro_de_juego`, a list of about 30 calls) and
the small hardware boundary underneath it.  The unmodified cartridge was
then run in a simulated MSX (`msxsim`) built from just that boundary, and it
booted, played stage 1 and scrolled at the speed measured from video.  Step
4a was the relocator (`reloc/gen.py`, which rebuilds antxiko's disassembly
with Konami's code and data moved to Spectrum addresses), 4b a layout
simulator that ran the relocated code in the simulated MSX to catch
relocation mistakes, and 4c the Spectrum build itself: Konami's relocated
code with Spectrum stand-ins for the MSX hardware, checked tick by tick
against the simulated original (the lockstep).  The name stayed until the
build became 0.8.

The first complete build ran at 14.9 ticks a second, against the MSX's 25
or so.  The work below starts there.

## Making it fast enough

Speed history over stage 1:

| Change | Ticks/s |
|---|---|
| First complete build | 14.9 |
| Keyboard decoded once per tick by generated code | 16.0 |
| Map upload: only the regions Konami wrote, instead of a full compare each tick | 16.7 |
| Native star twinkle (it had been six slow video writes a tick) | 17.3 |
| Pending-conversion flag in the tile attribute; tighter cell loop | 18.8 |
| Region list, cheaper cross-bank calls, faster sprites and keyboard | 20.3-21.3 |
| Flip in the interrupt (the next tick's logic runs while a frame waits) | about 22 in play |
| Scroll: unrolled shift, generated comparison, star moves through lists | 22.4 in play |

At that point Konami's own logic took about a third of a tick and drawing
the cells, sprites and stars most of the rest.  The ticks that missed their
two-frame slot were mostly scroll steps, where every non-empty cell changes
and is redrawn on both screens.

A few decisions were made along the way.  The power-up bar was redrawn for
the Spectrum (white letters on blue, the lit box yellow on black) rather
than colour-converted.  Pacing schedules each flip from the previous actual
flip, with no catching up, so a late tick costs one frame rather than
throwing the rhythm out.  And the pause when restarting after a death went
from 2.5 seconds to under one with a native version of Konami's graphics
decompressor writing through a buffer.

### Bug found: tune data overwritten

The tile conversion cache had been placed in memory that also held some of
Konami's tune data, so once tiles were converted those tunes played
garbage.  The lockstep did not compare sound then, so it did not show.  The
cache and the colour fit moved elsewhere.

## The scroll step

The scroll step was the most expensive tick: the full comparison of the map
against the screen, the column shift, redrawing about 95 changed cells
(about 60 of them stars moving), and rebuilding the star lists.  Several
approaches were tried:

| Attempt | Result |
|---|---|
| Fold the comparison into the shift | Correct, but slower: Konami's writes before and after the shift then needed comparing separately.  Dropped. |
| Unrolled row copies for the shift | A fifth faster.  Kept. |
| Generated comparison code | A little faster.  Kept. |
| Star moves through a bitmap | The bookkeeping per cell cost nearly as much as redrawing it.  Replaced. |
| Star moves through lists (`draw_stars`) | A clear saving on the ticks after a scroll.  Kept. |

The net gain was small (22.18 to 22.38 screens a second in play), because
the busiest scroll ticks took so long that a few thousand T-states either
way did not change how many frames they spanned.

## Where a tick's time went after the scroll work

The character enemies (2x2 map characters that move a cell every tick)
change about 32 map cells a tick while a wave is on screen, each tracked
and then redrawn on both screens.  New terrain graphics are uploaded long
before they scroll into view and converted when first drawn, which lands
the conversion cost on scroll ticks.  The stars cost a few percent between
the twinkle, the list rebuilds and their drawing.  Konami's own logic took
55,000-90,000 T-states a tick.

## Stars, laser, pacing

* The laser was nearly invisible: its writes into the map buffer had been
  missed, because the census of map writers had been run without a laser.
  Fixed, and the lockstep gained a laser mode.
* Turning the twinkle off, or showing half the stars, was tried and
  reverted.  The twinkle is what moves each star's pixel smoothly across its
  cell between the 8-pixel column jumps; without it the stars jump 8 pixels
  every 8 ticks.  The savings (about 4% for the twinkle, under 1% more for
  half the stars) were not worth the look.
* Catch-up pacing gained only about 1%, and frame skipping kept the game
  nearer 25 ticks a second but showed only 12-19 screens a second.  The
  existing pacing stayed.
* Timed by hand on a real PAL MSX, the Vic Viper takes 3.5 seconds to cross
  the screen top to bottom, against 3.86 on the port: about 10% slower.

## Missed map writers

Censuses of the MSX original through every stage, with no weapons, with all
weapons, with double shot, missiles and options, and with deaths, found 45
instructions that write the map buffer.  Four were not covered and are now
tracked: an enemy cleared when it turns into an explosion, the stage 7
boss's two-cell writer, the laser breaking a destructible cell, and the
buffer cleared before a boss.

## Stage 6 crash: bank 10

The all-weapons lockstep matched through stages 1 to 5, then in stage 6 the
Spectrum ran into its ROM.  The stage 6 boss is drawn from tables in MSX
bank 10, of which the build carried only the first 219 bytes (the title
graphics), so it read garbage, copied a huge rectangle and overwrote
Konami's stack.  Measuring which bytes the game reads over two whole games
showed it needs about 3.9 KB of bank 10, and there was no room for it.

## Front end and bank 10 in page E

To free up space, the front end now goes straight to PLAY SELECT: no Konami
logo and no attract cycle (no demo play, no illustration).  Two patches to
Konami's state machine do it, and the lockstep applies the same two to the
MSX side.

With no demo, play reads much less of the data bank that held it, so that
space could take the title's graphics and bank 10's used part, together
with the boss-piece code that runs with bank 10 mapped.  The conversion
cache shrank to 16 entries to make room.

The all-weapons lockstep then matched for 70,000 ticks: the whole first loop
of eight stages, the end-of-loop explosion and bonus, and the second loop to
stage 7.  On the way it found three numbers the relocator had taken for
addresses, none reached by any earlier run: the stage 7 boss's shot
position (its shots started too far right), two characters that boss writes
into the map, and the ship's position after the end-of-loop explosion.  A
scan of the disassembly for the same patterns found no others, and the
lockstep gained a way to report every instruction that writes a chosen
byte, on both machines.

## Options noted then (not taken up)

* Converting tiles ahead of need was measured as an upper bound (all
  conversions made free): about 0.4%.  Not worth building.
* Beyond that, more speed needed less work per tick: the full map
  comparison on scroll ticks, cheaper tracking of the character enemies, or
  native versions of Konami's hottest routines.  Each would need a best-case
  measurement first.

## Game over fixes

* Sprites were left on the title after a game.  Konami hides every sprite
  with a single write to the sprite table and leaves its own sprite list
  alone; the MSX shows no sprites after that write until the next upload,
  but the port's renderer drew from the list and kept showing it.  The
  renderer now follows the same rule, which also removed stale sprites from
  the restart screen after a death.
* Continue: Konami lets the player continue by pressing a key while the
  game-over tune plays.  The Spectrum key is now C (it was ENTER), and the
  message reads CONTINUE C.

## Masked sprites over terrain (prototype)

A build option draws a sprite with terrain under it through a mask, a halo
one pixel wider than the sprite, so that it stands out from the ground.  It
cost about 11% in speed, and screenshots of the same ticks barely differed:
the ugliness on the ground is the attribute clash (solid terrain cells take
the sprite's ink), which a halo cannot fix.  It was never enabled, and once bank 7 filled up
it no longer fitted; it was removed in the clear-out after 0.107.

## Dense tiles stored inverted

A converted tile with more than half its pixels set is now stored inverted:
pixels flipped, ink and paper swapped.  It looks the same, but its solid
part is now paper, and since a sprite changes only the ink of the cells it
covers, solid terrain keeps its colour under a sprite instead of turning
into a block of the sprite's colour.  Sprites over sparse tiles (tree tops,
edges) still recolour them.  The cost was negligible.

## Game speed: a tick without drawing after every four

After every four drawn ticks the main loop now runs one more of Konami's
ticks without drawing; the next drawing catches up.  The game itself is
unchanged (the lockstep still matches), but more of its ticks fit in a
second: 21.6 to 24.1 ticks a second, with screen updates going from 21.5 to
19.2 a second.

## Kempston joystick and the controls line

* A Kempston joystick is read alongside the keyboard.  Without an interface
  the port reads whatever is on the bus, so the port looks once at boot, at
  a moment when an idle bus reads all ones, and turns the joystick on only
  if it sees a real reading.  The Sinclair joystick (keys 6-0) was already
  mapped.
* The title shows the controls over PLAY SELECT, in Konami's own font.
* A prototype that blanked sparse terrain under sprites was 7% slower and
  was dropped.

## Version 0.8: title credit and loading screen

This build is named 0.8.
* Title: "PORTED BY PAUL AND CLAUDE", cleared when play starts.
* Loading screen: the MSX attract illustration (the one dropped with the
  attract cycle), converted cell by cell, with a little hand work on the
  planet and a rock face.  The loader shows the 128K's second screen and
  loads the picture into it first, so it builds up on screen while the rest
  loads, with the loader itself hidden in the other screen.  A simulated
  load of the tape gives memory identical to the snapshot.

## 0.81: the nuke capsule in cyan

Version numbers now go up by 0.01 a build.  The capsules are not sprites
but 2x2 map characters, and with one ink per cell the standard capsule
(red core on the MSX) and the nuke (blue and cyan core) came out as the
same white capsule.  The nuke's characters are now bright cyan; nothing
else uses them.  0.81 also loaded and ran on emulated +2A and +3 machines,
which settled a worry that the loader's ROM routine would be missing there.

## 0.82: compressed tape

The tape's blocks are compressed with ZX0 (Einar Saukas).  Each block loads
into memory that is free at that point and is unpacked into place; the
loading screen stays uncompressed so that it still builds up on screen.
The tape went from 100.7 KB to 60.3 KB, and the loading time at ROM speed
from about 10 minutes to 6.5.

## 0.83: sprite colours

The MSX's light blue, light red and light yellow, all nearest to white
before, now map to bright cyan, bright red and bright yellow.  The
explosion frames take yellow to red in turn whatever their MSX colour, and
the enemy bullet stays white.

## 0.84: the taken item's box

Once an item can no longer be taken (OPTION with every option out, for
instance), Konami blanks its box in the power-up bar.  One of the blank
box's characters was outside the bar's own design, so it got the ordinary
colour conversion and showed as a white block.  It is now part of the
design.

## 0.85: 1 in 3

One undrawn tick after every three drawn instead of four: in play it gave
fewer sluggish moments in stage 1 with no visible loss of smoothness.

## 0.86: the title logo

The colour conversion made the NEMESIS logo a patchwork of blue and cyan
blocks.  On the MSX each pixel line of the logo is a single colour, so a
rule now draws it: a cell is bright cyan if it has a cyan or light blue
line, otherwise bright white, with light blue lines as a 50% stipple.  The
look was chosen from mock-ups.

## 0.87: the missile over terrain

The missile, a few pixels rolling along the ground, left a big yellow trail
along the red terrain: a sprite colours every cell its 16 x 16 box touches,
and the solid floor cells under it turned yellow.  The missile now colours
only empty cells and star cells, so the ground keeps its colours (a star it
passes flashes yellow, which reads as a twinkle).

## 0.88: lost interrupts

The music sounded ponderous, and the game still felt slower than the PAL
MSX.

Input lag was measured first, by pressing up or down and counting frames
until the ship showed in its new place: about 3 frames on the simulated MSX,
about 5 on the port, and more spread out.  The extra comes from drawing the
whole screen and showing it at the next two-frame boundary, with the next
tick's logic (and its input) running ahead while it waits.

The music was a real fault.  Konami's sound driver runs once per interrupt,
so the tempo should match a PAL MSX exactly, but 1 interrupt in 18 never
ran.  The MSX's video chip holds its interrupt request until the game
acknowledges it, so Konami turns interrupts off freely and loses nothing;
the Spectrum's request is a pulse of about 36 T-states, lost if interrupts
are off just then.  The misses fell in the port's own code that borrowed a
bank with interrupts off, and inside Konami's di/ei around every bank
switch.  The pacing counts frames in the same interrupt, so it lost them
too.

Now every page switch goes through one routine that notes the new value
first, so the interrupt can restore the paging itself and nothing needs to
turn interrupts off for it.  The relocator turns Konami's `di` before its
57 bank switches into `nop`.  A first version caught the sound driver being
unmapped mid-tune (the lockstep found it at tick 409).  Missed interrupts
fell from 5.6% to 0.05%, the music came right, and speed and input lag both
improved a little.

## 0.88a: 1 in 4

With the music at its proper tempo, the game no longer sounded slow, so
1 in 3, 1 in 4 and none (every tick drawn) were compared side by side in
play.  None and 1 in 4 both felt smooth and playable, and 1 in 4 was
chosen.

## 0.89: all stages checked, and colours that never updated

The lockstep proves Konami's state through every stage, but the checks of
what the port draws had only been run over the start of stage 1.  The
emulator gained an all-stages mode (the ship invulnerable and, once play
starts, all weapons through the game's own cheat), and every checker uses
it; 3,000 seconds of play covers the first loop of eight stages and more.

Three checkers passed throughout; the tile checker did not.  From stage 2
on, some tiles still had stage 1's colours, most visibly the ground hatches
at the bottom right, drawn red instead of blue.  The cause was in the bulk
writes to video memory: they marked changed tiles using a code that the
colour table shared with sprite patterns, so colour changes were taken for
sprite writes and never marked.  The bug dated from the bulk writes' first
version; stage 1 escaped it because every tile starts out waiting for
conversion.

The run also showed that the explosion's last sprite pattern is the
option's too (magenta on the MSX), so the explosion colouring makes the
options red.

## 0.90: stage colours, and the bonus stages closed

A stage-by-stage review against the MSX found five stages where the colour
conversion, choosing two colours per cell from up to five in an MSX
character, gave a patchwork or the wrong impression: the stage 2 bricks,
the stage 3 Moai faces and rocks, the stage 6 brain, the stage 7 band and
its formations, and the stage 8 pipework and brain.  Each was mocked up on
full screens from the MSX characters, chosen from several versions, and
written as a rule that recognises its characters by the MSX colours in
them, so that a stage's other characters are left to the automatic
conversion.

Two findings on the way.  A new stage often reloads characters unchanged,
and a character is only converted again when it changes, so a rule's
result could outlive its stage; now every tile is reconverted when Konami's
stage number changes.  And one mock-up had put two colours of different
brightness in a cell, which a Spectrum cell cannot do, so the brain was
made bright throughout and the stage 7 band plain blue and white.

The bonus stages were closed for the time being.  Touching a hidden target
near the end of stage 2, 3, 4 or 7 sends the game to a bonus stage, but the
port did not carry the bonus stages' data, so a player who found a target
got about a minute and a half of junk on screen.  Making the stage endings
ignore the touch left the game waiting forever (the scroll stops at the
target), so the touch itself is now ignored, which is exactly the game when
the target is missed.

## 0.91: the bonus stages

The bonus stages come in between the normal ones when their targets are
touched: 1, 2, 9, 3, 10, 4, 11, 5, 6, 7, 12, 8.  Measured on the MSX with
every target touched, they need their four scripts and a table of their
endings, about 2.3 KB in all.

Room was found by measuring the banks carried whole and identifying every
range the game does not read, rather than taking "not read in our runs" to
mean "spare" (bank 12's own trimming had shown how wrong that can be).
There were two: graphics the game loads only when it finds Konami's TwinBee
cartridge in another slot (the capsules become TwinBee's bells), which it
never can on the Spectrum, and the attract cycle's high-score screen.  The
colour converter moved to make room where the bonus data had to go, and the
relocator learnt to place parts of a data bank separately.

Two faults only the bonus stages reach were fixed.  Stage 12 reads its
graphics list one word past the end of its table, from the next table, and
that word had been left unrelocated, so its screen was garbage.  And one
entry in a table of graphics pointers points into a different bank from the
rest, to an empty stream; it had been left as a plain number, which on the
Spectrum points into screen memory.

The lockstep and the checkers gained a mode that puts the ship on every
target as it appears, and another that lets the ship die once in each bonus
stage (dying there ends the bonus stage and sends the game on to the next
normal stage).  Both match and pass.

## 0.92: bonus stage 10's balls

The colour conversion drew bonus stage 10's balls white.  A rule now makes
them yellow, leaving the one-pixel stars alone.  The rule's first version
broke the bricks in the same stage, which a screenshot showed at once.

## 0.92a: a safe stack in the snapshot

The snapshot's stack pointer sat just above Konami code.  Emulators start a
snapshot from its program counter directly, but a hardware loader (a DivMMC
or Retroleum SmartCard, say) might start it by pushing the program counter
and returning, which would have corrupted that code.  The stack pointer now
points at the boot stack, which is rebuilt at start-up anyway.

## 0.93: sprites clipped at the edges

Sprites were drawn only when wholly on screen across, so everything coming
in from the right appeared up to 23 pixels late, and anything leaving on
the left vanished as soon as it touched the edge.  A sprite that is partly
off screen now has the visible part shifted into a pattern of its own and
drawn at the edge.  The sprite checker models the clipping, and a new mode
adds test sprites at every position across both edges.  The cost is under
1% of a tick in the busiest play.

## 0.94: power-up without the keyboard

On the MSX the power-up is the joystick's second trigger, so a one-button
Spectrum joystick player had to reach for M.  There are now two ways
round it:

* A second fire button on a Kempston interface, which some interfaces put
  on bit 5 and others on bit 7.  Each is used only if it reads as released
  at boot, so an interface that leaves the bit floating cannot select
  power-ups by itself.
* Hold-to-select: holding fire for 12 ticks presses the second trigger as
  well, until fire is let go.  Konami's code was read first to make sure
  this was safe: a held fire button only repeats the shot, nothing else
  reads it held, and a held second trigger gives one power-up per hold.

The title's second line now reads ON JOYSTICK HOLD FIRE TO SELECT.

## 0.94a: the tape on a DivMMC

The tape hung on a real +3 with a DivMMC Future: the BASIC and the loader
came in, then nothing.  A DivMMC loads a tape file from its card by
trapping the ROM loader at one particular instruction.  Our loader did the
ROM's set-up itself and joined the ROM just past that instruction, so the
trap never fired and the ROM sat waiting for a tape signal.  Real tape, the
Maxduino and the SmartCard do not rely on the trap, which is why they had
worked.

The loader now joins the ROM at the trapped instruction, so on a real tape
the ROM does exactly what it did before.  How esxDOS returns from the trap
is not documented, so the loader is also safe if interrupts come back on.
A new test loads the tape the trap's way, both ways it might return, and
the tape then loaded on the real +3 through the DivMMC Future, with the
second fire button working there too.

## 0.95: the real speed, and cheaper sprites

Side by side with a 50 Hz MSX on real hardware, the port was plainly
slower.  The 24.3 ticks a second quoted since 0.88 had come from 90
seconds that were mostly the quiet opening of stage 1; over four minutes of
stage 1 the port ran at 19.8 on average, 15-21 through the busy parts.

A profile of busy play showed the processor never idle.  Konami's code took
about 40% of the time and the port's drawing about 38%, more than half of
it the sprites, with map tracking and paging most of the rest.  Two changes
to the sprites (building one mask per sprite when erasing, and shifting
some offsets left instead of right) took play from 19.8 to 20.6 ticks a
second.  The usual big saving, pre-shifted sprites, needs kilobytes of fixed
memory there is not.

A build option to draw one tick in N was added.  One in three reached 23.1
ticks a second but only 7.7 screens, too jerky; one in two gave 22.6 ticks
and 11.3 screens, and was built to try.

## 0.96: one tick in two drawn, and the last overheads

Played side by side with the MSX, drawing one tick in two felt closer to
the original, and it became the default.  For a proper comparison the MSX
original was run in the simulator at 50 Hz, with the same front end and the
same scripted play as the port, and with an estimate of the real BIOS's
time charged for each BIOS call.  Over stage 1's scroll the MSX took 110
seconds, the previous build 141 and one tick in two 127.

Input lag was measured more carefully: about 5.4 frames before, 7.1 with
one tick in two, against about 3.2 for the MSX.  Drawing at once when the
joystick direction changes was tried, made no difference, and was taken
out.

A profile of the remaining overheads led to three small changes: skipping
writes to the sound chip that would not change anything, skipping needless
page switches, and copying a few frequently called routines into the bank
of the code that calls them.  They gained far less than estimated, and that
is where the optimising stopped.

## 0.97: the twinkle on drawn ticks only

With one tick in two drawn, the star twinkle's work on an undrawn tick is
overwritten before anything shows it, so it now runs only on ticks that
will be drawn (test builds still run it every tick, for the lockstep).  A
small gain, nothing visible.

Halving the stars was tried again, this time in Konami's own data.  It only
thins the open sky; once the terrain starts the stars come from the map
pieces, and the speed did not change.  Dropped again.

## 0.98: two editions

Neither drawing rate was clearly better: one tick in two is nearer the
MSX's speed but jerkier and laggier, four in five smoother and more
responsive but slower.  So both are released from one source, as *fast*
and *smooth*, and the player's notes suggest trying both.

## 0.99: pacing by the MSX's own rule

A longer comparison over the first two stages showed the fast edition ahead
in stage 1 but behind in stage 2, where the simulated MSX averaged 27.5
ticks a second.  The reason is in Konami's interrupt routine: it runs a
tick at every interrupt unless the previous tick is still running, so a
tick that fits in one frame gives one tick a frame.  At 50 Hz that happens
in light stretches (the starts of stages, the run to the stage 1 boss, parts
of stage 2), at up to 50 ticks a second.  The port's fixed two-frame rhythm
had come from 60 Hz video, where fewer ticks fit in a frame.  That also
explains why 50 and 60 Hz machines play at about the same speed while the
music is faster at 60.

The port now follows the MSX's rule: a tick takes at least one frame.  In
busy play nothing changes, and in light stretches the port speeds up as the
MSX does.  It could even run ahead, since the MSX's rate moves in whole
frames and the port's does not, so the fast edition keeps its screens at
least three frames apart, which holds the stage 2 boss near the MSX's
speed.  Over the first two stages the fast edition went from 86% of the
MSX's time to 94%, and the smooth from 84% to 86%.

## 0.99a: the stars' colours

In the fast editions of 0.97 to 0.99 every star showed red, where the MSX's
show yellow and bright cyan, and the cyan ones were not drawn at all, so
about half the stars were missing.

The fault was in the tile converter, and had been there since lazy
conversion was written.  When only a character's pixels have changed, the
converter keeps its existing ink and paper and maps the new pixels, but it
read that attribute from an address built from a register that had already
been overwritten, and the byte it found there meant red on black.  Only the
star characters ever take that path, and only when the first conversion of
a stage catches the star row blank.  With the twinkle running every tick
that rarely happened; with it only on drawn ticks (0.97) it happened at the
start of every stage.

The first explanation, which removed 0.97's change for a build that was
never released, was wrong: it blamed the registers the twinkle leaves
behind.  The real cause was found by tracing the star characters'
attributes frame by frame in both builds and catching the instruction that
wrote the wrong value.

The checks had missed it for two reasons.  The twinkle's skip is left out
of test builds, so the lockstep never saw the broken path; and the screen
and tile checks compare the picture with the port's own converted tiles,
which were themselves wrong.  Code that exists only in release builds is
outside the lockstep's reach.

## 0.100: the ship redrawn, its second sprite dropped, the version shown

The MSX ship is two hardware sprites at the same place: a white one, and a
red canopy over it (a light blue belly when climbing), since an MSX1 sprite
has one colour.  The port drew both, and since the white one was drawn last
its ink won every cell: the second sprite cost a full draw and erase for a
handful of pixels already inside the white outline, and the red was lost
anyway.

Several designs were tried over real stage 1 screens: a hollow canopy,
plates split by seams, split wings, blocks in the manner of the 1987
Spectrum Nemesis, that ship itself squeezed to size, and a mix.  At real
size the busier ones read as noise.  The one chosen kept the MSX outline,
with an outlined canopy where the red was and seams sweeping the wings
back, and each design needed its diving and climbing frames as well.

Konami's ship data is compressed in the cartridge and written by several
routines, so the patterns are not replaced there; instead the renderer
takes the ship's three frames from the port's own patterns and skips the
second sprite.  The video memory stays as the MSX has it, so the lockstep is
unaffected.

The run that confirmed nothing else uses the ship's patterns also showed
that the checkers' routine 600 seconds of all-stage play reaches only
stages 1-3 and bonus stages 9-10, not the whole loop as earlier entries had
said.  Those entries were corrected.

The version is now shown on the title (V0.100F or V0.100S), after Konami's
copyright.  Konami's font has no full stop, so one is added to a blank
character.

## 0.101: the version moved to the top right

The version after Konami's copyright left Konami's centred line lopsided,
so it moved to the top right of the title, and Konami's line is as the MSX
has it.

## 0.101: the overnight run

A full run of the checks on the release builds, after it turned out that
the routine checks cover only part of the loop.

On the route with every target touched, the fast edition reaches stage 4 at
622 seconds and stage 8 at 1,481, and the second loop's stage 1 at 1,699;
the smooth edition is about 14% behind.  The checkers ran over 3,000
seconds of it (the whole first loop with all four bonus stages and most of
the second loop) on both editions.  Everything passed except one tile check
at one stage change: when the stage number changes, the port notices only
at its next full map comparison, so for at most one tick a redrawn cell can
show the previous stage's colours.  It has been that way since the colour
rules came in, and was left alone.

The star tiles' colours were counted by stage on both editions, since the
tile checker cannot see a wrong choice of colours: all correct.  Konami's
stack was checked for headroom (its deepest use is 22 bytes clear of the
end of its area), and the interrupt table was never disturbed.  The
lockstep matched with all weapons over the whole first loop and most of the
second, and in shorter runs with every target touched, with deaths in the
bonus stages, and with hold-to-select.

## 0.102: the attract cycle's tune on the title

On the MSX the logo and the title are silent; the music comes with the
attract cycle, as its illustration appears.  With the attract cycle gone,
the tune was gone too, though its notes were still in the port: requested
on the port's title and compared with the simulated MSX, it plays the same
notes in the same order.

The title now loops it, with a 3-second gap between plays.  Starting a game
first left the tune playing on into the stage, and since Konami starts a
stage's music only on a silent channel, the stage's tune would have waited
for it; so starting a game now stops it with Konami's own silence request.
The lockstep, which compares the sound and knows the MSX title is silent,
now gives the MSX the same requests.

## 0.103: the ship's frames redrawn

0.100's diving frame looked better than its level frame, so it became the
level frame, and a new diving frame went further the way the MSX's does.
For climbing, a belly view was tried but became a plain silhouette; the
diving frame turned over about the nose was chosen instead.

## 0.104: the ship's climbing and diving frames, small tilts

In motion, 0.103's climbing and diving frames did not work: each change of
direction looked like a different ship.  The level frame stayed, and diving
and climbing became small tilts of it: a few pixels at the nose, and a
little more of the belly when climbing.

A lesson from checking the ship by screenshot: the screen on display can be
a tick or two behind Konami's sprite list, so a picture labelled from the
list can show the previous frame.  The ship's frame is now identified from
the screen's own pixels.

## 0.105: the ship back to Konami's outline, its second colour in one

0.104's frames still did not satisfy, so the ship went back to Konami's
sprites, with each one's second colour expressed in the one ink a cell
allows.  The climbing frame's light blue belly is a checkerboard stipple.
In the level and diving frames the red canopy is a black line inside the
ship, with the canopy's outer edge kept white; the level frame needed this
drawn by hand, since its red lies almost all along the top edge.  All three
frames share Konami's outline, so they match in motion.  An earlier attempt
that simply removed a few pixels where the red was had been rejected: those
pixels did not form an outline.

## 0.106: the colour fit made faster

Stage 1 felt laggy where the big hatch that launches enemies appears, and
at the boss.  A profile of the fast edition:

| | Quiet stretch | Hatch | Volcanoes | Boss |
|---|---|---|---|---|
| Whole tick (T-states) | 132,000 | 206,000 | 149,000 | 189,000 |
| Character conversion | 0 | 17,000 | 0 | 77,000 |
| Ticks a second | 26.9 | 17.2 | 23.8 | 18.8 |

At the hatch the extra time is spread out: Konami's own code (more enemies
to move), drawing the cells and drawing the sprites, with conversion only a
small part.  At the boss, conversion is the largest single cost: its
characters change colour as it animates, and almost none of them came from
the cache.

A bigger cache was considered and dropped.  Replaying the boss's
conversions through caches of different sizes, 128 entries would catch only
35% of them and need 4 KB, more than the memory free.  Instead the colour
fit's two hottest loops were rewritten, giving exactly the same results:
19% faster on average and 31% faster in the worst case.  The boss went from
18.3 to 20.9 ticks a second; the hatch barely changed, since conversion was
never most of its cost.

## 0.107: Konami's screen dissolve, and where the conversion time goes

### A census of the conversions

Every full conversion was recorded over the whole first loop (about 1,700
seconds of play).  There were 1,947 different characters, and converting
took about 3% of the processor in all, but it was bunched: in 87 separate
seconds of play it took more than a fifth.

| Stage | Different characters | New to the stage | Seconds over a fifth |
|---|---|---|---|
| 1 | 372 | 372 | 14 |
| 5 | 361 | 166 | 12 |
| 6 | 216 | 60 | 11 |
| 7 | 363 | 213 | 10 |
| 8 | 1,087 | 927 | 24 |
| 2, 3, 4 and the bonus stages | 71-237 each | | 1-5 each |

Characters a stage loads at its start make up 74% of the conversion time
(the stage 1 hatch and most mid-stage spikes); the rest are characters
Konami builds as it plays (the stage 1 boss, a stretch of stage 5, and
stage 8's brain dissolving).

Two ways of avoiding the work were considered and dropped:
* Converting at build time.  Konami's own code reads characters back from
  video memory (to make flipped copies at stage load, and in the dissolve
  below), so the MSX pattern and colour tables, and the compressed graphics
  that fill them, have to stay; converted tiles would be extra.  Every
  character of the loop is about 48 KB, and the loaded characters alone
  about 15 KB, against 2,500 bytes free.
* Loading each stage's converted characters from tape (multiload): a pause
  of tens of seconds between stages, rewinding after game over and at the
  end of each loop, and still nothing for the characters built during play.

### The screen dissolve

Stage 8 looked unplayable about 150 seconds in.  It turned out not to be
play at all, but Konami's screen dissolve after the brain is beaten: the
screen is eaten away, first every background turned black in one tick,
then eight passes over the character patterns that remove the pixels in a
speckle, 35 ticks in all.  The cartridge uses it in exactly two places: the
stage 8 brain, and the boss at the end of stage 7, which the player meets
only when stage 7's secret is not found.  The all-targets route had never
shown the second one.

On the simulated MSX the dissolve takes about 3.4 seconds.  0.106 took 18
seconds after the brain and 43 after the stage 7 boss.  Each tick changes
about 190 characters, which the port took to be a stage load: every
changed character on screen fully converted and the whole screen redrawn.

Skipping the effect was considered, but the game runs on underneath it, and
cutting it short would have put the port out of step with the MSX.
Instead, Konami's per-tick masking is now done natively on the port's
copies of video memory, ending with exactly the same bytes, so the lockstep
still matches; and while the dissolve runs, a character on a black
background is redrawn cheaply, keeping the colour that showed its
foreground, instead of going through the full colour fit.  As on the MSX,
the colours now stay put while the pixels go (0.106's refits had turned
stage 7's blue band white and cyan).

| Dissolve (seconds) | 0.106 fast | 0.107 fast | 0.107 smooth | MSX (simulated) |
|---|---|---|---|---|
| Stage 8 brain | 18 | 6.2 | 7.0 | about 3.4 |
| Stage 7 boss, secret not found | 43 | 7.4 | 8.3 | about 3.4 |

It is still about twice the MSX: what remains is redrawing every changed
character on screen, and the whole screen, on each drawn tick.

## After 0.107: a clear-out

With the source going on GitHub, every file was checked for a remaining
use: a trace of the files a full release build and the regression checks
open, short runs of every tool the technical description documents, and a
search of both documents.  Forty-five files had none and were removed: the
tools of the 0.31 hand port (only three of its modules were still in use,
and they moved into `spec/`), the relocator's development aids including
the first generator, one-off investigations in `spec/`, the rejected scroll
prototypes, and the masked-sprite prototype.  An assembler warning (a
repeat block closed with `endm`) was fixed at the same time.  The release
builds came out unchanged, byte for byte.

## 0.108: Konami's mapper writes

A study of what a port would gain by translating the MSX hardware ahead of
time, instead of standing in for it while Konami's code runs, found one
saving that needs no change to Konami's code.  The game switches its
cartridge banks by writing to 6000, 8000 and A000, about 13 times a tick in
play, and each write ran the whole page decision (`map_update`).  All 78
mapper writes in Konami's code were checked: every write to 6000 or 8000 is
followed, in straight-line code with no branch and no read through a
window, by a write to A000.  So the first writes now only record their
value, and the page is worked out once, at the write to A000 (about 5 a
tick).  It saves about 1,950 T-states a tick, and 2 bytes of fixed memory.

Over 300 seconds of the scripted play (`pacing.py`), the fast edition went
from 27.2 to 27.6 ticks a second (13.6 to 13.8 screens) and the smooth one
from 27.0 to 27.4 (21.6 to 21.9 screens): about 1.5%, too little to see in
play.  The builds do not play exactly the same game (the game's randomness
depends on instruction timing), so a few tenths either way are noise; that
script's play includes deaths and quiet stretches, so its rates run higher
than the figures over stages 1 and 2 below.

The same study measured where a tick's time goes with every tick drawn
(mean about 165,500 T-states on bench.py's workload): Konami's logic 34%,
the sprites 18%, the cells 16%, map tracking with the full comparison 11%,
paging 9%, the stars 7%, tile conversion 2%.  Two ideas were measured and
dropped: pre-shifted sprites (skipping all shifting saved only 5% of the
sprites' time), and converting each stage's tiles as soon as they load
(pauses of 8 to 9 seconds; the lazy converter never touches most of them).

## 0.109: the scroll tick and the sprite list

A scroll tick cost about 135,000 T-states more than an ordinary one (284,000
against 149,000 on bench.py's workload, every tick drawn).  Measured routine
by routine, most of that is work that has to be done: the full map
comparison's floor (an unchanged cell costs about 34 T-states, plus about 9
of group overhead), redrawing the changed cells (`draw_cells` is within
about 130 T-states a cell of a bare copy), converting the terrain characters
that arrive with the new column, and Konami's row shift (682 LDIs).  Three
things were not:

* After the shift has asked for a full comparison, Konami writes the new
  column through `nm_r11_hl_a`, which noted every cell as a region: about
  6,700 T-states a scroll for notes the full comparison made pointless.  It
  now skips the note when a full comparison is due (about 4,850 saved a
  scroll; outside scroll ticks the routine is hardly used).
* The generated comparison took a jump on every unchanged cell.  A changed
  cell's work is now out of line, so the usual case falls through (about 560
  a scroll, less than estimated: stars make many cells count as changed).
* Konami's sprite list is usually full, with about 29 of its 32 entries
  parked below the screen, and it was walked twice: once to find its end,
  once backwards to draw.  One pass now collects the entries on screen into
  `spr_vis` (32 bytes) and the drawing works back through those (about 810 a
  drawn screen).  The ship's second colour (patterns 4, 12, 20, never drawn
  since 0.100) is now dropped before its colour is looked up, not after.
  The sprite list cannot simply lose that entry: it is Konami's, written
  every tick, and the lockstep compares it with the MSX.

To make room in fixed memory, the title's full stop (`title_dot`, 46 bytes)
moved to bank C, which `spec_title` already maps.  It now writes through the
LDIRVM stand-in rather than `vbulk` directly: `vbulk` borrows the shadows'
banks into C000 while it reads its source, so a source in bank C would have
been hidden.  `far_dz_pat` moved to the low area (7C58).

Over 300 seconds of the scripted play (`pacing.py`), against 0.108: the fast
edition from 27.6 to 28.0 ticks a second (13.8 to 14.0 screens), the smooth
one from 27.4 to 27.8 (21.9 to 22.2 screens), about 1.5%.

Considered and left: interleaving the sprite patterns (left and right halves
alternating) would save `set 4,l` and `res 4,l` on each of a sprite's 16
rows, about 1,000 T-states a tick, but ten places touch the sprite pattern
copy, the bulk upload among them; and a leaner star-list rebuild (about 125
a tick) would drop the guard that keeps a stale star bit from corrupting
another list's counters.

## 0.110: one edition, adaptive pacing

The two editions had grown close in play, and a full profile was made to
choose between them.  The measurements of 0.95-0.100 had been made with
scripts that were never kept; they were recovered from an earlier session's
workspace and are now kept in the linked clone (`local/tools/measure/`),
where the MSX run reproduced its saved data row for row.  Over the first
two stages in light play, 0.109's fast edition ran at 98% of the MSX's
speed and the smooth one at 91%; but the smooth edition's extra screens
came unevenly (one in four jumped two ticks, the gaps between screens ran
from 1 to 4 frames), so it looked little smoother than the fast one.

A third scheme was tried: draw every tick while the game keeps up with a
rhythm near the MSX's, leave a tick undrawn while it is behind by more than
a slack, never two in a row (`pace_adapt`, bank C).  Five settings of rhythm
and slack were measured; all fell between the two editions in light play.
Over the whole first loop with every weapon, though, the smooth edition
fell to 77% of the MSX's speed while the adaptive rule held the fast
edition's (86% against 87%): under load it falls back to one tick in two,
and where there is room (stage 2, stage 8) it draws up to about two ticks
in three.  In play it looked better than either, since steady motion shows
most in quiet stretches, and it became the only edition (rhythm 15 eighths
of a frame a tick, slack one frame; the title shows A).  The fast and smooth
schemes remain build options, so the change is easy to reverse if players
prefer them.

Input lag on the MSX had been quoted as about 3.2 frames from a different
method (24 presses, no beam term); measured exactly as the port is, it is
3.1 to 3.2.  The Spectrum figures of a first profile were a frame too high
(the screen flips in the interrupt at a frame's start, not its end) and
were corrected before use.

## 1.0: the Spectrum Next build

What began as a question about what a Next could add became a second build
of the same tree.

* **Speed first.**  At 28 MHz the 128K build ran far too fast, even at
  7 MHz, so the Next build took screens at least two frames apart (with
  the 128K's adaptive pacing, about 26.7 ticks a second).
  The first `.tap` hung a Next emulator, which expects `.nex` files, so the
  snapshot is packed into a `.nex` (`sna2nex.py`).
* **Paging.**  Any write to port 7FFD on the Next also puts the ROM back at
  0000, where the Next build keeps its own code, so the Next pages through
  its MMU registers instead.
* **Layer 2 and hardware sprites** replaced the 128K's renderer: the MSX's
  tiles in their own colours, and the sprites in theirs.
* **Smooth scrolling.**  The screen is shown up to 7 pixels to the right of
  Konami's map and the gap closes a pixel a tick, using Layer 2's hardware
  scroll as a circular buffer.  Things that then looked wrong were fixed
  one by one: capsules and walkers hopping in 8-pixel steps (they move with
  the scenery through a Konami helper, which the Next now notes), enemies
  drawn with characters (lifted out and drawn as sprites), the stars
  twinkling in only half their cells, stray graphics on the title and after
  a death's wipe.
* **The MSX2 graphics.**  The patch "Nemesis - Gradius ENHANCED" turned out
  to keep Konami's tile layout and loader and change the data, so its
  graphics drop into the Next's drawing unchanged.  They were first taken
  from video memory captured in openMSX; the Next build now reads them from
  the patched ROM itself (`msx2_pack.py`), which needs the patch's IPS just
  as the build needs the ROM.  Running the patched cartridge in the
  project's own simulator was tried first and dropped: its start-up copies
  the BIOS into RAM, searches the slots for a sound chip and unpacks code
  over page 0, far more than the simulator models.
* **Colours.**  Blobs showed in the stage 1 ceiling (the patch also
  changes some map pieces, now taken too), and the ship's and the options'
  colours looked doubtful.  The patch sets sprite colours line by line in its own
  code, so the Next follows its tables; the options and the explosion were
  then given red, orange and yellow, after the arcade game.
* **A black block over OPTION**, at a boss, was first blamed on the
  patch's boss colour tables, wrongly: it was the Next's handling of
  enemies drawn with characters, which also took them out of the status
  rows, where there is no background to put back, and wrote character 0
  over the power-up bar (seen when stage 1's volcano rocks fall to the
  bottom).  Found by watching the status row's characters change in
  ZEsarUX.
* **The status line in the old graphics.**  At a new game and after a
  life is lost, the screen before the stage showed the status line and
  score in the original graphics and colours for a moment, until the stage
  loaded: Konami loads them there, and the patch loads its own.  The Next
  now gives that screen the coming stage's palette and bottom third, and
  takes the patch's font, so it matches from the start.
* **The title logo.**  The logo on the title screen was still Konami's.  The patch's is a bitmap, shown by switching the top of
  its title screen to a bitmap mode, so the stage replay never saw it; it
  is stored as it is in the patched ROM.  The Next now draws it on Layer 2
  in place of Konami's, leaving the text as it was.
* **The shield** broke the ship up: Konami draws it in place of the
  ship's white layer, and the patch, whose graphics assume its own code,
  keeps the layer and draws the barrier separately.  Found in JNEXT and
  compared with the patched cartridge in openMSX; the Next now does what
  the patch does.
* **30 ticks a second.**  The Next felt a little slow against the MSX.
  The original runs at 30 ticks a second on a 60 Hz machine (measured from
  a video) and about 27 on a 50 Hz one.  A first 30-tick build
  only set the adaptive rhythm and let screens come a frame apart: in
  ZEsarUX the processor held it near 31, but JNEXT, which runs the build
  faster, ran it far too fast, since the pacing only ever skips drawing and
  never holds the game back.  Screens are now capped at 2, 2, 1 frames
  apart, exactly 30 a second.  The measurements also
  showed that ZEsarUX runs this `.nex` at 14 MHz unless told otherwise,
  and that even at 28 MHz it leaves some ticks undrawn.
* **Comparing with the MSX2 patch.**  Both played through every stage,
  invulnerable and with every weapon, the patched cartridge in openMSX and
  the Next in ZEsarUX, captured at the same map distances (E063).  openMSX's
  screenshots lag the emulation when it runs unthrottled (the first pairs
  looked a screen apart), so the MSX2 side was rendered from its video
  memory instead.  Everything matched except the patch's palette changes
  (the red volcano sections, a flashing colour in the stage 8 boss, a fade)
  and its recoloured Big Core.  Neither was taken: the volcano rocks are
  drawn in fire colours instead, and the Big Core keeps its colours.
* **The walking cannons in colours of our own.**  Their colour in the
  patch's stage 1 palette is an olive close to the trees'.  The patch can
  only colour sprites row by row (the MSX2's limit), but the Next draws
  every sprite as a 16-colour pattern, so they were given arcade-style
  colours, chosen from mock-ups: teal and orange, and red with a blue
  core for those that leave a power-up.
* **Stage 1's enemies after the arcade game.**  The single-coloured
  enemies were redrawn after the arcade game's sprite sheets, fitted to
  the MSX's sizes.  Each was matched
  frame by frame and mocked up before anything was built, and the matching
  went wrong in instructive ways: it was first done against the patch's
  sprites instead of Konami's originals (now read straight from the ROM
  by replaying Konami's sprite loader); the jet and
  the pod were first matched to the wrong arcade sprites; the pod's frames
  first turned the wrong way (it squashes vertically, played forwards then
  back); the robot's hood came out pointed until it was coloured in bands;
  the capsules were found only in the Vic Viper sheet; and the walker's
  twelve patterns turned out to be three drawings in four orientations.
  The art is kept as data in the repository (no new build dependency; on
  Konami's stated terms for fan use), and two build switches can leave out
  either half.  The red versions for enemies that leave a
  capsule were first given to the turrets by byte 14, as Konami does for
  sprites, on the assumption that Konami could not colour a turret alone.
  But the MSX does show red turrets: the ROM showed Konami draws them with
  a second set of red characters (frames 09-0E), which now get our red
  turret.
* **Stage 2's enemies.**  A static survey of stage 2 from the ROM found its
  sprites the same as stage 1's and its waves, pods, jets and saucers
  already covered.  New were the enemies that materialise in columns of
  five (Konami's type 8, a disc that grows over four frames; the
  disassembly calls them a wall of stones), drawn from the arcade's
  growing ring, and its turrets: four sets, every frame with the pixels of
  one of stage 1's, so they take stage 1's drawings in a blue tint, red for
  those that leave a capsule.  That needed a character table per stage.
* **The patch showing through.**  A fan moving diagonally flashed in the
  patch's colours: its four characters on the screen can lag a tick behind
  its position, part old drawing, part new, and matched nothing.  Character
  enemies are now recognised by Konami's frame number (the object's byte
  12).  Then the turrets and capsules turned out never to show our
  drawings at all: Konami moves them with the scenery, and the Next left
  such objects in the map, drawn from the patch's characters.  Those that
  are ours are now lifted out too and drawn as sprites that move with the
  scenery.
* **No IPS.**  The build read the patch's graphics from the user's IPS at
  every build, and drawing our own on top meant keeping its versions
  underneath.  The graphics were read from the patched ROM once and are now
  data in the repository, ours to change; a `.nex` built from them matched
  the IPS-built one byte for byte, and the build no longer needs the IPS.
* **The character pool.**  To keep one set of artwork, the background is
  now drawn from full-colour characters (a shared pool of 8 by 8 blocks
  with a map per stage), with our drawings of the turrets and capsules in
  it, so they stay in the scenery.  Two bugs on the way: the shared code
  marks every tile as changed once a stage starts (for the 128K's
  converter), so for most of a stage the Next took every character as
  written by Konami and the pool was hardly used, which nothing showed
  until a turret was seen in the patch's colours; and a block copied into
  column 31 carried into the next line's address, so a cell at the bottom
  of a third ran past FFFF into the Next's own code bank, which in play
  brought up the title logo.  A snapshot taken in JNEXT found the second:
  its code bank, compared with the build, showed the cell's lines.  The
  smoke test now checks that the pool is in use and that the code bank is
  intact.
* **One set of artwork.**  With the pool in place, the stage files still
  held every character in the patch's two colours, and our drawings of the
  character enemies were kept a second time as whole sprites for the
  enemies lifted out of the map.  The pool and its maps are now the
  committed artwork (made once by `local/tools/pool/make_pool.py`, byte for
  byte as the build had been making them), and the stage files keep only
  the sprites, the palette, the line-colour tables and the stars, the two
  characters Konami rewrites in play (a third, F8, was first kept as one
  whose colours Konami cycles; it is the ship's shot, which Konami only
  places in the map, and was cut too).  Lifted-out enemies are made from the
  pool's blocks, so an enemy looks the same in the map and out of it; they
  came out identical to the previous build for every stage, frame and row,
  apart from frames 29-2C, which Konami builds from the fans' characters
  and which now show our fans' pieces instead of the patch's.  The screen
  before each stage draws its status line from the pool.  Konami's screen
  dissolve, which ate the two-colour copies, became a fade to black of the
  Layer 2 palette over the same ticks, with the status line and stars kept
  in an unfaded copy of the stage's colours, as Konami's dissolve spares
  them.
* **Stage 1's ground edge in brown.**  The patch draws the ground's lower
  edge (a dithered line of character 43) dark brown on magenta in stage 1
  but dark brown on the lighter brown in stage 4.  The browns looked
  better; stage 1 is coloured as stage 4 (now in the character pool).
* **The Big Core moves smoothly.**  Konami moves it 8 pixels at a time,
  every 3 to 5 ticks; it is now drawn with sprites that glide towards the
  next step, which Konami has always decided by then.  On the way in, the
  first try stepped at the right edge: the sprites were made from what
  Konami had drawn, which stops at the screen's edge, so the glide pulled
  the boss's leading edge up to 7 pixels short of it between steps.  The
  part still off the screen is now made from Konami's boss tables.
* **The status line holds still with the boss on screen.**  A line
  interrupt at line 176 resets the scroll for the status rows, alternating
  with the frame interrupt.  The boss's patterns were sent with interrupts
  disabled, and an interrupt that comes then is lost on the Next; the
  alternation went out of step and the status rows took the play area's
  scroll.  A first fix moved the split to the copper and dropped the line
  interrupt; in JNEXT that build ran faster than before and the game-over
  music was choppy (the two builds compared side by side; ZEsarUX showed
  no difference), so it was withdrawn.  The interrupts are as they
  were, and the boss's patterns are now made and sent with interrupts on,
  in a buffer of their own, and made and sent again if the frame interrupt
  ran in the middle (a first try shared the interrupt's buffer: the boss's
  blocks took the interrupt's patterns).
* **A table read past its end.**  The Big Core's vertical glide looks up
  8 * n / c in a small table; at c = 5 (stage 1's difficulty) the last tick
  needs a fifth entry, and the table had four.  The byte after it was the 06
  of the next routine's first instruction, the right value by luck, until
  new code was put there and the boss jumped 33 pixels every fifth tick.
  The table now has the entry.
* **Stages 2 and 3 in the arcade's colours.**  Stage 2's bricks and balls
  came from the arcade sheet's tiles; stage 3's Moai heads and stone kept
  Konami's shapes and were shaded in the arcade's yellows, golds and
  creams.  Neither fits the stage's 16 colours, so a stage can now have a
  scenery palette of up to 15 more (Layer 2 entries D1h-DFh), loaded with
  the stage and faded in the dissolve.  `local/tools/pool/put_blocks.py`
  writes such blocks into the pool.
* **Stage 3's disc and wheel.**  Our sprite drawings had been matched to a
  stage only where its patterns were stage 1's, so stage 3's own enemies
  could not have any.  A drawing is now of a pattern as some stage loads
  it, and goes wherever a stage's pattern has that content: the disc after
  the arcade's frames, and the spoked wheel, which the arcade lacks, as
  Konami's shapes lit from one side so the light holds still as it turns.
* **Stage 3's boss pieces move smoothly.**  Konami moves the round pieces
  a pixel at a time but draws them into the map, so they jumped a
  character at a time; they are now lifted out and shown as sprites at
  Konami's positions.  The code no longer fitted below the Next's sprite
  buffers, so part of it lives in two free stretches of the buffer area.
  Stage 4's mid-boss, a stream of flyers in the same slots drawn the same
  way, moved in the same 8-pixel jumps and is handled by the same code.
  Konami blanks the background at each flyer's four corners as it draws
  it; lifted out, the corners show the background instead, since black
  squares would have to be drawn on purpose.
* **The ship's and the status line's colours.**  The ship's line colours
  and the status line came from the stage's palette, so the ship's red
  canopy turned brown in stage 3 and the status line looked different
  from stage to stage.  Both now keep stage 1's colours throughout, in
  palette entries of their own.  A first try at the ship put its colour 1
  in a palette entry that the sprite palettes already use for one of
  Konami's colours, which turned part of the ship magenta; it uses a free
  entry now.
* **The bonus stages.**  The pack covered stages 1-8 only, so the four
  bonus stages kept Konami's own characters and sprites in the previous
  stage's colours, and the ship's patterns were drawn with the previous
  stage's line colours, breaking it up.  A stopgap that copied stage 1's
  sprites in also replaced the bonus stages' own score sprites.  The
  patch does have graphics for them (no palettes); they were read from the
  patched ROM the same way as the other stages', checked against the
  patched cartridge in openMSX, and became one shared stage file and four
  maps.  Our art goes on top from stage 2, matched by content because the
  patch draws some of the same bricks and turret pieces under other
  character numbers.  The balls, the only difference between the four,
  are our arcade sphere in green, yellow, blue and magenta, toned down
  from a first, brighter set.
* **Stage 2's cut-off bricks.**  Short slabs showed at the ends of the
  rows of bricks.  A first diagnosis, from the static replay of the stage
  map, put the two characters at the edges of the hanging clusters and
  proposed redrawing them; the map dumped from the running game showed
  they are the rows' end caps, tips a few pixels wide on the MSX.  They
  are not wall, so they are now blank, which matches what collides.
* **Turrets in every stage.**  The first placement of our turrets took a
  stage's turret characters only where they were stage 1's in all three
  thirds of the screen, so stages 3, 5, 7 and 8 kept the patch's (green in
  stage 7's palette).  Every turret in the game is one design, ordinary or
  red for those that leave a capsule, and those four stages now take ours
  wherever Konami's own characters show it, in the colours Konami gives
  them there.
* **Stage 5, the bone stage.**  An MSX-only stage, so there is no arcade
  art to follow.  The patch draws the bones in two colours and black and
  shades them by stippling; they are now shaded on a 9-step ramp from ivory
  to a warm brown in the stage's scenery palette, lit from the top left,
  the stippling smoothed into tones.  Rather than redraw each character by
  hand, every screen of a run through the stage was rebuilt from the pool
  and reshaded as a whole, and each character took the result it got most
  often.  The stage's own enemies were shaded the same way from Konami's
  shapes: crescents in salmon and orange (with a red twin), the balls in
  pink with their inner ring of dots as a darker band, the bone claws in
  gold and the stars in ice blue, in two new sprite palettes.
* **The turrets and skeletons rise smoothly.**  Stage 5's turrets, which
  slide out of the floor, the ceiling or a ledge, and its skeletons, which
  come out of the floor and down from the ceiling, are characters that
  Konami draws a row at a time, so
  they rose 8 pixels a step.  They are now redrawn every screen a pixel
  step at a time, inside the rectangle Konami draws them in, so they never
  show where Konami has not put them.  Konami makes a skeleton's last step
  as it is out and no longer counts ticks for it, which first showed as a
  final 9-pixel jump; the Next counts that step itself.  The open mouth is
  still Konami's instant change of drawing: a few pixels, and it suits the
  sound.  The code did not fit in the Next's code bank, so it has an 8K
  page of its own, called once a screen.
* **The laser's black boxes.**  Konami writes the shot and the laser into
  its map, and on the MSX each of their cells is a black 8 by 8 with the
  shot through it.  On the Next's detailed scenery these showed as black
  boxes over bones, rocks and enemies.  Every shot cell is now drawn again
  over what Konami saved from under it, the shot's lit lines on top with a
  one-pixel black edge above and below, so the beam stays visible over
  bright scenery.  It works in every stage, not only over stage 5's
  skulls.  Two details needed care: stage 5's smooth drawing has already
  painted some cells this screen, which must be kept rather than redrawn at
  Konami's position, and the scenery under a lifted-out enemy is Konami's
  map, not the enemy.
* **The stars that missed the skeletons' mouths.**  The stars the stage 5
  skeletons release appeared about 48 pixels to the left of the mouth.
  It was not timing: Konami creates each star on the right tick and at
  the mouth.  The patch gives these stars the colour byte 80h, its code
  for a table of line colours, and the Next read bit 7 of it as the MSX's
  early clock bit, which shifts a sprite 32 pixels left.  For Konami's
  objects 80h is now the patch's table, with no shift.
* **The Moai's rings.**  They flashed between blue and a greenish yellow
  (the patch's colours for objects of colour 0 in stage 3).  They now
  flash between blue and purple; the stage's palette has no red.  Only the
  rings change: nothing else in stage 3 takes the new pair.
* **Stage 6.**  The robots are the arcade's, in the fans' palette.  The
  brains and the ball chains on them, which Konami moves a character at a
  time, are lifted out and shown as sprites in the arcade's drawing: a
  brain glides towards its next step, and each ball slides from its place
  in the chain's old drawing to its place in the new.  Konami takes a
  brain off as soon as it touches the left edge, so brains and their
  chains vanished there; they now glide on off the screen as ghosts that
  nothing collides with.  The first version kept one ghost per brain
  slot, and a new brain arriving in that slot cut the ghost short; each
  slot now has a ghost of its own.
* **Stage 7.**  The amoeba and its doughnut and burst follow the arcade's
  pink cell, in a palette 15 of the stage's own.  The conveyor belts were
  restyled like stage 5's bones, from every screen of a run through the
  belt section: one lilac band with a darker rim, and white hollow rings
  for the patch's green beads.
* **Ghosts in stages 3 and 4.**  The pieces of stage 3's boss and the
  flyers of stage 4's mid-boss vanished at the left edge in the same way:
  Konami clears only the first byte of a piece's slot, leaving its X
  wrapped past the edge.  Each piece's steps are now watched, and one
  that leaves this way glides on off the screen at its own rate.  A piece
  that is shot does not move off the screen first, so it is not ghosted.
* **Stage 8's brain.**  The patch's brain, Konami's characters recoloured,
  was replaced by the arcade's, which the arcade draws as part of the
  scenery and which fits Konami's 8 by 8 characters at full size once it
  is moved a pixel right and three down.  Konami's tendrils became blank
  and the electricity six bolts of sprites from the brain to the six
  sockets, taken from the arcade's lines and squashed to fit.  They are on
  from when the brain's screen scrolls in, flicker throughout and swap
  cyan and green now and then, which reads as arcing better than a plain
  swap of colours did.  A bolt goes when its socket is shot.  The fight
  can end after only a few sockets are shot, because Konami ends it on a
  timer as well; that is Konami's game and is unchanged.  In a first
  version the bolts stayed on screen through the dissolve; they now fade
  with the room.  Konami's tendrils never collided: the disassembly's
  comment on the map collision routine says the opposite of what the
  code does (characters 01h-76h are solid, 77h and above only in stages 3
  and 4).
* **The ending.**  The Vic Viper's flight towards the camera, 6 drawings in
  the patch, has 16 sizes drawn from a head-on model of the ship (its
  wing tips swept up a little), timed by Konami's own counters so the
  ending's length is Konami's.
* **The arcade's Big Core.**  The Big Core is now the arcade's drawing in
  the arcade's colours, which do not change from boss to boss.  It is
  wider than Konami's 11 characters, so it is trimmed, and the cut edge is
  shaded a step darker so the crop does not look sliced off.  The core is
  a sprite of its own, so it can be placed to the pixel and turn from grey
  to blue as the boss is hit, and disappear when the boss is beaten, as in
  the arcade.  A first try drew the walls as vertical lines; a frame of
  the arcade game showed them as a strip of four bars and a ball in the
  mouth, which is what is drawn now, with bars taken away as Konami takes
  its walls away.  Pictures of the boss for this work were made from the
  ROM and the arcade sheet directly rather than from runs of the game,
  which was much quicker.
* **Memory.**  Bank 8's code area is full (3 bytes left below 2000), so
  the new code went into `nx_tur.asm`'s page, which then overflowed; stage
  6's tables moved to the top of that page.  The new drawings are in pages
  of their own (57, 59, 61, 63 and, since 5 November, 82), mapped in only
  while they are read.  Page 81 and pages 83-91 (80K) are still free.
* **A packer bug.**  A build broke every stage's graphics within seconds
  of the start: a loop added to `nx_pack.py` for the ending's drawings
  reused the variable that held the offset of stage 6's tables, which were
  then written over the wrong place.  The pack step's loop variables are
  now kept distinct, and stage 6's tables were checked in the file and in
  the game after the move.
* **The dissolve's fade.**  After the release candidate was tried on a
  real Next, the fade at the stage 7 boss and the stage 8 brain was found
  to look like a few separate steps rather than a fade.  It took one level
  off every colour channel every 4 screens: seven steps, and dim colours
  went black after two or three.  The Next's palette has only 8 levels a
  channel, so a fade that keeps every colour's hue has at most 7 steps for
  a grey.  Taking one level off one channel at a time gives 21 steps, but
  rendering the frames showed stage 7's pale lilac-greys turning cream,
  green and blue in turn, which was dropped before it was tried.  The fade
  now scales every channel by the same fraction and rounds, in 21 steps
  that follow Konami's own progress through the dissolve, so it ends when
  the dissolve ends; bright and dim colours change at different steps, so
  the screen changes at nearly every step (18 different frames on stage
  7's screen).  The high, warbling sound under it is Konami's (sound 3E,
  which the dissolve starts), as on the MSX.
* **The hatches.**  The arcade's hatch (its body, with the last two frames
  of its opening doors upright on top) was mocked up for the enemy hatches,
  and the patch's drawing was preferred after all; what made the patch's
  hard to see was its darkest navy, close enough to black that the eye
  took it for background.  The navy, and the dark brown of the shot
  hatch, are now a step lighter wherever the hatch appears (stages 1, 2
  and 4, and stage 8's own colours), and only in the hatch's own
  characters.  The extra blocks took the character pool past its old last
  page into the Big Core's, so the Big Core's drawings moved two pages up.
  Scorch marks and a dent on the shot hatch were mocked up as well and
  dropped: at that size they read as a corrupted graphic.
* **One tree.**  The Next's changes to shared files are under `ifdef NEXT`,
  its takeovers of Konami's instructions are in `gen.py` with the 128K's,
  and the 128K builds are byte for byte those of 0.110 apart from the
  version on the title.  `verify.sh` builds the `.nex` too, and
  `release.sh` makes it and, with ZEsarUX, plays it for a minute.
* **1.0.**  Both builds take the version 1.0 (V1.0A, V1.0N; the letters
  stay: A for the 128K's adaptive pacing, N for the Next), shown right-
  aligned at the top right of the title.  The Next's smoke test never
  passed before: it played the game as it was and the ship died before the
  scroll was sampled again; it now plays an invulnerable copy at 28 MHz.
  Before the release the Next build was played through in ZEsarUX (every
  bonus stage, two whole loops, deaths to game over from six stages) with
  its code and data checked throughout, and on a real Next (KS2) and an
  N-Go.

## 1.1: no MSX graphics

Up to 1.0 the 128K build ran Konami's graphics code much as the MSX does.
Konami's compressed graphics were in the banks, its loaders unpacked them
into copies of the MSX's pattern and colour tables in pages C and D, and
each character was converted to a Spectrum tile when it was first shown
(the colour fit, its cache and the stage colour rules, all at run time).
In 1.1 that layer is gone from the 128K build.  Every graphics load is a
load of tiles and sprite patterns converted when the game is built, and
the Next build was moved onto the same code.

The reasons were these.  Fixed memory was full (60 bytes free), and it
was what every recent change had been short of; the video stand-ins, the
converter and its bookkeeping, the star twinkle on MSX pattern rows and
Konami's loaders were all in it.  The conversion came in bursts: 0.107's
census found seconds of play in which it took more than a fifth of the
processor.  Stage starts and restarts paused while the graphics were
unpacked and converted, and the dissolve still took about twice the MSX's
time.  And the layer was the most complicated part of the port: the
colour fit, the cache, the lazy conversion, the rules at run time, the
copies of the tables and the reconversion at a stage change.  0.107 had
set converting at build time aside because Konami reads characters back
from video memory, to make flipped copies at a stage load and in the
dissolve.  Both happen inside events that can be replayed when the game
is built, provided there are no others, and the first job was to find
out.  The work was done on a branch, so the Next went on building from
the main line until it was moved across.

### The census

`census_gfx.py` (in the linked clone, `local/tools/native/`) ran the
original cartridge in msxsim with the Spectrum build's front end, the
ship sweeping up and down and firing, with every weapon.  One run (40,000
ticks) took the route with every hidden target, the ending and the start
of the second loop; the other (47,169 ticks) the plain route with a death
in each stage, the stage 7 boss without the secret, game over and the
title.

* Konami's writes to the pattern, colour and sprite pattern tables are
  exactly the events found by reading the code, and no others.  In play:
  the stage loads (a new game, each stage, and after the screen before
  each life), the Big Core's load in stages 1-6 (its colours different in
  each stage), the star twinkle, the dissolve and the ending's loads.
  Outside play: the title, the screen before each life, game over, and
  clearing the video memory at boot.
* No character that a stage's load leaves as it was is ever shown in that
  stage.  Character 00 of each third is never loaded by anyone and is
  always blank, and bonus stage 9's sprite pattern 50 is stage 2's, which
  is always so because stage 9 is entered only from stage 2.  Each stage
  can therefore be stored as a complete set and unpacked straight into
  place.
* The other screens do show what was there before.  The screen before
  each life shows the stage just played (the title's characters at a new
  game), and game over and the title after it show stage 8's.  Those
  loads are small, and are stored as patches over what is there, with a
  mask, as the MSX writes them.
* Of the RAM Konami's loaders use as scratch, the game reads only E100
  before writing it again, and it is 1 after every stage and Big Core
  load.  The rest of each loader is game logic (the Big Core's load also
  clears the objects), so only the routines inside the loaders that write
  video memory are replaced; a native load sets E100 to 1.

### The sets, made when the game is built

Before anything changed, a check of the pictures was written:
`spec/screen_lockstep.py`.  It runs two test builds that draw every tick,
a reference and a candidate, side by side with the MSX original, the same
input to all three.  After every tick it checks each build's Konami RAM
against the MSX, as the lockstep does, and compares both of the
candidate's screens with the reference's, byte for byte.  It was proved on
short runs first: 1.0 against itself matched, and a build with the
power-up bar's paper changed was caught at the bar's first drawing, with
the 24 cells named.  Then a 1.0 with Konami's bank 3 code moved 6 bytes
matched 1.0 over the whole route twice, with every hidden target (40,000
ticks) and with a death in each of stages 1-8 (50,000 ticks), so it
raises no false alarms.  It runs at about 110 ticks a second.

`spec/native_sets.py` replays every load event from the ROM in msxsim and
converts each character with the rules 1.0 applied at run time, which
`spec/tilemodel.py` does as a function: the colour fit, the power-up
bar's design, the title logo, the stage colour rules, inversion and the
nuke capsule.  A checker (`native_check.py`, in the linked clone) ran 1.0
through both routes, keeping a model of the tile set the native build
would have, and required every tile 1.0 converted, and every sprite
pattern on show, to equal the model's.  In the bonus-stage route all
4,370 tiles that 1.0 converted matched; in the route with deaths, game
over and back to the title, 5,299 of 5,305.

The six that differ are a bug in 1.0.  Stage 3's Moai rule applied only
to characters first drawn before distance 195h, and some characters
appear both among the Moai and past 195h, so after a restart from a
checkpoint past their Moai appearance they stayed in the fit's white.
The native build decides per character: they always take the Moai's
colours, as in an uninterrupted pass.  The list had to be built from
every pass through the stage, not only the first, and has 561 characters
(`spec/native_moai.txt`).  This difference from 1.0 is intended.

Two things turned up on the way.  The Spectrum title's own full stop
(`title_dot`) became part of the title's patch.  And on the MSX, the
dissolve after the stage 8 brain can still be running in the tick the
ending's graphics load, and wipes part of what was just loaded (the
status font, until the ending loads it again 800 ticks later).  1.0
reproduces this, and so does a dissolve done chunk by chunk as Konami
does it, so the native one was written that way.

### The cut-over

The change was made in one step: the sets fit only once the MSX layer is
out, and the stars and the dissolve depended on that layer.

Each event site in Konami's code now calls an entry point in
`spec/native.asm` (`nl_stage`, `nl_bigcore`, `nl_prestage` and so on),
which unpacks the event's data into bank 7: a stage's complete set
straight into the tile set (DB00-F5FF) and the sprite patterns (from
F800), a patch into page D's work area and from there into place a
character at a time.  Every cell is then redrawn, as after 1.0's loads.
The packed pieces are in other banks, which map at C000 as bank 7 does,
so the two cannot be mapped at once.  ZX0 reads its input strictly in
order, though, so the unpacker reads it through a 256-byte buffer in
fixed memory (`nl_buf`), refilled from the source bank as it empties, and
writes straight into bank 7.  Konami's loaders in bank 0 are then
unreachable and are left out of the build (`reloc/gen.py`'s `LEAVE_OUT`):
a new kind of change for the relocator, which had only ever replaced
instructions.  The video stand-ins keep only their name-table and sprite
work.

The stars are the same two characters (F6, F7) in every stage, blank
when loaded with a single pixel's row when lit.  `blink_native` now puts
the tick's rows into row 0 of those tiles in each third, and the
attribute a star tile takes when it first shows a pixel is worked out
when the game is built and stored with each event's data.

The dissolve now works on the converted tiles.  The colour pass gives
every tile in the chunk black paper, and each pattern pass ANDs the
tile's rows with Konami's mask for the pass.  The first version was
visibly unlike 1.0 and the MSX in stage 7: the blue shapes on the left
came out as green discs.  1.0 had decided per tile which colour showed
the foreground and kept the MSX's foreground pixels.  That is now
modelled (`tilemodel.dz_post`), and the tiles where the simple rule gives
something else are stored for stages 7 and 8 as a patch, applied after
the colour pass's last chunk (about 1.8 KB packed for the two).  With the
colour pass exact, the pattern passes give exactly what 1.0 showed, since
1.0's pixels were the MSX's pattern masked row by row.  The chunk buffer
turned out to be EA00-EBFF, not EA00-EAFF: a chunk is up to 512 bytes.
The census shows nothing reads it after the dissolve, and the lockstep
excuses it.

The packing (`spec/native_pack.py`) first placed the pieces first fit,
which stopped fitting once the dissolve's patches were added.  It now
places them largest first, each where it fills the room best, and
searches back when that leaves a later piece no room.  Page C and page D
after their code are free room too, asserted against the end of each.
`build.py` runs the packer (about 15 seconds) when any of its inputs is
newer than what it last wrote.  What it writes is Konami's graphics,
converted, so it is not in the repository.

The checks, against 1.0, with Konami's RAM matching the MSX throughout:

* With every hidden target (40,000 ticks: stages
  1-2-9-3-10-4-11-5-6-7-12-8, the ending and into the second loop), the
  screens were identical to 1.0's on every tick, the dissolve after the
  stage 8 brain included,
  apart from its first three ticks: 1.0 converted the changed tiles a few
  a tick, and its screen caught up with the colour pass where the native
  build shows it at once.  The screen lockstep allows those ticks.
* With a death in each of stages 1-8 (50,000 ticks: the screen before
  each life, the stage 7 boss without the secret and its dissolve, the
  ending, the second loop), the screens were identical apart from 88
  ticks in stage 3 after the restart, all of them the Moai fix.
* Game over five times, with the title and a new game after each (20,000
  ticks, a new option of the screen lockstep), identical.
* `verify.sh` and the simulated tape load pass.  The lockstep compares
  only the name table of video memory for the native build, since there
  are no copies of the MSX's tables, and excuses the loaders' scratch RAM
  after a native load.

Removed with the layer: `vbulk.asm`, `rules.asm`, `convert_e.asm`,
`barstyle.asm`, and the checks of the run-time converter, `check_tiles.py`
and `test_convert.py`.

### Sizes and speed

The packed graphics are 28 pieces, 27,215 bytes, with about 1.4 KB of
room left in the banks in pieces of at most 384 bytes.  In fixed memory
`platform_end` is A500, leaving 2 KB free below AD00.  The tape grew:
70,445 bytes against 1.0's 63,340, about 40 seconds more at the ROM's
speed, because the packed graphics do not compress again on the tape,
where 1.0's MSX graphics and code did.

Over stages 1 and 2 in light play (`specrun.py`, 120 seconds) the native
build ran 24.57 ticks and 14.7 screens a second, against 1.0's 24.16 and
13.7.  Over stages 1-6 (`perfprofile.py`, 1,500 seconds, every weapon),
which now also reports the gaps between screens and the fewest screens in
any second:

| | 1.0 | 1.1 |
|---|---|---|
| Ticks a second, by stage | 22.0-25.5 | 23.1-26.6 |
| Screens a second, by stage | 12.3-17.1 | 13.3-18.9 |
| Fewest screens in any second, by stage | 0-4 | 6-8 |
| Gaps of 9 frames or more | 247 | 38 |
| Longest gap | 90 frames | 28 frames |

1.0 had a second or more with no new screen in each of stages 2-6, while
it converted tiles.  The gain is less in the average than in
consistency: played, there are no obvious lags at the turrets and the
like, where 1.0 converted tiles as they scrolled in.

### The Next on the same code

The Next never used the 128K's two-colour tiles.  Its Layer 2 renderer
draws the scenery from the character pool, and every character the pool
does not cover (the stars, the Big Core until the next load, the title
apart from its logo, the screen before each life, game over and the
ending) pixel by pixel from a store of character rows laid out as the
MSX's tables: pages C and D at E800, and bank 7's F800 for the sprite
patterns.  That store was kept, and is now filled from data made when the
game is built, at the same load hooks as the 128K's.  Konami's loaders,
the decompressors, the video stand-ins for patterns and colours, and
`lo_stage`'s overlay of the MSX2 patch's data at run time are gone.
Making all of those characters Layer 2 blocks was set aside: the pool
already allows any colours per character, so it would only move the
remaining text screens to blocks, which can be done a screen at a time if
one gets new art.

* `nx_pack.py` completes each stage file with Konami's own stage load, so
  a stage load copies the three tables whole.  Stages 10-12 share stage
  9's file; Konami's loads differ from it only in character 44's colours,
  24 bytes put in after the copy.
* The other events' bytes (the title, the Big Core, the screen before each
  life, game over, the status line, the ending) are recorded by
  `spec/native_next.py`, which replays Konami's loaders in msxsim with the
  MSX2 patch's data in the ROM, and are stored raw in 8K pages 84-91,
  unused before: 28 KB in 13 pieces.
* One hook inside the left-out code is kept for the Next only (0:544F, the
  stage's colours and status line before each life: `gen.py`'s
  `NEXT_KEEP`).
* The stars are written into row 0 of F6 and F7 from the same phase as
  the 128K's, and the dissolve ANDs the store as Konami's does the video
  chip's tables.

It was checked in ZEsarUX, built from source for the purpose, against
1.0N, with new tools that dump the store, the sprite patterns, the name
table and both Layer 2 screens at each change of stage or state, and
compare two runs.  The characters on show were identical at every stage
start, every Big Core arrival and the ending's load.

Three faults were found after that:

* **Stars and the laser as solid blocks**, on a real Next.  `dz_on`, the
  flag for a dissolve under way, had moved into `native.asm` at 77BC.  The
  Next's renderer reads it while 4000-7FFF hold the store, so it read a
  colour byte there, took the dissolve as under way, and drew characters
  F6 and up (the stars and the laser) in Layer 2 colour entries that are
  only set during a dissolve.  `dz_on` is now above 8000, asserted.  The
  ZEsarUX runs had shown the fault in their data (every dump in play
  about 2,000 pixels different, the stars' cells) and it had been put down
  to timing without being looked at.  The comparison now also reports
  colour entries one run uses and the other does not, which flags this
  kind of fault at the first dump.
* **The ordinary shot's black box** over scenery, in 1.0N too.  Konami
  keeps a shot's row and column in bytes 3 and 5 of its slot, and
  `tu_shots` and `tu_find` (`nx_tur.asm`) took them the other way round.
  So they looked for the shot in the wrong cell, found another character
  there, and left the shot's black 8 by 8 as Konami draws it, which is
  invisible over empty space but not over scenery.  With the bytes
  swapped, the cell is Konami's own map address for every row and column
  (checked for all 256 by 192 positions against a model of Konami's
  routine).
* **`dz_on` after a dissolve.**  1.0 kept it up from the dissolve's first
  chunk to the next graphics load; the native build cleared it only at a
  stage load, so through the ending after the stage 8 brain, characters
  F6 and up took the dissolve's unfaded palette entries.  Every native
  load now clears it, and Layer 2 at the ending's load is identical to
  1.0N's.

The 128K build is unchanged in behaviour by this work, since the Next's
code is all under `ifdef NEXT`; the screen lockstep was run again over
both routes after the shared changes.

### Before the release

`fulltest.py` (in the linked clone, `local/tools/nexttest/`) was rewritten
to play the whole Next game in ZEsarUX with an invulnerable copy, the ship
put on every hidden target unless told otherwise, checking the code and
read-only pages at every stage, and dumping for `nx_ftcmp.py`, which
compares two runs at each stage start, boss and point of the ending.  On
the bonus route (to 30 seconds into the second loop) the native build and
1.0N had no problems, and the characters on show were identical at all 50
points compared, the bonus stages included.  The native build also went
through two whole loops of the plain route without a problem.  1.0N did
not.

**The crash.**  In that run, at the end of stage 5 in the second loop,
1.0N's stage number became 7Eh and a byte of `nx_low.asm`'s code (01B1,
the operand of a `call`) was overwritten, and the screen froze.  It looked
like a stray write into 0000-3FFF, which is ROM on a 128K and the Next's
code bank on the Next.  `hunt.py` (fulltest with a breakpoint on writes to
01B1) ran both builds through two loops again at 400% with no crash in
either, so it depended on timing.  The cause was found by reading the
code.  The Next code reads a Next register in two steps: it selects the
register (an `out` to 243Bh) and reads it (an `in` from 253Bh).  The
interrupt selects registers too, to read the memory pages and the raster
line, so an interrupt between the two steps makes the read return
whichever register the interrupt selected last.  `tu_bsend`, which sends
the Big Core's blocks, reads MMU2 that way and puts the value back as
MMU2 when it has sent a block.  After a bad read, 4000-5FFF shows another
8K page in place of Konami's bank 0 code, and the next call into it runs
garbage.  One place (`lo_apply` in `nx_l2.asm`) already held the
interrupt off round the pair, with a note saying why; five in `nx_tur.asm`
did not.  It was shown with two test builds that widened the gap in
`tu_bsend` to about 38,000 T-states: without `di`, the first Big Core
crashed twice out of two, 9-10 seconds into the fight (one stop caught
MMU2 as 35h instead of 0Ah, and 01B1 being written); with `di` and `ei`
round the pair, the first two Big Cores passed.  The interrupt is now held
off between selecting and reading at all five places, and a stress build
with all five gaps widened went through stages 1-8, the ending and into
the second loop with no problems.  1.0N has the same race.

**The one-frame flash.**  Now and then, in any stage, the whole scenery
jumped sideways for a frame on the Next (on hardware and in emulators),
never on the 128K.  Layer 2 is a circular buffer, and its X scroll is the
origin column times 8 less the fine offset.  The frame interrupt sets it
for the play area, and the line interrupt at line 176 sets 0 for the
status rows; the two are told apart by alternation.  A lost frame
interrupt leaves the play area at scroll 0 for the next frame.  On the
Next an interrupt that comes while interrupts are off is lost, and in
play the longest stretch with them off was Konami's sound request
(`pide_sonido`, 0:4A02-0:4A11, on every shot and explosion), the one `di`
the port had kept, since it guards the sound queue.  Two test builds told
the interrupts apart by the raster line instead of by turns.  The first
window missed one emulator's line interrupt; the second ran, but the
flash stayed, because it only put the alternation back in step after a
loss, and the loss itself was the fault.  Moving the split to the copper
had been tried for 1.0 and withdrawn (above), and the copper is not used.
The fix leaves the interrupts as they were: `gen.py`'s `NEXT_PATCH` puts
`call snd_hold` and `call snd_free` in place of that `di` and `ei`, which
set and clear a flag (`snd_busy`), and while it is set the interrupt
leaves Konami's sound driver, which reads the queue, for that frame and
still sets the scroll.  The 128K's snapshot and tape are byte for byte
as before.  The fixed build was played in JNEXT to near the end of stage
4 without a flash, where the build before had shown two in stage 1.  1.0N
has the same flash.

**The walkers' gaps.**  The gaps inside the walkers' outline were
see-through, and showed the scenery behind.  They are now opaque black
(sprite colour 11, black in the walkers' two palettes).

**1.1.**  Both builds take the version 1.1 (V1.1A, V1.1N).

## 1.1.1: the Next's sound effects

All the changes are the Next's; the 128K's snapshot and tape are 1.1's
apart from the version on the title.

**Sound effects on a second AY.**  On the Next (and on the MSX) some
effects were lost while the music played, in stage 1 most of all.
Konami's request routine (`encola_sonido`, 0:4A22) gives a sound
channels by its number: below 16h, an effect, channel C only; 16h-25h,
two channels (A and B); 26h and over, all three.  A sound is played only
if its number is not below the one already on its channel.  Konami's
table at 1:7056 gives each stage's music by distance: the start tune
(2Ch) to distance 64h, then the stage's theme, then the boss tune (35h).
From stage 2 on the themes are two-channel (16h-24h), and channel C is
left to the effects; stage 1's theme (2Fh), the start tune and the boss
tune take all three, and an effect then has to outrank the tune to be
heard, which none does.  The Next has three AYs.  The effects now go into
three channel records of the port's own, played on the second AY by
Konami's own channel routines after its driver (9.3 of the technical
description).  The first trial played them on one record, as Konami's
channel C; in stage 1's volcanoes one was not enough, and effects were
still lost, so there are three, an effect going to a record already
playing it, else a free one, else the one with the lowest number.  The
third AY was considered for the two-channel themes, but moving them frees
nothing: the effects already have the second AY.  The three-channel
sounds that cut the music (the ship lost, the end of stage 8, the screen
going dark after a boss, a core destroyed) cut it on the MSX too, and
were left as they are.

**Sprites clipped to the play area.**  Sprites could be drawn over the
status rows (the Big Core at the bottom of the screen, for one).  The
sprite clip window is now lines 0-175.

**The Big Core's flick.**  A flick of the status rows, shifted sideways
for a frame, was seen in the Big Core fight (caught in a recording from
Xpeccy+), and 1.1 has it too.  1.1's
fix for the crash held interrupts off round each read of a Next register
from the main program, and the Big Core's pattern sends make those reads
often; a line interrupt lost there leaves the status rows with the play
area's scroll for a frame.  A trial read each register twice until two
reads agreed; it was replaced by the way the 128K's paging is kept: the
main program notes the register in `nx_sel` before selecting it, and the
interrupt selects it again before returning, so the read can run with
interrupts on.  The Next's code in play now has no `di` at all (the one
left is on the title screen).  It was played to the Big Core twice
without the flick.

**1.1.1.**  Both builds take the version 1.1.1 (V1.1.1A, V1.1.1N), seven
characters, as many as the title's space holds.

## After 1.1.1: the 128K's speed, measured again (10 November 2026)

Measurements of 1.1.1 against the MSX, and experiments made from them; none
changed the build. The method and every table are in the project's notes
(`claude/feel-1.1.1.md`); the scripts are in `local/tools/measure/feel/`.

**How it feels, per frame.**  The three machines played the same scripted
first loop (invulnerable, Konami's all-weapons cheat, fire on
keys_default's rhythm, a press up or down every 97 frames), and each 50 Hz
frame's picture was traced to the game tick it shows: the MSX in the
simulator (the last write to the sprite table before the beam reaches the
middle of the play area), the 128K in the Spectrum simulator (the tick each
screen was drawn for), the Next in ZEsarUX (stepped through `nx_frame` and
`lo_render`). The MSX ran 26.5 ticks a second over the loop, but 25 in its
median second in every stage, a new picture every second frame almost
without exception, and sprints of up to 50 only in quiet stretches. The
128K ran 24.5 ticks a second (92%), but drew only 15 pictures a second, at
gaps of 1 to 7 frames, most of them two ticks apart, and its input lag was
twice the MSX's (5.7 frames against 2.8). The Next held 29-30 throughout,
one tick a picture, with lag of 3.8 frames. The difference felt between the
MSX and the 128K is in the rhythm and the lag more than in the speed.

**Drawing every tick** (`NEM_EXTRA=0`) gave the 128K 20 pictures a second,
each one tick, but 75% of the MSX's speed, dipping to 12-14 ticks a second
in busy stretches; it felt much slower in play. **A pacing target of 25
ticks a second** (`NEM_ADAPT=16,8`) skipped about an eighth fewer ticks for
3% less speed: in the seconds below 24 ticks the adaptive rule is already
at one in two either way.

**Where the time goes.**  Profiled over the loop (the PC sampled every
300 T-states, by category): in the busiest quarter of seconds a tick took
about 185,500 T-states, against 141,816 for 25 a second. Konami's code
(logic and sound) was about 74,000, enough for about 48 ticks a second on
its own; the port's drawing, tracking and paging the rest. A drawn picture
cost about 136,000 there, mostly sprites (about 68,000) and cells (about
54,000). Of the 79 cells redrawn a picture, 29 were there only because a
sprite had covered them; the sprites' boxes cover 31 cells a picture, their
pixels 17.

**Compiled sprites.**  With every sprite pattern known when the game is
built (since 1.1), each pattern can have drawing code of its own, one
routine per pixel offset, with no loop and no blank bytes. In the simulator,
with the code held in memory the 128K does not have, compiling every
pattern made sprite drawing about 30% cheaper (35% in busy stretches), for
4% more speed and 10% more pictures, at a cost of 124 KB of code over the
loop (17-60 KB per stage). Five patterns are the same in every stage and
take 58% of the draws in this play (the options' two frames, the ship, the
round bullet, the missile), but compiling only those changed the slowest
seconds not at all. A real build (`NEM_CSPR=1`, title V1.1.1C) compiled the
ship's level frame and the round bullet into fixed memory: 1,664 of the
2,048 bytes free there. The compiled draws checked in the simulator (3,937,
all 16 routines) matched what `draw_sprite16` draws; sprites about 4% cheaper a picture, speed and
pictures up by under 1%, the slowest seconds unchanged. Not kept: fixed
memory is worth more than that. The change is in
`local/tools/measure/feel/` (`cspr_real.diff`, `cspr_gen.py`). If it is
ever taken up, the ship frame to compile should be chosen from real play:
the scripted play keeps the ship mostly level, and a player climbing and
diving shows the other two frames more.

## 1.1.2: sprite boxes trimmed to their pixels

The one change from the measurements above that went into the build.  A
sprite used to colour, and record for the next erase, its whole box: 2 or 3
cells across by 2 or 3 down, wherever its pixels were.  A bullet four pixels
square coloured up to six cells.  Over the first loop with every weapon the
boxes came to 7.7 cells a sprite and the cells the pixels reach to 4.7.

`sp_ext` (268 bytes) holds each sprite pattern's first and last rows with
pixels and the OR of its left and right column bytes: Konami's 64 patterns,
worked out again (`sp_calc`) at the first drawing after each graphics load,
which sets `spx_stale` in `nl_done`, and the ship's three frames.  At the
colouring, `sp_trim` turns them into the rows and columns the pixels reach
at the sprite's position and cuts the box down to those.  Patterns with no
pixels at all are neither coloured nor recorded.  A clipped sprite at the
edge (`edge_pat`) keeps its box.

In play the difference is the colour: cells near a small sprite keep their
own colours instead of taking its ink.  Each drawn picture costs about
5,000 T-states less (cell redraws 12-14% fewer, sprite colouring a little
less), but over the loop the speed was within the runs' noise of 1.1.1's.
Fixed memory: `platform_end` A700, 1.5 KB free below AD00.

A first build (title V1.1.1T, sent for a look) left pixels behind where a
sprite crosses the left or right edge: `spr_edge` enters `draw_sprite16` at
`.cols`, after the note of the pattern, so the trim used the previous
sprite's.  The note is now at `.cols`.  The checker written for the
change watched only `draw_sprite16`'s entry and missed it; the screen
lockstep found it in stage 1.

Checks: the screen lockstep against a 1.1.1 test build, pixels compared on
every tick (attributes left out, as they now differ by design, and the
title's version text): the route with every target (40,000 ticks), deaths
(50,000) and game overs (20,000), all identical.  `verify.sh` and the tape
traps pass.  The Next's .nex differs from 1.1.1N in the version's one
digit.

## 1.1.3: input lag on the 128K, the Next's drawing and 60 Hz

**Where the 128K's lag goes.**  Timed press by press (first loop, every
weapon, 779 presses, frames from the press): 1.40 to the tick that reads
it, 1.98 to the end of that tick and the pacing decision, nothing waiting
for the previous screen to be shown, 1.44 drawing, 0.98 to the screen
shown down to the ship's line: 5.80 in all.  The two frames before drawing
starts are the rest of the tick and, when the pacer leaves that tick
undrawn, the next whole tick (0.55 ticks on average).  Waiting for the
previous screen before the tick instead of after made the game 11% slower
and the lag no less: the wait was not where the lag was.

**Drawing the tick after a change of direction** (`INPUT_DRAW`, the 128K's
default; `NEM_INPUTDRAW=0` for 1.1.2's pacing): `pace_adapt` compares the
directions (`kb_cache+9` bits 0-3, the keys and a Kempston stick, not fire)
with the last tick's and never leaves a tick where they changed undrawn;
the debt it leaves makes the pacer skip a later one.  15 bytes in page C.
With presses every 97 frames the median lag went from 5.49 frames to 4.51
and the 90th percentile from 8.50 to 7.49, for 0.8% of speed (within the
runs' noise); with presses every 17 frames (about four changes of
direction a second), 5.50 to 4.50 and 8.50 to 6.51, for 2.7%.  The draw at
a joystick change tried before 0.110 predates the adaptive pacer.

**Why the Next left ticks undrawn.**  The Next has the time to draw every
tick, yet over 1.1.1N's loop it left about 3% undrawn, in runs of one every
8 ticks or so; at each, two ticks ran inside one frame.  Probes in ZEsarUX
(breakpoints with its t-state count) showed a screen taking 1.30-1.34
frames to draw in stage 1, so the 1-frame slots of the 2, 2, 1 rhythm were
missed, the game ran at about 1.76 frames a tick against the pacer's 1.75,
and the pacer's debt drifted over its slack.  The drawing: stars and setup
0.06 of a frame, cells 0.40 (65 a screen), turrets and shots 0.01, and the
sprites 0.83: Konami's 64 patterns compared with the copy last sent 0.19,
the character enemies' 4-bit patterns made 0.46, Konami's 32 sprite
entries 0.17.

Two of those were work done again for nothing.  Konami's patterns change
only with a graphics load, so all 64 are compared only after one
(`spr_new`), and one in turn on other screens as a safety net.  The
character enemies' patterns depend only on their four blocks of the pool:
each slot keeps the blocks it was made from (`nx_ckey`, fixed memory), and
a store of the last 32 patterns made, in bank 12's first 8K (unused until
now), is searched before making one.  Stage 1's opening has only 9
different patterns.  A first version kept only the slots: 0.84 of a frame
a screen, still over a frame for a quarter of them.  With the store: 0.71
on average, over a frame for 0.1% of screens, and in stage 1's first 30
seconds 4 ticks undrawn of 874 where 1.1.2 left 143.  Bank 8's code below
2000 had 51 bytes left; the hooks in it take 11, the rest is in fixed
memory (`lo_ci` moved there too).

Checked in ZEsarUX (`cachecheck.py`): at each hit the slot's pattern and
palette were read, the hit turned into a miss so the pattern was made
again as before, and the two compared.  The first store build had two
bugs, a register overwritten in the copy and a key offset that wrapped
for entries past 25; the check found them at once.

**GAME OVER's colours.**  On the Next the game-over text took the stage's
palette (dark olive in stage 8): the title and the ending put the TMS9918's
text is drawn from the copies in Layer 2's entries 0-15, which hold the
stage's colours.  `nl_gameover` now puts stage 1's 16 colours there
(`nx_gopal`, the status line's set), so GAME OVER looks the same after
every stage; nothing else changes, and a continue's stage load puts the
stage's colours back.  (A first try called `lo_marcador`, which also turns
the stage's graphics off, status line and all: Konami's original look,
which is for the title and the ending only.)

**60 Hz.**  A Next set to 60 Hz (NEXTREG 05h bit 2; NMI + 3 on the Next's
keyboard) has frames of 262-264 lines, 60 a second, and the game ran 20%
fast, its music too.  `nx_hz` reads the setting each frame: screens are 2
frames apart at 60 Hz (30 ticks a second, as at 50), the pacer's rhythm
is the same in 60 Hz frames, and Konami's sound driver is left out one
frame in six.  Played in JNext.  ZEsarUX does not change its frame timing
at 60 Hz.

## How releases are checked

Since 0.98, each release has been checked the same way before it went out:
the quick regression suite (`verify.sh`, including a short lockstep run);
the four checkers over 600 seconds of all-stage play with every target
touched (which reaches stages 1-3 and bonus stages 9-10); and the tape,
both by a simulated load and the way a DivMMC loads it.  Changes that reach
further get more: the lockstep through the whole loop, the checkers over
the whole route (0.101's overnight run), or the checkers concentrated on the
part of the game that changed (0.107's dissolves).  The released files are
compared byte for byte with the builds that were checked, and the source
package is rebuilt from scratch to make sure it reproduces them.

From 1.1 there is no run-time converter, so its checks (`check_tiles`,
`test_convert`) are gone and three checkers remain.  The pictures are
checked instead by the screen lockstep (`screen_lockstep.py`), which
compares every tick's screens with the previous release's, byte for
byte, over whole routes: every hidden target, a death in each stage, and
game over.  The lockstep compares only the name table of video memory,
the native build having no copies of the MSX's tables.

The Next build has no simulator.  `verify.sh` only assembles it, and
`release.sh` plays the `.nex` for a minute in ZEsarUX (`nx_smoke.py`).
The tools in the linked clone's `local/tools/nexttest/` play it through
in ZEsarUX: `fulltest.py` the whole game, on the bonus route or the plain
one, checking the code and read-only pages at every stage; `nx_ftcmp.py`
compares two runs at each stage start, boss and point of the ending;
`hunt.py` and `replay.py` add a watch for a stray write and snapshots to
replay from.  They compare memory, not the picture, so a wrong scroll
split, palette or hardware sprite passes them, and the Next build is also
played (1.1's flash was found that way).

## Where it stands (1.1.3)

* The 128K build has no MSX graphics.  Every graphics load is a load of
  tiles and sprite patterns converted when the game is built, and
  Konami's loaders are left out of the build.
* Its Konami RAM matches the MSX original's on every tick, and its screens
  match 1.0's byte for byte, over the route with every hidden target
  (all twelve stages, the ending and into the second loop), over a death in
  each of stages 1-8 (apart from the intended stage 3 Moai fix) and over
  five game overs.
* 1.1's tape (70,445 bytes) passes the simulated load.
* Since 1.1.2 a sprite colours and erases only the cells its pixels
  reach; its screens match 1.1.1's pixel for pixel over those three routes.
* Since 1.1.3 a tick where the directions change is always drawn: a frame
  off the typical input lag (median 4.5 frames, the MSX's 2.8).
* Fixed memory has 1.5 KB free below AD00 (`platform_end` A700), and the
  switched banks about 1.4 KB, in pieces of at most 384 bytes.
* Speed: over the first two stages in light play, 24.57 ticks and 14.7
  screens a second (1.0: 24.16 and 13.7).  Over stages 1-6 with every
  weapon, never fewer than 6 screens in any second, where 1.0 had seconds
  with none.
* The Next build is on the same code, with its store of character rows
  filled from data made when the game is built.  In ZEsarUX its builds
  have played the bonus route and two whole loops of the plain route with
  their code and read-only pages intact, the characters on show identical
  to 1.0N's at every point compared.  1.0N's crash and one-frame flash
  are fixed in it.  From 1.1.1 its sound effects play on a second AY, its
  sprites are not drawn over the status rows, and no code in play
  disables interrupts.  From 1.1.3 it draws a screen in about 0.7 of a
  frame (1.3 before, in stage 1's opening in ZEsarUX), so it shows nearly
  every tick, and it keeps its
  speed and its music's tempo at 60 Hz.
