"""Produce ROM-only MSX/Spectrum comparison images for stage 1."""
from pathlib import Path
import sys
from PIL import Image,ImageDraw
from extract import Nemesis,TMS
from convert import tile_table,make_screen,screen_to_png
ROOT=Path(__file__).resolve().parents[1]

def msx_panel(n,v,stage,xstart):
    rows=n.stage_map(stage)
    img=Image.new('RGB',(256,176))
    px=img.load()
    for r in range(22):
        for c in range(32):
            ch=rows[r][(xstart+c)%len(rows[0])]
            pixels=n.msx_tile(v,ch,r//8)
            for dy in range(8):
                for dx in range(8):
                    px[c*8+dx,r*8+dy]=TMS[pixels[dy*8+dx]]
    return img

def run(path):
    n=Nemesis(path);v=n.stage_vram(1);m=n.stage_map(1)
    images=ROOT/'images';images.mkdir(exist_ok=True)
    original=msx_panel(n,v,1,176)
    scr=make_screen(m,tile_table(v),176)
    screen_to_png(scr,images/'stage1_column176_spectrum.png',1)
    original.save(images/'stage1_column176_msx_rom.png')
    spectrum=Image.open(images/'stage1_column176_spectrum.png').crop((0,0,256,176))
    # Normal game screenshot x=160-192 y=0-24 around terrain bump.
    crop=(154,0,198,32)
    for name,im in (('msx',original),('spectrum',spectrum)):
        im.crop(crop).resize((440,320),Image.Resampling.NEAREST).save(images/f'rom_mound_{name}.png')
    labels=Image.new('RGB',(900,357),(18,18,18))
    labels.paste(original.crop(crop).resize((440,320),Image.Resampling.NEAREST),(10,27))
    labels.paste(spectrum.crop(crop).resize((440,320),Image.Resampling.NEAREST),(450,27))
    d=ImageDraw.Draw(labels);d.text((12,8),'MSX (direct ROM data)',fill=(240,240,240))
    d.text((452,8),'Spectrum (same data, ZX attributes)',fill=(240,240,240))
    labels.save(images/'mound_rom_derived_comparison.png')
    print('Generated ROM-only mound comparison')

if __name__=='__main__':run(sys.argv[1])
