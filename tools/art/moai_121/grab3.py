import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os, pickle
sys.path.insert(0, (_SCRATCH + '/work/clean12/spec'))
os.environ['NEM_ALL'] = '1'
import emu
m = emu.Spectrum((_SCRATCH + '/work/clean12/spec/nemesis.sna'))
S = emu._syms((_SCRATCH + '/work/clean12/spec/nemesis.sym'))
ns = S['name_shadow']
grabs = []; reset = False; want = list(range(0x08, 0x1A0, 0x08))
for f in range(50 * 900):
    m.run_frame()
    st = m.k(0xE061); d = m.k(0xE063) | m.k(0xE064) << 8
    if st == 3 and d < 0x20: reset = True
    if m.k(0xE000) == 5 and st == 3 and reset and want and d >= want[0]:
        b2 = m.mem.banks[2]
        names = bytes(b2[ns - 0x8000 + i] for i in range(768))
        grabs.append(dict(dist=d, frame=f, screen=bytes(m.screen()), names=names,
                          tiles=bytes(m.mem.banks[7][0xDB00 - 0xC000:0xF600 - 0xC000]),
                          sprites=bytes(m.k(0xEC80 + i) for i in range(128))))
        print('grab dist %03X frame %d' % (d, f), flush=True)
        want.pop(0)
    if st == 3 and not want: break
    if st == 4: break
pickle.dump(grabs, open('grabs3.pkl', 'wb'))
