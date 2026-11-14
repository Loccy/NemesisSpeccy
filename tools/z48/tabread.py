"""For every data item of banks 0-3, the stages (1-8) whose test runs read
any byte of it (any of Konami's states; the front end, stage 0, counts as
stage 1).  Writes reloc/z48_reads.txt: bank addr stages."""
import sys, collections, io, contextlib
sys.argv=['x','cA.pkl','cB.pkl']
with contextlib.redirect_stdout(io.StringIO()):
    import report48 as R
from reach import *
rd={}
for k,v in R.RD.items():
    s=k[1] if 1<=k[1]<=8 else (1 if k[1]==0 else None)
    if s is None: continue
    rd[s]=R.OR(rd[s],v) if s in rd else bytearray(v)
out=[]
for b in B:
    for it in items[b]:
        if it[2]=='code': continue
        a,n=it[0],it[1]
        st=[s for s in sorted(rd) if any(rd[s][(b<<13)+(a-ORG[b])+j] for j in range(n))]
        if st: out.append('%d %04X %s'%(b,a,','.join(map(str,st))))
open((os.environ.get('Z48_KEEP_OUT') or NEMROOT + '/reloc')+'/z48_reads.txt','w').write('\n'.join(out)+'\n')
print(len(out),'items read')
