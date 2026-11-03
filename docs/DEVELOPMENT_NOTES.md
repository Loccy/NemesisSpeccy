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

## After 0.110: the Spectrum Next build

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
* **Stage 1's ground edge in brown.**  The patch draws the ground's lower
  edge (a dithered line of character 43) dark brown on magenta in stage 1
  but dark brown on the lighter brown in stage 4.  The browns looked
  better; stage 1 is coloured as stage 4 (now in `spec/nxgfx/stage1.bin`).
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
* **One tree.**  The Next's changes to shared files are under `ifdef NEXT`,
  its takeovers of Konami's instructions are in `gen.py` with the 128K's,
  and the 128K builds are byte for byte those of 0.110.  `verify.sh` builds
  the `.nex` too, and `release.sh` makes it and, with ZEsarUX, plays it for
  a minute.

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

## Where it stands (0.110)

* The test build matches the MSX original in Konami's RAM and video memory
  with all weapons through the whole first loop and well into the second,
  and through the whole route with every target touched; it has also been
  run with deaths in the bonus stages and with hold-to-select.
* The checkers have passed over the whole first loop and most of the second
  (0.101), and around both dissolves (0.107).
* The tape loads and runs on a real 128K and a real +3 (through a
  SmartCard, a DivMMC Future and a Maxduino), and in emulators as a 128K,
  +2A and +3.  The second fire button and hold-to-select work on real
  hardware.
* Konami's stack has 22 bytes of headroom at its deepest.
* About 1,540 bytes of memory are free, most of it in the switched banks
  (technical description, section 5).
* Speed against the simulated 50 Hz MSX (technical description, section
  6.8): 96% over the first two stages in light play, at about 16 screens a
  second and an input lag of about 6 frames (the MSX's: 3.15); 86% over
  the whole first loop with every weapon.
