"""Layer 2 dumps (fulltest.py's dNNN_TAG.l2, nx_poll.py's eNNN.l2) as PNGs
side by side, the colour entries as false colours (0 black; 0-15 the
TMS9918's; others by hue), for a first look: the palette itself is not
dumped.  usage: l2png.py OUT.png FILE.l2 [FILE.l2 ...] (screen 0 of each)"""
import sys, colorsys
from PIL import Image
TMS = [(0,0,0),(0,0,0),(33,200,66),(94,220,120),(84,85,237),(125,118,252),(212,82,77),(66,235,245),
       (252,85,84),(255,121,120),(212,193,84),(230,206,128),(33,176,59),(201,91,186),(204,204,204),(255,255,255)]
def col(v):
    if v < 16: return TMS[v]
    r, g, b = colorsys.hsv_to_rgb((v * 47 % 256) / 256, 0.6, 0.95); return (int(r * 255), int(g * 255), int(b * 255))
fs = sys.argv[2:]
S = Image.new('RGB', (len(fs) * 266, 192), (60, 60, 60))
for i, f in enumerate(fs):
    d = open(f, 'rb').read()
    im = Image.new('RGB', (256, 192)); px = im.load()
    for y in range(192):
        for x in range(256): px[x, y] = col(d[y * 256 + x])
    S.paste(im, (i * 266, 0))
S.resize((S.size[0] * 2, 384), Image.NEAREST).save(sys.argv[1])
