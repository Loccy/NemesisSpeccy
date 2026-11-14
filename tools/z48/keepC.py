"""Stage N's keep list built from the census alone (not from stage 1's list):
what stage N runs or reads (whole routines and tables), the front end and
the screens before a life, death and game over (any stage), code no route
ran (less the typed cheats), the Big Core for stages 1-6, the power-up
dispatch table; then closed under direct control flow for code run in
stage N, in three or more stages, or never; then the data blocks the added
code refers to.  Writes reloc/z48_keepc_N.txt."""
import sys, pickle, collections, io, contextlib
N=int(sys.argv[1])
sys.argv=['x','cA.pkl','cB.pkl']
with contextlib.redirect_stdout(io.StringIO()):
    import report48 as R
from reach import *
grp=R.grp
d=pickle.load(open('keepN.pkl','rb')); SN=d['SN']; FE=d['FE']; D467=d['D467']
k1=pickle.load(open('keep1.pkl','rb'))['keep']
NEVER=k1-SN[1]-FE-D467
gitems=collections.defaultdict(list)
for (b,k),g in grp.items(): gitems[g].append((b,items[b][k][0]))
# the front end (13 November): what of it no stage's play runs is stage 1's
# alone (the title and a new game come only with stage 1 loaded); stages
# 2-8 reach it through a slot that loads stage 1 (z48_fe)
# (play: Konami's states 4-7.  The test runs' game over in stage 8 went on
# to the title with E061 still 8, so SN[8] holds the title too)
def play_groups():
    ex=bytearray(R.SIZE); rd=bytearray(R.SIZE)
    for k in R.EX:
        if k[0] in (4,5,6,7) and 1<=k[1]<=8: ex=R.OR(ex,R.EX[k]); rd=R.OR(rd,R.RD[k])
    xi,_=R.items_of(ex,True); di,_=R.items_of(rd,False)
    return {grp[x] for x in R.nl(xi)} | {grp[(b,k)] for b,k,a in di if not gen.left_out(b,a)}
PLAYG=play_groups()
FEX={g for g in FE if g not in D467 and g not in PLAYG}
if N!=1: SN[N]=SN[N]-FEX
G=SN[N]|D467|NEVER|(FE if N==1 else FE-FEX)
KEEP={x for g in G for x in gitems[g] if x[0] in B and not gen.left_out(*x)}
if N<=6: KEEP|={(1,items[1][k][0]) for k in range(len(items[1])) if 0x7C8D<=items[1][k][0]<0x7E03}
KEEP|={(3,a) for a in range(0xA094,0xA0A0) if a in idx[3]}
# stage 3's boss on later rounds (boss 6: the three boss tables' seventh
# entries, 1:7C41/7C65/7C7F), which the test runs never reached (13 November)
if N==3: KEEP|={(2,0x83A5),(2,0x86C0),(1,0x6A2C)}
EXCL=[] if N==5 else [(3,0xB7BF,0xB845),(3,0xB870,0xB8DA)]
# stage 5's skeletons and skulls already risen (13 November, gen.py): the
# skulls' rise and slide (3:B17D-B1D0) and half-drawn skull (3:B478-B49D),
# the skeletons' rising pictures (3:B567-B5CA, B5FF-B65E, B693-B6F6: the
# 4-byte items wholly inside them)
EXCL+=[(3,0xB17D,0xB1D1),(3,0xB478,0xB49E),(3,0xB567,0xB5CB),(3,0xB5FF,0xB65F),(3,0xB693,0xB6F7)]
# and the split pieces' chase (gen.py): apunta_la_aceleracion and its table
EXCL+=[(2,0x95EB,0x9857)]
excl=lambda b,a: any(eb==b and lo<=a<hi for eb,lo,hi in EXCL)
KEEP={x for x in KEEP if not excl(*x)}
def ran_where(b,a):
    st=set()
    for key,ex in R.EX.items():
        if ex[(b<<13)+(a-ORG[b])]: st.add(key[1])
    return st
