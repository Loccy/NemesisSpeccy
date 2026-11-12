import sys, glob, os
from PIL import Image, ImageDraw
d, a, b, step, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
fs = {int(os.path.basename(f)[1:5]): f for f in glob.glob(d + '/p*.png')}
secs = [s for s in range(a, b + 1, step) if s in fs]
W, H, C = 256, 192, 6
R = (len(secs) + C - 1) // C
sh = Image.new('RGB', (W * C, (H + 14) * R), (40, 40, 40))
dr = ImageDraw.Draw(sh)
for i, s in enumerate(secs):
    im = Image.open(fs[s]).resize((W, H))
    x, y = (i % C) * W, (i // C) * (H + 14)
    sh.paste(im, (x, y + 14)); dr.text((x + 2, y + 1), os.path.basename(fs[s])[:-4], fill=(255, 255, 0))
sh.save(out); print(len(secs))
