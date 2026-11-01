import sys, pickle, collections, re
sys.path.insert(0,'.')
import test_convert as tc
S = pickle.load(open('vram_states.pkl','rb')); vr = S[('stage',1)]
lab = sorted((v,k) for k,v in tc.syms.items() if 0x8000<=v<0xAD00 and not k.startswith('far_'))
import bisect
keys=[v for v,k in lab]
def name(pc):
    i=bisect.bisect_right(keys,pc)-1; return lab[i][1] if i>=0 else '?'
hist=collections.Counter(); n=0
mem=tc.mem; r=tc.sim.registers
for ch in range(0,256,3):
    o=ch*8; rows=tuple((vr[0x2000+o+l], vr[o+l]) for l in range(8))
    for i,(p,c) in enumerate(rows): mem[tc.syms['cv_pat']+i]=p; mem[tc.syms['cv_col']+i]=c
    sp=0xAEA0; mem[sp]=0xFE; mem[sp+1]=0xFF; mem[0xFFFE]=0x18; mem[0xFFFF]=0xFE
    r[12]=sp; r[24]=tc.syms['convert_tile']
    while r[24]!=0xFFFE:
        pc=r[24]; t=r[25]; tc.sim.opcodes[mem[pc]](); hist[name(pc)]+=r[25]-t
    n+=1
tot=sum(hist.values())
for k,v in hist.most_common(25): print('%-28s %6d per tile  %4.1f%%'%(k, v//n, 100*v/tot))
