# Stage 3's Moai and rocks for 1.2.1 (12 November 2026)

How `spec/stage3_tiles.txt` was made. Run once; the file is now the art, to be
edited directly.

1. `grab3.py`: plays 1.2 in the Spectrum simulator (NEM_ALL) to stage 3 and
   saves the screen, the character map and Konami's sprite list every 8
   distance steps through the Moai section (`grabs3.pkl`).
2. `nextlike.py` (with `recolour.py`, `grad.py`, `fill.py`, `render.py`):
   recolours a captured screen: heads yellow with yellow-and-black stippled
   shading, bright where the face is lit (the face's edge, and cells three
   quarters face with no black; a bright cell with no bright neighbour dim;
   characters 23 and E5, the lying heads' lone bright cell against the rocks,
   dim in every third); rocks green, solid at their edges, stippled inside.
3. `gentiles.py`: lists the head characters and the rock characters, and
   takes each one's tile from its appearances in the recoloured screens (the
   most common value of each byte), stored inverted when more than half set,
   as `tilemodel.invert`. Writes `v121/s3new.pkl` in the scratch folder,
   which was then written out as `spec/stage3_tiles.txt` (267 tiles).
   * A head character is a stage 3 Moai-section character whose 1.2 tile is
     only cyan, blue and black, and which is in one of Konami's head or pile
     drawings (pointers 1:6370, sizes 1:6283). Without the second test the
     laser's strip (FD) and the nuke capsule (77-7A), caught crossing a head
     in the captured screens, were taken for head pieces: the laser got a
     blank tile and vanished in the middle third.
   * A rock character's 1.2 tile is only magenta and black, and its number is
     not one of Konami's turret characters (frame table 2:9205, shape table
     5:91D1), whose barrels share the rocks' magenta. Turret numbers are not
     left out of the heads: in stage 3, D2-D9 are head pieces.
4. `piles.py`: the rubble pile a destroyed head leaves (Konami's drawing 12
   on the ground, 13 hanging from the ceiling, the same upside down). Copies
   the ground pile's tiles from the middle third to the top third, and flips
   them for the hanging pile in the top and middle thirds. 24 tiles, marked
   `pile`.
5. `fill_thirds.py`: a head or pile character that never turned up in a
   third in the captured screens kept 1.2's colours there. Copies its tile
   from a third where it was recoloured, when Konami's pixels and colours for
   it are the same in both. 24 tiles, giving 315 in all.

Steps 4 and 5 edit `spec/stage3_tiles.txt` in place.  Every script finds
the repository from its own place (or from `NEM_ROOT`).  Steps 1 to 3 kept
their captured screens and working files in folders `moai` and `v121`
beside the repository (`NEM_SCRATCH` names the folder that holds them), and
import each other from `moai`: copy them there to run them again.
