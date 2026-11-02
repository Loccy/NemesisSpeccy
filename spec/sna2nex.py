"""128K .sna -> .NEX (header per wiki.specnext.dev/NEX_file_format, V1.2)."""
import sys
sna=open(sys.argv[1],'rb').read(); pc=int(sys.argv[3],16); sp=int(sys.argv[4],16)
assert len(sna) in (131103,147487), len(sna)
banks={}
banks[5]=sna[27:27+16384]; banks[2]=sna[27+16384:27+32768]; cur_data=sna[27+32768:27+49152]
p7ffd=sna[49181]; cur=p7ffd&7; banks[cur]=cur_data
o=49183
for b in (0,1,3,4,6,7):
    if b==cur: continue
    banks[b]=sna[o:o+16384]; assert len(banks[b])==16384; o+=16384
assert sorted(banks)==list(range(8)), sorted(banks)
h=bytearray(512)
h[0:4]=b'Next'; h[4:8]=b'V1.2'
extra=open(sys.argv[5],'rb').read() if len(sys.argv)>5 else None
hi=open(sys.argv[6],'rb').read() if len(sys.argv)>6 else b''   # banks 16 on
assert len(hi)%16384==0
nhi=len(hi)//16384
h[8]=0; h[9]=8+(1 if extra else 0)+nhi; h[10]=0; h[11]=0
h[12:14]=sp.to_bytes(2,'little'); h[14:16]=pc.to_bytes(2,'little')
for b in range(8): h[18+b]=1
if extra:
    assert len(extra)==16384; h[18+8]=1
for b in range(nhi): h[18+16+b]=1
h[134]=0          # Next registers reset
h[139]=cur        # entry bank at C000
out=bytes(h)+b''.join(banks[b] for b in (5,2,0,1,3,4,6,7))+(extra or b'')+hi
open(sys.argv[2],'wb').write(out)
print('7FFD=%02X entry bank %d, PC %04X SP %04X, %d bytes'%(p7ffd,cur,pc,sp,len(out)))
