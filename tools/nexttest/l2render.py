"""Renders fadeprobe.py's Layer 2 dumps (l2_*.bin, 256 x 192 bytes) with the
palette logged with each (pal_*.txt, 256 9-bit values as hex) to PNGs, and a
contact sheet of them.  l2render.py DIR"""
import os, sys, glob
from PIL import Image, ImageDraw
D = sys.argv[1]
ims = []
for f in sorted(glob.glob(os.path.join(D, 'l2_*.bin'))):
    tag = os.path.basename(f)[3:-4]
    pal = [int(x, 16) for x in open(os.path.join(D, 'pal_%s.txt' % tag)).read().split()]
    rgb = [(((v >> 6) & 7) * 255 // 7, ((v >> 3) & 7) * 255 // 7, (v & 7) * 255 // 7) for v in pal]
    b = open(f, 'rb').read()
    im = Image.new('RGB', (256, 192))
    im.putdata([rgb[c] for c in b])
    im.save(os.path.join(D, 'r_%s.png' % tag)); ims.append((tag, im))
C = 5
R = (len(ims) + C - 1) // C
sheet = Image.new('RGB', (C * 260 + 4, R * 210 + 4), (40, 40, 40))
dr = ImageDraw.Draw(sheet)
for i, (tag, im) in enumerate(ims):
    x = 4 + (i % C) * 260; y = 4 + (i // C) * 210
    sheet.paste(im, (x, y + 14)); dr.text((x, y), tag, fill=(255, 255, 0))
sheet.save(os.path.join(D, 'sheet.png'))
print(len(ims), 'frames')
