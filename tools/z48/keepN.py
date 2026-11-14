"""Keep-set sizes per stage, by keep1.py's rules."""
import sys, pickle
sys.argv=['x','cA.pkl','cB.pkl']
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import report48 as R
from reach import *
grp=R.grp; gsize=R.gsize; EX=R.EX; RD=R.RD
def gr(pred):
    ex=bytearray(R.SIZE); rd=bytearray(R.SIZE)
    for k in EX:
        if pred(k): ex=R.OR(ex,EX[k]); rd=R.OR(rd,RD[k])
    xi,_=R.items_of(ex,True); di,_=R.items_of(rd,False)
    return {grp[x] for x in R.nl(xi)} | {grp[(b,k)] for b,k,a in di if not gen.left_out(b,a)}, ex, rd
print('ticks:', sorted((k,v) for k,v in R.TICKS.items()))
FE,_,_=gr(lambda k:k[0] in (0,1,2,3))
D467,_,_=gr(lambda k:k[0] in (4,6,7))
sz=lambda s: sum(gsize[g] for g in s)
SN={}
for n in range(1,9):
    SN[n],_,_=gr(lambda k,n=n:k[1]==n)
    print('stage %d: own %5d  +FE/D467 %5d   not in stage1 set %5d'%(n,sz(SN[n]),sz(SN[n]|FE|D467),sz((SN[n]|FE|D467)-SN[1]-FE-D467)))
pickle.dump(dict(SN=SN,FE=FE,D467=D467),open('keepN.pkl','wb'))
