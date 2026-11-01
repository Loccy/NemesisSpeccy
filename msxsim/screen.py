"""Render the TMS9918 screen 2 (Graphics II) plus sprites from VRAM to PNG."""
from PIL import Image
PAL=[(0,0,0),(0,0,0),(33,200,66),(94,220,120),(84,85,237),(125,118,252),(212,82,77),(66,235,245),
     (252,85,84),(255,121,120),(212,193,84),(230,206,128),(33,176,59),(201,91,186),(204,204,204),(255,255,255)]
def render(vdp, path, scale=2):
    v=vdp.vram; r=vdp.reg
    name=(r[2]&0x0F)<<10; col=0x2000 if r[3]&0x80 else 0; pat=0x2000 if r[4]&4 else 0
    sat=(r[5]&0x7F)<<7; spg=(r[6]&7)<<11
    im=Image.new('RGB',(256,192)); px=im.load()
    for ty in range(24):
        third=(ty>>3)<<11
        for tx in range(32):
            ch=v[name+ty*32+tx]
            for y in range(8):
                p=v[pat+third+ch*8+y]; c=v[col+third+ch*8+y]
                fg=PAL[c>>4]; bg=PAL[c&15]
                for x in range(8): px[tx*8+x,ty*8+y]= fg if p&(0x80>>x) else bg
    big=r[1]&2
    for i in range(32):
        y=v[sat+i*4]
        if y==0xD0: break
        x=v[sat+i*4+1]; n=v[sat+i*4+2]; c=v[sat+i*4+3]
        if c&0x80: x-=32
        y=(y+1)&0xFF
        if y>191 and y<0xE0: continue
        if y>=0xE0: y-=256
        size=16 if big else 8
        if big: n&=0xFC
        colr=PAL[c&15]
        if (c&15)==0: continue
        for yy in range(size):
            for xx in range(size):
                if big: b=v[spg+n*8+(xx//8)*16+yy]
                else: b=v[spg+n*8+yy]
                if b&(0x80>>(xx%8)):
                    X=x+xx; Y=y+yy
                    if 0<=X<256 and 0<=Y<192: px[X,Y]=colr
    im.resize((256*scale,192*scale),0).save(path)
