import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, collections, bisect
sys.path.insert(0,NEM_ROOT + '/spec')
from emu import Spectrum
syms={}
for l in open('nemesis.sym'):
    m=re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)',l)
    if m: syms[m.group(1)]=int(m.group(2),16)&0xFFFF
inv={v:k for k,v in syms.items() if k.startswith('far_m') or k.startswith('far_0x')}
fixed=sorted((v,k) for k,v in syms.items() if v<0xC000); fk=[v for v,k in fixed]
m=Spectrum()
for f in range(22*50): m.run_frame()
sim=m.sim; regs=m.regs; FR=70908
end=regs[25]+int(8*50*FR); c=collections.Counter()
go=syms['far_go']
while regs[25]<end:
    sim.trace(m.pc,go,0,end,1,None,None,None,None,None); m.pc=regs[24]
    if m.pc!=go: break
    sp=regs[12]; ret=m.mem[sp]|m.mem[sp+1]<<8   # points at db page
    stubaddr=ret-3; name=inv.get(stubaddr,'?')
    page=m.mem[ret]; cur=m.tr.out7ffd&7
    caller=m.mem[sp+2]|m.mem[sp+3]<<8
    c[(name, 'same' if page==cur else 'switch', 'caller fixed' if caller<0xC000 else 'caller p%d'%cur)]+=1
    sim.trace(m.pc,-1,1,end,1,None,None,None,None,None); m.pc=regs[24]
tot=sum(c.values()); print('far calls/s', tot/8)
agg=collections.Counter()
for (n,s,cl),v in c.items():
    tgt=n.split('_')[1][0] if n!='?' else '?'
    agg[(s,cl,'target bank '+n[5:6])]+=v
for k,v in agg.most_common(): print('%7.1f/s'%(v/8),k)
for k,v in c.most_common(15): print('%7.1f/s'%(v/8),k)
