"""Input lag on the simulated PAL MSX: frames from the joystick going down
to the first frame whose VRAM sprite table (at that frame's start) shows the
ship lower."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys
R = _NEM
sys.path.insert(0, R + '/reloc'); sys.path.insert(0, R + '/msxsim')
import msxsim
msxsim.FRAME_T = 71364                     # PAL
import layoutsim as L
class O(L.Original):
    bios_call = msxsim.MSX.bios_call       # plain keys/joy
m = O(); m.boot()
f = 0
while m.mem[0xE000] != 5:
    m.keys[8] = 0xFE if (f // 10) % 4 == 0 else 0xFF
    m.run_frame(); f += 1
m.keys[8] = 0xFF
for i in range(150): m.run_frame()
def ship_entries():
    v = m.vdp.vram; out = []
    for i in range(32):
        y = v[0x3B00 + 4 * i]
        if y == 0xD0: break
        out.append((y, v[0x3B01 + 4 * i], v[0x3B02 + 4 * i]))
    return out
def ship_y():
    sy, sx = m.mem[0xE204], m.mem[0xE206]
    c = [e for e in ship_entries() if abs(e[1] - sx) <= 16 and abs(((e[0] + 1) & 255) - sy) <= 16]
    return min(e[0] for e in c) if c else None
lags = []
for trial in range(24):
    joy = 0x3F & ~(2 if trial % 2 == 0 else 1)   # down, then up, alternately
    for k in range(trial % 5): m.run_frame()     # vary the phase
    y0 = ship_y()
    m.joy = joy
    for k in range(12):
        m.run_frame()                            # frame k runs with the stick held
        y = ship_y()
        if y is not None and y0 is not None and y != y0:
            lags.append(k + 1); break            # visible from the next frame on
    m.joy = 0x3F
    for k in range(20): m.run_frame()
print('MSX PAL lag (frames, key down at a frame start -> first frame showing the move):', lags)
print('min %d max %d mean %.2f' % (min(lags), max(lags), sum(lags) / len(lags)))
