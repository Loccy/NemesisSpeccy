import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, pickle
sys.path.insert(0,'.')
from emu import Spectrum, keys_default
from fit_model import heur_q
sys.path.insert(0,NEM_ROOT + '/w31/tools')
syms={}
for l in open('nemesis.sym'):
    m=re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)',l)
    if m: syms[m.group(1)]=int(m.group(2),16)
secs=float(sys.argv[1])
m=Spectrum()
for f in range(int(secs*50)): m.run_frame()
B=m.mem.banks
def fixed(a): return B[2][a-0x8000] if a>=0x8000 else B[5][a-0x4000]
name=bytes(fixed(syms['name_shadow']+i) for i in range(768))
print('row 23 names:', name[23*32:24*32].hex(' '))
print('row 22 names:', name[22*32:23*32].hex(' '))
# stars in name table rows 0-21
import collections
print('name histogram rows0-21:', collections.Counter(name[:704]).most_common(8))
def tile(third,i):
    pat=[B[6][0xE800-0xC000+third*0x800+i*8+r] for r in range(8)]
    col=[B[4][0xE800-0xC000+third*0x800+i*8+r] for r in range(8)]
    conv=[B[7][((0xDB+9*third+r)<<8)-0xC000+i] for r in range(9)]
    return pat,col,conv
for third,i in ((0,0xF6),(0,0xF7),(1,0xF6),(2,0x40),(2,name[23*32+5]),(2,name[22*32+3])):
    pat,col,conv=tile(third,i)
    want=heur_q(tuple(zip(pat,col)))
    cd=B[2][syms['tile_cdirty']-0x8000+third*32+(i>>3)]>>(i&7)&1; pd=B[2][syms['tile_pdirty']-0x8000+third*32+(i>>3)]>>(i&7)&1
    print('third %d tile %02X pat %s col %s conv %s model %s dirty c%d p%d'%(third,i,bytes(pat).hex(),bytes(col).hex(),bytes(conv).hex(),want.hex(),cd,pd))
from convert import colour_fit
from extract import TMS
for i in (0x15,0x16,0x2f,0x0b,0x02,0x12):
    pat,col,conv=tile(2,i)
    pix=[]
    for p,c in zip(pat,col): pix.extend((c>>4) if p&(128>>k) else (c&15) for k in range(8))
    print('tile %02X pat %s col %s conv %s model %s full %s'%(i,bytes(pat).hex(),bytes(col).hex(),bytes(conv).hex(),heur_q(tuple(zip(pat,col))).hex(),colour_fit(tuple(pix)).hex()))
