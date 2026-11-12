"""Contact sheets of fulltest.py's screenshots: the screen area of each
(cropped from ZEsarUX's 704 x 608 with border), at full size, COLS x ROWS a
sheet, labelled with the file name.

  sheets.py RUNDIR OUTDIR [COLS ROWS] [GLOB]"""
import os, sys, glob
from PIL import Image, ImageDraw
D, O = sys.argv[1], sys.argv[2]
C = int(sys.argv[3]) if len(sys.argv) > 3 else 3
R = int(sys.argv[4]) if len(sys.argv) > 4 else 3
G = sys.argv[5] if len(sys.argv) > 5 else '*.bmp'
os.makedirs(O, exist_ok=True)
files = sorted(glob.glob(os.path.join(D, G)))
BOX = (96, 96, 608, 512)            # the 256 x 192 screen, doubled, with a little border
W, H = BOX[2] - BOX[0], BOX[3] - BOX[1]
SC = 0.5
w, h = int(W * SC), int(H * SC)
n = 0
for i in range(0, len(files), C * R):
    sheet = Image.new('RGB', (C * w + (C + 1) * 4, R * (h + 14) + 4), (40, 40, 40))
    dr = ImageDraw.Draw(sheet)
    for j, f in enumerate(files[i:i + C * R]):
        im = Image.open(f).convert('RGB').crop(BOX).resize((w, h), Image.NEAREST)
        x = 4 + (j % C) * (w + 4); y = 4 + (j // C) * (h + 14)
        sheet.paste(im, (x, y + 12)); dr.text((x, y), os.path.basename(f)[:-4], fill=(255, 255, 0))
    n += 1; sheet.save(os.path.join(O, 'sheet_%03d.png' % n))
print(n, 'sheets of', len(files))
