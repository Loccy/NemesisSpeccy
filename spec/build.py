"""Build the Spectrum 128K version: relocate Konami's code for the Spectrum
target, generate tables, assemble, write nemesis.sna."""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RELOC = os.path.join(HERE, '..', 'reloc')

def run(cmd, cwd, env=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if r.returncode:
        sys.exit('FAILED: %s\n%s%s' % (' '.join(cmd), r.stdout, r.stderr))
    return r.stdout + r.stderr

# The cartridge: Nemesis (Konami RC-742, 128 KB MegaROM), not included; the
# SHA-256 is the one antxiko's disassembly is checked against.
ROM_SHA256 = '3210f8a0f2309dd4b9a89fc2b24d0f178ce4393a0a1f2854fbce545c361261bc'
# The disassembly, pinned: the port is built against commit DISASM_COMMIT, and
# DISASM_SHA256 is the SHA-256 of the files the build reads from it
# (src/nemesis_p00.asm to nemesis_p15.asm, concatenated in order).
# NEM_ANY_DISASM=1 builds from other versions at your own risk.
DISASM_COMMIT = '3e486bc2f39c65eb97a944cda246f85fd30218ec'
DISASM_SHA256 = 'b4c685a4a8649dbaa999b0a42abc59c245f69e83ce4011e24609a1d41e4be653'

def check_inputs():
    import hashlib
    root = os.path.normpath(os.path.join(HERE, '..'))
    rom = os.path.join(root, 'nem.rom')
    if not os.path.isfile(rom):
        sys.exit('nem.rom not found: put your copy of the Nemesis cartridge ROM '
                 '(RC-742, 131072 bytes) in %s' % root)
    if hashlib.sha256(open(rom, 'rb').read()).hexdigest() != ROM_SHA256:
        sys.exit('nem.rom is not the expected dump: its SHA-256 should be\n  ' + ROM_SHA256)
    ref = os.path.join(root, 'ref', 'Nemesis-disassembly')
    fetch = ('  git clone https://github.com/antxiko/Nemesis-disassembly %s\n'
             '  git -C %s checkout %s' % (ref, ref, DISASM_COMMIT))
    srcs = [os.path.join(ref, 'src', 'nemesis_p%02d.asm' % i) for i in range(16)]
    if not all(os.path.isfile(s) for s in srcs):
        sys.exit('the disassembly is missing; fetch the pinned version with\n' + fetch)
    h = hashlib.sha256()
    for s in srcs:
        h.update(open(s, 'rb').read())
    if h.hexdigest() != DISASM_SHA256 and os.environ.get('NEM_ANY_DISASM') != '1':
        sys.exit('the disassembly is not the pinned version; check it out with\n'
                 '  git -C %s checkout %s\n'
                 '(or set NEM_ANY_DISASM=1 to build from it anyway)' % (ref, DISASM_COMMIT))

def main():
    check_inputs()
    env = dict(os.environ, NEM_TARGET='spec')
    out = run([sys.executable, 'gen.py'], RELOC, env)
    if 'True' not in out.split('\n')[0]:
        sys.exit('identity check failed:\n' + out)
    run([sys.executable, 'tables.py'], HERE)
    run([sys.executable, 'gen_fullcmp.py'], HERE)
    defs = []
    if os.environ.get('NEM_PACE') == 'palmix':
        defs.append('-DPACE_PAL_MIX=1')
    # Pacing.  By default (0.110) adaptive: every tick drawn unless the game is
    # behind a rhythm of T eighths of a frame a tick by more than SLACK eighths,
    # never two ticks in a row undrawn (pace_adapt, page C); T,SLACK = 15,8
    # unless NEM_ADAPT=T,SLACK says otherwise, NEM_ADAPT=0 to turn it off.
    # Setting NEM_DRAW_EVERY or NEM_EXTRA selects the fixed schemes instead:
    # NEM_DRAW_EVERY=N, one tick in N drawn (2: the fast edition of 0.98-0.109);
    # NEM_DRAW_EVERY=0, one undrawn tick after every four drawn (the smooth
    # edition); NEM_EXTRA=N, one undrawn tick after every N drawn (NEM_EXTRA=0:
    # every tick drawn, for bench.py).
    adapt = os.environ.get('NEM_ADAPT')
    if adapt == '0' or (adapt is None and ('NEM_DRAW_EVERY' in os.environ or 'NEM_EXTRA' in os.environ)):
        adapt = None
    elif adapt is None:
        adapt = '15,8'
    if adapt:
        t, slack = (int(x) for x in adapt.split(','))
        defs += ['-DADAPT=1', '-DPACE_T=%d' % t, '-DPACE_SLACK=%d' % slack, '-DLOGIC_EXTRA=0']
    draw_every = 0 if adapt else int(os.environ.get('NEM_DRAW_EVERY', '0' if os.environ.get('NEM_EXTRA') else '2'))
    if draw_every:
        defs.append('-DDRAW_EVERY=%d' % draw_every)
        defs.append('-DLOGIC_EXTRA=0')
    elif os.environ.get('NEM_EXTRA'):
        defs.append('-DLOGIC_EXTRA=%d' % int(os.environ['NEM_EXTRA']))   # 0: draw every tick
    # Pacing limits (0.99): a tick may take as little as one frame, as on the
    # MSX (NEM_FPT, frames per tick at least; 2 before 0.99), and with one tick
    # in N drawn the screens are at least NEM_FLIP frames apart (default 3).
    defs.append('-DFRAMES_PER_TICK=%d' % int(os.environ.get('NEM_FPT', '1')))
    if draw_every:
        defs.append('-DFLIP_FRAMES=%d' % int(os.environ.get('NEM_FLIP', '3')))
    if os.environ.get('NEM_INVERT') == '0':
        defs.append('-DNO_INVERT=1')    # dense tiles stored as converted (not inverted)
    if os.environ.get('NEM_HOLD'):
        defs.append('-DHOLD_TICKS=%d' % int(os.environ['NEM_HOLD']))   # fire held this long: power-up too
    # The version on the title (0.100): VERSION, then A (adaptive, 0.110), S
    # (smooth) or F (fast),
    # top right (0.101), in Konami's font (ASCII - 0x20; its digits are
    # 0x10-0x19, and tile 0E is given a full stop by title_dot).
    # NEM_NEXT=1: the Spectrum Next build (nxbuild.sh), letter N.
    nxt = os.environ.get('NEM_NEXT') == '1'
    if nxt:
        defs.append('-DNEXT=1')
    ver = 'V' + open(os.path.join(HERE, 'VERSION')).read().strip() + ('N' if nxt else 'A' if adapt else 'F' if draw_every else 'S')
    codes = [0x0E if ch == '.' else ord(ch) - 0x20 for ch in ver]
    assert all(0x10 <= c <= 0x3A or c == 0x0E for c in codes), ver
    open(os.path.join(HERE, 'version.inc'), 'w').write(
        '; generated by build.py: %s\n    db %s\n' % (ver, ','.join('0x%02X' % c for c in codes)))
    test = os.environ.get('NEM_PIN_R') == '1'
    if test:
        defs.append('-DTEST=1')
    name = 'nemesis_test' if test else 'nemesis_next' if nxt else 'nemesis'
    log = run(['sjasmplus', '--nologo', '--msg=war', '--sym=%s.sym' % name, '--lst=%s.lst' % name] + defs
              + ['plat_spec.asm'], HERE)
    if log.strip():
        print(log)
    syms = {}
    for line in open(os.path.join(HERE, name + '.sym')):
        p = line.split()
        if len(p) >= 3 and p[1] == 'EQU':
            syms[p[0].rstrip(':')] = int(p[2], 16)
    for k in ('section_fixed_end', 'section_fixed2_end', 'section_A_end', 'section_C_end',
              'section_D_end', 'platform_end'):
        print('%-20s %04X' % (k, syms[k] & 0xFFFF))
    # The snapshot's SP: sjasmplus leaves 6000, just above Konami code
    # (5FFE-5FFF).  A loader that pushes the PC (or anything else) onto the
    # snapshot's stack to start it would overwrite that code, so SP points at
    # the boot stack instead (AD00-AE9F: zero at load, the IM2 table and stack
    # are built by plat_boot, which sets SP to the same place).
    sna = os.path.join(HERE, name + '.sna')
    d = bytearray(open(sna, 'rb').read())
    d[23:25] = (0xAEA0).to_bytes(2, 'little')
    open(sna, 'wb').write(d)
    print(name + '.sna written')

if __name__ == '__main__':
    main()
