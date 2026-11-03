# Legal notice and attribution

## Who owns what

**This game is not ours.** The MSX version of *Nemesis* (aka *Gradius*),
catalogue number RC-742, was written and published by **Konami** in 1986.
Its code, graphics, music and sound effects, and the names Nemesis and
Gradius, belong to Konami and the other holders of rights in it. This is an
unofficial fan project, with no connection to Konami and no endorsement by
it. This project was made out of affection for the original game, and to
show what a Spectrum version could have achieved. It is a non-commercial
project and no financial benefit accrues from it. Konami Digital
Entertainment B.V. states that it does not generally object to fans using
its copyrighted material for non-commercial purposes, while reserving the
right to have it taken down ([Konami
support](https://eu-support.konami.com/hc/en-gb/articles/9648771731479-Copyrights-Career-Opportunities-Goodies)).

**What is ours** is the work done to make the game run on the ZX Spectrum
128K and the ZX Spectrum Next: the platform layer that stands in for the MSX
hardware (the `.asm` files in `spec/` other than the generated
`konami_spec*.asm`, among them the Next's `nx_low.asm` and `nx_l2.asm`), the
relocating generator and its tables (`reloc/`), the MSX simulator and test tools
(`msxsim/`, the `.py` files), the tape loader, and the documentation.
These are published under the MIT licence in [LICENSE](LICENSE). The
licence covers nothing of Konami's: not the game's code, graphics, music or
sound, whether in the ROM, in the files the build generates, or in the
tapes, snapshots and Next file; nor the MSX2 patch's graphics.

## What is in this project

* **The source** does not contain the cartridge image. To build the port
  you supply your own copy of the ROM (`nem.rom`); the generator reads
  Konami's code and data from it and writes them back out, relocated, for
  the Spectrum. The generated files (`konami_spec.asm`, the `.bin` data
  banks) are therefore Konami's code and data in a new arrangement, not ours.
* **The tape, snapshots and Next file** (`nemesis.tap`, `nemesis.sna`,
  `nemesis_test.sna`, the `.nex`) are built that way, so they contain Konami's game: its
  code and data, relocated, alongside our platform layer.
* **The Spectrum Next version's graphics** are mostly not ours either.
  They began as those of the MSX2 patch "Nemesis - Gradius ENHANCED" V1.01
  (programmed by Victor Martinez, graphics and colours by Toni Galvez,
  based on SHALOM's patched version), which belong to their authors, and
  which are themselves Konami's graphics reworked. They were read from the
  patched ROM once and are kept in this repository (`spec/nxgfx/`), with
  our changes since, so the Next version builds from the ROM alone; the
  patch itself is not included. They are here on the same basis as
  Konami's material: a non-commercial fan project. The released
  `.nex` file contains Konami's game and these graphics alongside our
  platform layer. The red, orange and yellow options and explosion are our
  own change to them.
* **The Next version's redrawn enemies** (`spec/nx_art.py`) are drawn
  after the sprites of Konami's arcade *Gradius* (1985), in their colours,
  and fitted to the MSX's sizes and frames, so they are Konami's artwork
  too, adapted; they are in the repository on the basis of Konami's
  statement above.
* **The loading screen** (`tape/loading.scr`) is converted from the
  illustration in Konami's MSX attract sequence (`tape/illustration_msx.png`,
  rendered from the running MSX game), so it is Konami's artwork too.
* **Departures from the original** (no Konami logo or attract cycle, the
  colours chosen for the Spectrum, the speed) are described in `README.md` and `docs/TECHNICAL.md`.
  Nothing has been added to the game but the controls and the credit line
  on the title screen.

## What it rests on

* **antxiko's annotated disassembly** of the cartridge
  (https://github.com/antxiko/Nemesis-disassembly), which `reloc/gen.py`
  parses and which explained much of how the game works: the bonus stages,
  the hidden targets, the checkpoints, the cartridge's search for TwinBee.
  Its tools, comments and documentation are published by its authors under
  the MIT licence, which like this project's does not cover the game itself.
* **ZX0** by Einar Saukas (https://github.com/einar-saukas/ZX0), which packs
  the tape's blocks; its unpacker is included in `tape/` under its own
  licence (`tape/ZX0_LICENSE`).
* **SkoolKit** by Richard Dymond, whose 128K emulator runs the checks.
