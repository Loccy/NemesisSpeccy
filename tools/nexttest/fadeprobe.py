"""Logs the dissolve's fade step by step: Konami's progress (E1A0-E1A2), the
Next's step (lo_flv) and channels (lo_fdr/g/b), with a screenshot at each new
step and a few of Layer 2's palette entries.  fadeprobe.py file.nex OUT PORT"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, time, re
sys.argv += []
NEX, OUT, PORT = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]), sys.argv[3]
os.makedirs(OUT, exist_ok=True)
sys.argv = [sys.argv[0], NEX, OUT, PORT]
src = open((_SCRATCH + '/gfx/dbg/fulltest.py')).read()
head = src[:src.index('try:\n    time.sleep(3)')]
os.environ.setdefault('SPD', '100')
exec(head)
dz = sym['dz_on']
try:
    time.sleep(3); k = conn(); zr()
    keys(space=True); time.sleep(0.4); keys()
    t = time.time()
    while r8(0xE000) != 5 and time.time() - t < 30: time.sleep(0.5)
    log('in play: ' + state())
    fire = False; t0 = time.time()
    while time.time() - t0 < 900:
        fire = not fire; keys(space=fire); time.sleep(0.1)
        if r8(0xE151) and r8(0xE152) in (3, 4): break
    log('boss: ' + state())
    keys(space=True)
    zr('enter-cpu-step'); zr('enable-breakpoints')
    k.settimeout(900)
    for i in range(50):
        zr('set-breakpoint 1 PC=%04XH' % sym['dz_mark']); zr('run')
        if rd(0xE1A0 - K)[0] == 0 and r8(0xE151): break
        zr('set-breakpoint 1 PC=%04XH' % sym['lo_render']); zr('run')
    log('dissolve starts: ' + state() + ' dz %d' % rd(dz)[0])
    keys()
    zr('enter-cpu-step'); zr('enable-breakpoints'); zr('set-breakpoint 1 PC=%04XH' % sym['lo_render'])
    n = 0; prev = -1; seen = []
    for scr in range(400):
        zr('run')
        e = rd(0xE1A0 - K, 3); f = rd(0x3FF0, 6); on = rd(dz)[0]
        seen.append(f[1])
        if f[1] != prev or scr < 3:
            log('screen %3d dz %d E1A0 %02X E1A1 %02X E1A2 %02X | step %2d  R-%d G-%d B-%d' % (scr, on, e[0], e[1], e[2], f[1], f[3], f[4], f[5]))
            pal = zr('tbblue-get-palette layer2 first 0 256').split()
            pal = [x for x in pal if re.fullmatch(r'[0-9A-Fa-f]{3}', x)][:256]
            log('   pal 0-15 %s | D1-DF %s' % (' '.join(pal[0:16]), ' '.join(pal[0xD1:0xE0])))
            pb = rd(0x8006)[0]; bank = 13 if pb & 8 else 9
            zr('set-memory-zone 0'); img = []
            for t in range(3):
                for o in range(0, 0x4000, 0x1000): img += rd(0x40000 + (bank + t) * 0x4000 + o, 0x1000)
            zr('set-memory-zone -1')
            open(os.path.join(OUT, 'l2_%03d_s%02d.bin' % (scr, f[1])), 'wb').write(bytes(img))
            open(os.path.join(OUT, 'pal_%03d_s%02d.txt' % (scr, f[1])), 'w').write(' '.join(pal))
            prev = f[1]
        if not on: log('dissolve flag off at screen %d' % scr); break
    log('steps by screen: ' + ' '.join(map(str, seen)))
    pal = zr('tbblue-get-palette layer2 first 0 16'); log('layer2 0-15 at the end: ' + ' '.join(pal.split()[:40]))
finally:
    try: keys()
    except Exception: pass
    p.kill()
