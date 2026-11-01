# Nemesis for the ZX Spectrum 128K

Nemesis, aka Gradius, was a seminal shmup. I first played it on a friend's
C64, but we Spectrum owners were really shortchanged with the conversion we
got. It didn't help that the mags of the era ran reviews featuring "screenshots"
that were obviously mock-ups created by graphic artists. The game we got was
a pale shadow of the game we were promised.

In contrast, the MSX was home turf for Konami, and like the vast majority of
their titles they handled the conversion themselves. It was an excellent port
that ran at a decent clip, maintained the playability of the original, and made
sensible compromises to fit the game into the hardware platform.

Architecturally, the MSX wasn't THAT different to the Spectrum. Hardware sprites,
yes, and slightly better colour attributes, but the same Z80 CPU, the same sound
chip (at least compared to the Spectrum 128), same screen resolution. It would
have made sense to use the MSX version of Nemesis as a basis for the Spectrum
port.

So, this project is an attempt to tap into that alternate universe where that
happened.

What we have here is a port of Konami's MSX cartridge Nemesis (RC-742, 1986) 
for running on a standard 128K Spectrum using Konami's own game code (tested 
on a real 128K and +3, loading from tape, and in emulation on the 128K, +2A
and +3). It is mostly the same code that sits
on top of a platform layer which stands in for the MSX hardware.

