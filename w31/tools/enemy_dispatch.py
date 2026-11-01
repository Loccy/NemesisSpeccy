"""Audit the *original* Konami enemy dispatch table at 5DFD, no guesses.

The live 5DDE dispatcher indexes its 31 two-byte entries with type-1 and
jumps to bank 0/1/2/3 code. A complete transplant must preserve this mapping,
plus the original stage-script activation logic, before enemies become visible.
"""
import hashlib
from pathlib import Path

BANK0=0
EXPECTED_ROM_HASH='3210f8a0f2309dd4b9a89fc2b24d0f178ce4393a0a1f2854fbce545c361261bc'


def dispatch_entries(rom):
    if hashlib.sha256(rom).hexdigest()!=EXPECTED_ROM_HASH:
        raise ValueError('Not the exact original MSX Nemesis ROM')
    offset=0x5dfd-0x4000
    payload=rom[offset:offset+31*2]
    assert len(payload)==62
    entries=[int.from_bytes(payload[2*i:2*i+2],'little') for i in range(31)]
    assert entries[0]==0x9119 and entries[6]==0x5ee7 and entries[-1]==0xbd7d
    return entries


def source_bank(pc):
    if 0x4000<=pc<0x6000:return 0
    if 0x6000<=pc<0x8000:return 1
    if 0x8000<=pc<0xa000:return 2
    if 0xa000<=pc<0xc000:return 3
    raise ValueError('Unknown Konami address '+hex(pc))


def report(rom):
    values=dispatch_entries(rom)
    output=['enemy_type\tmsx_entry\tcartridge_bank']
    for t,v in enumerate(values,1):
        output.append(f'{t:02X}\t{v:04X}\t{source_bank(v)}')
    return '\n'.join(output)+'\n'

if __name__=='__main__':
    import sys
    print(report(Path(sys.argv[1]).read_bytes()),end='')
