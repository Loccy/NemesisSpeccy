"""Colour conversion: MSX TMS9918 tiles -> ZX Spectrum ink/paper tiles.

Each 8x8 tile is fitted independently using a *single* ZX attribute byte.
Within that constraint the 64 pixels are approximated by the closest of the
pair of permissible colours, minimizing summed squared RGB error.
"""
from collections import Counter
from functools import lru_cache
from PIL import Image
from extract import TMS

ZX_BASE = [(0,0,0),(0,0,205),(205,0,0),(205,0,205),(0,205,0),
           (0,205,205),(205,205,0),(205,205,205)]
ZX_BRIGHT = [(0,0,0),(0,0,255),(255,0,0),(255,0,255),(0,255,0),
             (0,255,255),(255,255,0),(255,255,255)]
PALETTES = (ZX_BASE, ZX_BRIGHT)

def dist2(a,b):
    return sum((x-y)**2 for x,y in zip(a,b))

@lru_cache(maxsize=None)
def colour_fit(tuple_of_64):
    counts=Counter(tuple_of_64)
    best=None
    for bright,palette in enumerate(PALETTES):
        for ink in range(8):
            for paper in range(8):
                err=sum(n*min(dist2(TMS[col],palette[ink]),
                              dist2(TMS[col],palette[paper]))
                        for col,n in counts.items())
                attr=ink | (paper<<3) | (bright<<6)
                key=(err, (ink==paper), (ink != 7 and paper != 0),attr)
                if best is None or key < best[0]:
                    best=(key,ink,paper,bright)
    _, ink,paper,bright=best
    palette=PALETTES[bright]
    chosen=[ink if dist2(TMS[c],palette[ink]) < dist2(TMS[c],palette[paper])
            else paper for c in tuple_of_64]
    bits=[]
    for r in range(8):
        val=0
        for i,x in enumerate(chosen[8*r:8*r+8]):
            if x==ink and ink!=paper: val |= 128>>i
        bits.append(val)
    return bytes(bits)+(bytes([ink | (paper<<3)|(bright<<6)]))

def tile_table(vram):
    """Encode completed ROM-derived VRAM, without hand-painted tile overrides."""
    result=bytearray()
    for third in range(3):
        for ch in range(256):
            tile=[]
            for line in range(8):
                off=third*0x800+ch*8+line
                pat=vram[0x2000+off]
                col=vram[off]
                tile.extend((col>>4) if pat&(128>>i) else (col&15)
                            for i in range(8))
            result.extend(colour_fit(tuple(tile)))
    assert len(result)==3*256*9
    return bytes(result)

def make_screen(map_rows, tiles, xstart):
    """Return a full ZX .SCR image (6912 bytes) at map-column xstart."""
    scr=bytearray(6912)
    for row in range(22):
        for col in range(32):
            ch=map_rows[row][(xstart+col)%len(map_rows[0])]
            tileoffset=(row//8)*2304+ch*9
            for line in range(8):
                y=row*8+line
                scr[((y&0xC0)<<5)|((y&7)<<8)|((y&0x38)<<2)|col] = tiles[tileoffset+line]
            scr[6144+row*32+col]=tiles[tileoffset+8]
    return bytes(scr)

def screen_to_png(scr, out, scale=3):
    img=Image.new('RGB',(256,192),(0,0,0))
    px=img.load()
    for y in range(192):
        for x in range(256):
            pix=scr[((y&0xC0)<<5)|((y&7)<<8)|((y&0x38)<<2)|(x//8)]
            attr=scr[6144+(y//8)*32+(x//8)]
            colour = attr&7 if pix & (0x80>>(x&7)) else (attr>>3)&7
            px[x,y]=PALETTES[(attr>>6)&1][colour]
    img.resize((256*scale,192*scale),Image.Resampling.NEAREST).save(out)