CHEATS=('mira_lo_que_se_teclea','que_tecla','apunta_la_tecla','compara_','castiga','clave_','acierto_de_premio','borra_el_estado_del_marcador')
# whole routines: every item of a routine stage N runs that some stage ran or none did
rout=lambda b,a:(b,R.named(b,a))
live={rout(b,a) for g in SN[N] for b,a in gitems[g]}
for b in B:
    for it in items[b]:
        a=it[0]
        if it[2]=='code' and (b,a) not in KEEP and rout(b,a) in live and not gen.left_out(b,a) and not excl(b,a):
            KEEP.add((b,a))
PLAYER_DISP=('corre_los_nueve_disparos',)   # (not the states: state 2, the demo, is not in the 48K)
add={}
work=[(b,idx[b][a]) for b,a in KEEP if b in B and a in idx[b]]; seen=set()
while work:
    b,k=work.pop()
    if (b,k) in seen: continue
    seen.add((b,k)); it=items[b][k]
    if it[2]!='code': continue
    out,term=refs(b,k,frozenset())
    pdisp=R.named(b,it[0]) in PLAYER_DISP       # (the player's shots and the game's states: dispatch followed)
    nxt=[(tb,item_at(tb,t)) for tb,t,how in out if (how in ('jr','call','patch') or (how=='disp' and pdisp)) and tb in B]
    if not term and not gen.left_out(b,it[0]) and k+1<len(items[b]): nxt.append((b,k+1))
    for tb,tk in nxt:
        ti=items[tb][tk]
        if (tb,ti[0]) in KEEP or (tb,ti[0]) in add: work.append((tb,tk)); continue
        if excl(tb,ti[0]) or gen.left_out(tb,ti[0]) or ti[2]!='code': continue
        st=ran_where(tb,ti[0]); st8=st&set(range(1,9))
        if st and N not in st8 and len(st8)<3: continue
        if not st and R.named(tb,ti[0]).startswith(CHEATS): continue
        add[(tb,ti[0])]=ti[1]; work.append((tb,tk))
KEEP|=set(add)
# every routine the list keeps any of, kept whole, then closed again (13
# November: stage 8's third round reached 1:7B57, a branch of the background
# explosion's set-up that only one or two other stages' test runs took)
if __import__('os').environ.get('KEEP_WHOLE', '1') == '1':
    for _round in range(4):
        have={rout(b,a) for b,a in KEEP if b in B and a in idx[b] and items[b][idx[b][a]][2]=='code'}
        more=set()
        for b in B:
            for it in items[b]:
                a=it[0]
                if it[2]=='code' and (b,a) not in KEEP and rout(b,a) in have and not gen.left_out(b,a) and not excl(b,a) and not R.named(b,a).startswith(CHEATS):
                    more.add((b,a))
        if not more: break
        KEEP|=more
        for x in more: add[x]=items[x[0]][idx[x[0]][x[1]]][1]     # (so the data pass below gives them their tables: an inline dispatch table after `call 0x4067`, 1:607B's, 13 November)
        work=[(b,idx[b][a]) for b,a in more]
        while work:
            b,k=work.pop()
            it=items[b][k]
            if it[2]!='code': continue
            out,term=refs(b,k,frozenset())
            nxt=[(tb,item_at(tb,t)) for tb,t,how in out if how in ('jr','call','patch') and tb in B]
            if not term and not gen.left_out(b,it[0]) and k+1<len(items[b]): nxt.append((b,k+1))
            for tb,tk in nxt:
                ti=items[tb][tk]; x=(tb,ti[0])
                if x in KEEP or excl(*x) or gen.left_out(*x) or ti[2]!='code': continue
                st=ran_where(*x); st8=st&set(range(1,9))
                if st and N not in st8 and len(st8)<3: continue
                if not st and R.named(tb,ti[0]).startswith(CHEATS): continue
                KEEP.add(x); add[x]=ti[1]; work.append((tb,tk))