The Z80 code of the cartridge is relocated to the Spectrum's memory by a 
generator (`reloc/gen.py`), and a platform layer (`spec/`) stands in for 
the hardware the code talks to: the memory mapper, the BIOS routines it calls,
the video chip (TMS9918), the sound chip (AY-3-8910, the same family as the
128K's) and the keyboard and joystick.

The game logic is Konami's, unchanged except where it meets the hardware.
A test build matches the MSX original byte for byte in Konami's RAM, tick by
tick (see [the technical description](docs/TECHNICAL.md), section 4).

Departures from the MSX original are all deliberate:

* The front end goes straight to the title screen: no Konami logo, no
  attract cycle (demo play and the illustration).  The title carries the
  controls and a credit line. This is to save on space - it was a tight fit!
* It runs slower than the PAL MSX overall, and comes in two editions that
  differ only in how often the screen is drawn (technical description,
  section 6.8).  Over the
  first two stages, *fast* (one tick in two drawn) takes 94% of the MSX's
  time, at 12 screens a second and an input lag of about 7 frames against
  the MSX's 3; *smooth* (four in five) 88%, at 18 screens a second and
  about 6 frames.
* Colours are chosen for the Spectrum's attribute cells: tiles are fitted to
  two colours per cell, sprites take one ink per cell, and a few objects get
  colours of their own (technical description, sections 6.6 and 6.7). Where the automatic fit made a
  mess of the scenery (the bricks of stage 2 and the bonus stages, the Moai
  of stage 3, the brains of stages 6 and 8, the band and formations of stage
  7 and the pipework of stage 8), the colours were picked by hand instead,
  stage by stage, against the MSX.
* The ship keeps the MSX's shape, but on the MSX it is two sprites one over
  the other: white, with a red canopy, and a light blue belly when it
  climbs. A Spectrum cell has one colour, so the canopy is drawn as a black
  line inside the white outline, and the belly as a stippled pattern.

Everything Konami made is still Konami's: see [LEGAL-NOTICE.md](LEGAL-NOTICE.md)
for who owns what.

FULL DISCLOSURE: this is an AI project. The Claude in the credit is the Claude
from Anthropic. I make no claim that I hand-wrote the code. 

I guided the AI, brainstormed solutions to problems with it, proposed strategies
for solving problems, gave direction on how best to accommodate modifications
needed for the Spectrum. If you object to AI-authored code/projects then that is
your prerogative, but perhaps then this project is not for you.

![The title screen](docs/images/01_title.png)
![Stage 1: the volcanoes](docs/images/04_stage1_volcanoes.png)
![Stage 3: the Moai](docs/images/09_stage3_moai.png)
![Stage 8: the brain](docs/images/18_stage8_brain.png)

## Playing it

### What you need

* A ZX Spectrum 128K, +2, +2A, +2B or +3. It needs the 128K's extra memory,
  so it won't run on a 48K.
* Tested on a real 128K and a real +3 (from tape, through a Retroleum
  SmartCard and through a DivMMC Future), and in emulators as a 128K, +2A
  and +3.

### Loading

* **Tape:** `LOAD ""` (on a +2A, +2B or +3, choose Loader from the menu).
  The loading screen builds up, then the game starts by itself.
* **Emulators:** the `.tap` files load like a real tape; the `.sna` files are
  128K snapshots that start straight away.

### Fast or smooth

There are two editions, the same game drawn two ways. Try both and keep the
one you prefer.

* **Fast** (files ending `_fast`): close to the MSX's speed, about 6%
  slower overall. The screen is redrawn about 12 times a second, so
  movement is jerkier, and the controls respond a little later.
* **Smooth** (files ending `_smooth`): the screen is redrawn about 18 times
  a second and the controls respond sooner, but the game runs about 12%
  slower than the MSX.

The title screen shows which one you have, in the top right corner after
the version number: V0.107F for fast, V0.107S for smooth.

### Controls

| Action | Keys | Joystick |
|---|---|---|
| Move | Q A O P, or 9 8 6 7 | Kempston, or Sinclair (keys 6-0) |
| Fire | SPACE or 0 | Fire |
| Power up | M, or hold fire | Second fire button, or hold fire |
| Pause | H | |
| Continue after game over | C, while the game-over tune is playing | |

On the title screen, choose 1 or 2 players with the movement keys and start
with fire. A Kempston joystick is picked up when the machine is switched on;
with none plugged in, the keys work as normal.

Holding fire down for about half a second takes the highlighted power-up,
once each time you hold it, so a one-button joystick can play without the
keyboard. On an interface with a second fire button, that button takes the
power-up too, like the MSX's second button. This works on the SmartCard and
the DivMMC Future; on the SmartCard with a Mega Drive pad, B fires and C
takes the power-up.

### Playing

Destroy the red enemies and fly into the capsules they leave. Each capsule
moves the highlight along the power-up bar at the bottom (SPEED UP, MISSILE,
DOUBLE, LASER, OPTION and the shield); press M, or hold fire, to take
whatever is highlighted.

Konami hid a few things in this one. Some stages have a secret near the end,
and finding it takes you somewhere you would not otherwise go. That is all
we are saying.

## Building from source

The source does not include the cartridge. You need:

- Your own copy of the Nemesis ROM (Konami RC-742, 131,072 bytes) as `nem.rom`
  in the root. Its SHA-256 should be
  `3210f8a0f2309dd4b9a89fc2b24d0f178ce4393a0a1f2854fbce545c361261bc`, and the
  build stops if it is not.
- antxiko's annotated disassembly in `ref/`, at the version the port is
  built against (the build stops if it is a different one):
  ```
  git clone https://github.com/antxiko/Nemesis-disassembly ref/Nemesis-disassembly
  git -C ref/Nemesis-disassembly checkout 3e486bc2f39c65eb97a944cda246f85fd30218ec
  ```
- Python 3 with SkoolKit and Pillow (`pip install skoolkit pillow`).
- sjasmplus (https://github.com/z00m128/sjasmplus) on the PATH.
- Einar Saukas's ZX0 compressor (https://github.com/einar-saukas/ZX0) for the
  tape, on the PATH as `zx0` or named by the `ZX0` environment variable.

It was last built with Python 3.13, SkoolKit 10.1, Pillow 12.3 and sjasmplus
1.21.0. Then, in `spec/`:

```
python3 build.py              # nemesis.sna, the fast edition
python3 make_tap.py           # nemesis.tap from it
sh release.sh 0.107           # both editions, tape and snapshot, in release/
sh verify.sh                  # the regression checks
```

Built this way, the files in `release/` are identical to the published ones.
The first run of `verify.sh` also captures Konami's graphics from the ROM
for the colour-converter test (`spec/vram_states.pkl`, kept out of the
repository). Section 3 of the technical description has the details and the
build options.

## Documentation

* [Technical description](docs/TECHNICAL.md): how the port works, how it is
  built and how it is checked against the MSX original.
* [Development notes](docs/DEVELOPMENT_NOTES.md): the history of the
  project, what was tried, kept and dropped, and the bugs found on the way.
* [Legal notice](LEGAL-NOTICE.md): who owns what.
* [Licence](LICENSE): the MIT licence, which covers the port's own work
  and none of Konami's.

## Credits

* The game: Konami, 1986.
* Spectrum 128K port: Paul and Claude (Anthropic's AI), built on the
  annotated disassembly of the cartridge by antxiko
  (https://github.com/antxiko/Nemesis-disassembly).
* Tape compression: ZX0 by Einar Saukas.

Nemesis and Gradius belong to Konami. This is an unofficial fan
project. See [LEGAL-NOTICE.md](LEGAL-NOTICE.md) for who owns what.
