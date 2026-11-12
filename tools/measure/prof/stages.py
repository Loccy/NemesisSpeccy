import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os, time
os.environ['NEM_ALL']='1'
sys.path.insert(0,(_NEM + '/spec'))
from emu import Spectrum, keys_default
s=Spectrum((_NEM + '/spec/nemesis.sna')); R=s.regs
last=None; t=time.time(); lt=0; lf=0; rows=[]
for f in range(90000):
    s.run_frame()
    st=(s.k(0xE000), s.k(0xE061))
    if st!=last:
        print('frame %6d state %d stage %d' % (f, st[0], st[1]), flush=True); last=st
    if f%1000==999:
        tk=s.k(0xE003)
    if st==(5,1) and f>80000: break
print('%.0f s'%(time.time()-t))
