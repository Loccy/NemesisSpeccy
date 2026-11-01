"""Run a 128K snapshot with contention, scripted keys; report ticks/sec and grab screens.
usage: bench.py SNAP COUNTER_ADDR SECONDS [png_every_sec] [outprefix] [--ff N_ticks_poke]"""
import sys, time
from skoolkit.snapshot import Snapshot
from skoolkit.simutils import from_snapshot
from skoolkit import CCMIOSimulator
from skoolkit.trace import Tracer
from skoolkit.pagingtracer import Memory
from PIL import Image

FRAME=70908
PAL=[(0,0,0),(0,0,0xd7),(0xd7,0,0),(0xd7,0,0xd7),(0,0xd7,0),(0,0xd7,0xd7),(0xd7,0xd7,0),(0xd7,0xd7,0xd7),
     (0,0,0),(0,0,0xff),(0xff,0,0),(0xff,0,0xff),(0,0xff,0),(0,0xff,0xff),(0xff,0xff,0),(0xff,0xff,0xff)]
def scr_png(scr,path):
    im=Image.new('RGB',(256,192))
    px=im.load()
    for y in range(192):
        a=((y&0xc0)<<5)|((y&7)<<8)|((y&0x38)<<2)
        for cx in range(32):
            b=scr[a+cx]; at=scr[6144+(y>>3)*32+cx]
            br=8 if at&64 else 0
            ink=PAL[(at&7)+br]; pap=PAL[((at>>3)&7)+br]
            for bit in range(8):
                px[cx*8+bit,y]=ink if b&(0x80>>bit) else pap
    im.resize((512,384),0).save(path)

def keys_for(frame):
    kb=[0]*8
    kb[7]|=1 if (frame//6)%2==0 else 0     # tap SPACE: fire
    ph=(frame//100)%4
    if ph==1: kb[2]|=1     # Q up
    if ph==3: kb[1]|=1     # A down
    return kb

def run(path,counter,seconds,png_every=0,prefix='shot',pokes=()):
    snap=Snapshot.get(path)
    if snap.type=='SNA' and len(snap.tail)==0xC000: snap.sp=(snap.sp+2)%65536
    sim=from_snapshot(CCMIOSimulator,snap,{},{'ay':[None]*16},{'fast_djnz':False,'fast_ldir':False})
    mem=sim.memory; mem.out7ffd(snap.out7ffd)
    tr=Tracer(sim,snap.border,snap.out7ffd,snap.outfffd,list(snap.ay),snap.outfe,False)
    sim.set_tracer(tr)
    for bank,addr,val in pokes: mem.banks[bank][addr]=val
    regs=sim.registers; pc=snap.pc
    def ctr():
        b,a=counter
        return mem.banks[b][a]|(mem.banks[b][a+1]<<8 if len(counter)>2 and counter[2]==2 else 0)
    samples=[]
    t0=regs[25]; last=ctr(); total=0
    for f in range(int(seconds*50)):
        tr.keyboard=keys_for(f)
        sim.trace(pc,-1,0,t0+(f+1)*FRAME,1,None,None,None,None,None)
        pc=regs[24]
        c=ctr(); d=(c-last)%(65536 if len(counter)>2 else 256); last=c; total+=d
        samples.append(d)
        if png_every and f%(png_every*50)==png_every*50-1:
            vis=mem.banks[7 if tr.out7ffd&8 else 5][:6912]
            scr_png(vis,f'{prefix}_{f//50:03d}.png')
    return total,samples,sim,tr
if __name__=='__main__':
    p=sys.argv
    tot,s,_,_=run(p[1],(int(p[2]),int(p[3],16)),float(p[4]),int(p[5]) if len(p)>5 else 0,p[6] if len(p)>6 else 'shot')
    secs=len(s)/50
    print(f'ticks={tot} in {secs:.0f}s -> {tot/secs:.1f} ticks/s')
    per=[sum(s[i:i+50]) for i in range(0,len(s),50)]
    print('per-second:',per)
