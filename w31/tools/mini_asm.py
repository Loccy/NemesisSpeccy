"""Assembler front-end. Same interface as the old whitelist assembler
(assemble(source, base) -> (bytes, labels)), but backed by sjasmplus so the
full Z80 instruction set is available. Source is lowercased as before."""
import os, re, subprocess, tempfile

def assemble(source, base=0x8000):
    src = source.lower()
    with tempfile.TemporaryDirectory() as d:
        asm = os.path.join(d, 'in.asm'); raw = os.path.join(d, 'out.bin'); sym = os.path.join(d, 'out.sym')
        with open(asm, 'w') as f:
            f.write(f'    device none\n    org 0x{base:04x}\n' + src + '\n')
        r = subprocess.run(['sjasmplus', '--nologo', '--msg=war', '--dirbol', f'--raw={raw}', f'--sym={sym}', asm],
                           capture_output=True, text=True)
        if r.returncode:
            raise ValueError('sjasmplus failed:\n' + r.stdout + r.stderr)
        code = open(raw, 'rb').read() if os.path.exists(raw) else b''
        labels = {}
        for line in open(sym):
            m = re.match(r'\s*([A-Za-z_][\w.]*):\s+EQU\s+0x([0-9A-Fa-f]+)', line)
            if m:
                labels[m.group(1).lower()] = int(m.group(2), 16) & 0xFFFF
    return code, labels
