import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re
sys.path.insert(0,NEM_ROOT + '/spec')
from emu import Spectrum
syms={}
for l in open('nemesis.sym'):
    m=re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)',l)
    if m: syms[m.group(1)]=int(m.group(2),16)&0xFFFF
m=Spectrum()
for f in range(22*50): m.run_frame()
sim=m.sim; regs=m.regs; v=[]
for n in range(100):
    sim.trace(m.pc,syms['isr'],0,regs[25]+70908*3,1,None,None,None,None,None); m.pc=regs[24]
    sp=regs[12]; ret=m.mem[sp]|m.mem[sp+1]<<8; t=regs[25]
    while True:
        sim.trace(m.pc,ret,0,regs[25]+70908,0,None,None,None,None,None); m.pc=regs[24]
        if regs[12]==sp+2: break
    v.append(regs[25]-t)
v.sort(); print('ISR T: median %d p90 %d max %d'%(v[50],v[90],v[-1]))
