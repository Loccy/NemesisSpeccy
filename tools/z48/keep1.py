"""The 48K demo's keep set: groups of banks 0-3 that stage 1 needs."""
import sys, collections, pickle
sys.argv=['x','cA.pkl','cB.pkl']
import report48 as R
from reach import *
grp=R.grp; gsize=R.gsize; EX=R.EX; RD=R.RD
def gr(pred):
    ex=bytearray(R.SIZE); rd=bytearray(R.SIZE)
    for k in EX:
        if pred(k): ex=R.OR(ex,EX[k]); rd=R.OR(rd,RD[k])
    xi,_=R.items_of(ex,True); di,_=R.items_of(rd,False)
    return {grp[x] for x in R.nl(xi)} | {grp[(b,k)] for b,k,a in di if not gen.left_out(b,a)}, ex, rd
S1,ex1,rd1=gr(lambda k:k[1]==1)
FE,_,_=gr(lambda k:k[0] in (0,1,2,3))
D467,_,_=gr(lambda k:k[0] in (4,6,7))
allstatic=set()
for s in R.STAGES:
    allstatic|={grp[x] for x in R.res[s]['r'] if items[x[0]][x[1]][2]=='code' and not gen.left_out(x[0],items[x[0]][x[1]][0])}
cheat=lambda g: R.named(*g).startswith(('mira_lo_que_se_teclea','que_tecla','apunta_la_tecla','compara_','castiga','clave_','dos_fases','acierto_de_premio','borra_el_estado_del_marcador','cambia_b_bytes'))
NEVER={g for g in allstatic-R.ever_groups if not cheat(g)}
KEEP=S1|FE|D467|NEVER
print('stage 1 %d, +front end %d, +states 4/6/7 any stage %d, +never-run %d -> keep %d'%(sum(gsize[g] for g in S1),sum(gsize[g] for g in FE-S1),sum(gsize[g] for g in D467-S1-FE),sum(gsize[g] for g in NEVER-S1-FE-D467),sum(gsize[g] for g in KEEP)))
for b in B:
    tot=sum(gsize[g] for g in gsize if g[0]==b); k=sum(gsize[g] for g in KEEP if g[0]==b)
    print(' bank %d: keep %5d of %5d'%(b,k,tot))
# data banks read in stage 1 (all states with stage 1, and front end)
for b in (5,9,10,11,12):
    offs=[o for o in range(8192) if rd1[(b<<13)+o]]
    if offs: print(' data bank %d: %d bytes read, %04X-%04X'%(b,len(offs),offs[0],offs[-1]))
o11=[o for o in range(8192) if rd1[(11<<13)+o]]
# runs
runs=[];s=None
for o in o11:
    if s is None or o!=p+1:
        if s is not None: runs.append((s,p))
        s=o
    p=o
runs.append((s,p)); print(' bank 11 runs:',len(runs),' span 8000+%04X..%04X'%(o11[0],o11[-1]))
pickle.dump(dict(keep=KEEP,grp=grp),open('keep1.pkl','wb'))
