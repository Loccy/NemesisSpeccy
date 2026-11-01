"""Game ticks per second over a stretch of play (scripted keys)."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys
sys.path.insert(0,NEM_ROOT + '/spec')
from emu import Spectrum
secs=float(sys.argv[1]); skip=float(sys.argv[2])
m=Spectrum()
for f in range(int(skip*50)): m.run_frame()
last=m.k(0xE003); tot=0; per=[]; acc=0
for f in range(int(secs*50)):
    m.run_frame()
    c=m.k(0xE003); d=(c-last)&255; last=c; tot+=d; acc+=d
    if f%50==49: per.append(acc); acc=0
print('ticks/s %.1f  per second: %s' % (tot/secs, per))