# what all eight lists keep (the core, near enough), from the lists as they
# were before this data rule (KEEP_PHASE=1 writes them; KEEP_PHASE=2 reads
# them here)
INTER=set()
if __import__('os').environ.get('KEEP_PHASE')=='2':
    _L=[]
    for _n in range(1,9):
        _s=set()
        for _l in open((os.environ.get('Z48_KEEP_OUT') or NEMROOT + '/reloc')+'/z48_keepc1_%d.txt'%_n):
            _p=_l.split()
            if len(_p)==2 and not _l.startswith('#'): _s.add((int(_p[0]),int(_p[1],16)))
        _L.append(_s)
    INTER=set.intersection(*_L)
elif __import__('os').environ.get('KEEP_PHASE')=='1':
    INTER=None
fix={}
def addblk(b,k):
    for j in range(k, block_end(b,k)):
        it=items[b][j]
        if (b,it[0]) not in KEEP and not excl(b,it[0]): fix[(b,it[0])]=it[1]
for b in B:
    its=items[b]
    for k,it in enumerate(its):
        if (b,it[0]) not in add and not (it[2]=='code' and (b,it[0]) in KEEP and INTER is not None and (b,it[0]) not in INTER): continue    # (the stage's own kept instructions too, not only the closure's: 13 November, 2:8B2C; the core's are gen.py's)
        if it[2]=='code' and (b,it[0]) in tables:
            j=k+1
            while j<len(its) and its[j][2]=='defw':
                if (b,its[j][0]) not in KEEP: fix[(b,its[j][0])]=its[j][1]
                j+=1
        out,_=refs(b,k,frozenset())
        for tb,t,how in out:
            if how in ('imm','data','tab','dw','patch') and tb in B:
                kk=item_at(tb,t)
                if items[tb][kk][2]!='code': addblk(tb,kk)
KEEP|=set(fix)
# every kept `call 0x4067` keeps the table of addresses after it, however
# the call came in (13 November: the whole-routine rule kept 1:607B in
# stages whose test runs never read its table)
for b in B:
    its=items[b]
    for k,it in enumerate(its):
        if it[2]=='code' and (b,it[0]) in KEEP and (b,it[0]) in tables:
            j=k+1
            while j<len(its) and its[j][2]=='defw':
                if not excl(b,its[j][0]): KEEP.add((b,its[j][0]))
                j+=1
# the pause (13 November): 0:451C's call to the typed codes is patched out
# (gen.py), and the pause's call to borra_el_estado_del_marcador kept
KEEP|={(0,it[0]) for it in items[0] if 0x50B4<=it[0]<0x50C9}
tot=sum(items[b][idx[b][a]][1] for b,a in KEEP if b in B and a in idx[b] and not gen.left_out(b,a))
print('stage %d: closure %d bytes, data %d, total %d'%(N,sum(add.values()),sum(fix.values()),tot))
if N==1:
    with open((os.environ.get('Z48_KEEP_OUT') or NEMROOT + '/reloc')+'/z48_feonly.txt','w') as f:
        for b,a in sorted({x for g in FEX for x in gitems[g] if x[0] in B}): f.write('%d %04X\n'%(b,a))
if __import__('os').environ.get('KEEP_PHASE')=='1':
    with open((os.environ.get('Z48_KEEP_OUT') or NEMROOT + '/reloc')+'/z48_keepc1_%d.txt'%N,'w') as f:
        for b,a in sorted(KEEP): f.write('%d %04X\n'%(b,a))
    sys.exit(0)
with open((os.environ.get('Z48_KEEP_OUT') or NEMROOT + '/reloc')+'/z48_keepc_%d.txt'%N,'w') as f:
    f.write('# items of banks 0-3 stage %d keeps, from the census alone (tools/z48/keepC.py)\n'%N)
    for b,a in sorted(KEEP): f.write('%d %04X\n'%(b,a))
