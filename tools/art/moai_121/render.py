import pickle, sys
from PIL import Image
PAL = [(0,0,0),(0,0,0xD7),(0xD7,0,0),(0xD7,0,0xD7),(0,0xD7,0),(0,0xD7,0xD7),(0xD7,0xD7,0),(0xD7,0xD7,0xD7),
       (0,0,0),(0,0,0xFF),(0xFF,0,0),(0xFF,0,0xFF),(0,0xFF,0),(0,0xFF,0xFF),(0xFF,0xFF,0),(0xFF,0xFF,0xFF)]
def render(scr, scale=3):
    im = Image.new('RGB', (256, 192))
    px = im.load()
    for y in range(192):
        base = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
        for cx in range(32):
            b = scr[base + cx]; a = scr[6144 + (y // 8) * 32 + cx]
            br = 8 if a & 0x40 else 0
            ink = PAL[(a & 7) + br]; pap = PAL[((a >> 3) & 7) + br]
            for bit in range(8):
                px[cx * 8 + bit, y] = ink if b & (0x80 >> bit) else pap
    return im.resize((256 * scale, 192 * scale), Image.NEAREST)
if __name__ == '__main__':
    g = pickle.load(open('grabs.pkl', 'rb'))
    for i, s in enumerate(g):
        render(s['screen']).save('cur_%03X.png' % s['dist'])
