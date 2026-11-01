"""Who calls a routine: over SECONDS of play (after 22 seconds of the title
and start), count the calling routines of each call to ROUTINE, per second.
usage: callers.py ROUTINE SECONDS"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, os, collections, bisect
sys.path.insert(0,NEM_ROOT + '/spec')
from emu import Spectrum, keys_default
syms={}
for l in open('nemesis.sym'):
    m=re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)',l)
    if m: syms[m.group(1)]=int(m.group(2),16)&0xFFFF
target=syms[sys.argv[1]]
fixed=sorted((v,k) for k,v in syms.items() if v<0xC000)
fk=[v for v,k in fixed]
m=Spectrum()
for f in range(22*50): m.run_frame()
sim=m.sim; regs=m.regs; FR=70908
end=regs[25]+int(float(sys.argv[2])*50*FR); c=collections.Counter(); ticks0=None
t0=syms['pm_tick']; nt=0
while regs[25]<end:
    sim.trace(m.pc,target,0,end,1,None,None,None,None,None); m.pc=regs[24]
    if m.pc!=target: break
    sp=regs[12]; ret=m.mem[sp]|m.mem[sp+1]<<8
    if ret<0xC000:
        i=bisect.bisect_right(fk,ret)-1; nm=fixed[i][1]
    else: nm='paged %04X p%d'%(ret, m.tr.out7ffd&7)
    c[nm]+=1
    sim.trace(m.pc,-1,1,end,1,None,None,None,None,None); m.pc=regs[24]
tot=sum(c.values()); secs=float(sys.argv[2])
print('calls per second', tot/secs)
for k,v in c.most_common(25): print('%6.1f/s %s'%(v/secs,k))
