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
128K: the platform layer that stands in for the MSX hardware (the `.asm`
files in `spec/` other than the generated `konami_spec*.asm`), the relocating
generator and its tables (`reloc/`), the MSX simulator and test tools
(`msxsim/`, the `.py` files), the tape loader, and the documentation.

## What is in this project

* **The source** does not contain the cartridge image. To build the port
  you supply your own copy of the ROM (`nem.rom`); the generator reads
  Konami's code and data from it and writes them back out, relocated, for
  the Spectrum. The generated files (`konami_spec.asm`, the `.bin` data
  banks) are therefore Konami's code and data in a new arrangement, not ours.
* **The tape and snapshots** (`nemesis.tap`, `nemesis.sna`,
  `nemesis_test.sna`) are built that way, so they contain Konami's game: its
  code and data, relocated, alongside our platform layer.
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
  the MIT licence; like this project, it does not cover the game itself.
* **ZX0** by Einar Saukas (https://github.com/einar-saukas/ZX0), which packs
  the tape's blocks; its unpacker is included in `tape/` under its own
  licence (`tape/ZX0_LICENSE`).
* **SkoolKit** by Richard Dymond, whose 128K emulator runs the checks.
