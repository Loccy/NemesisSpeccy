"""Extract the two distinct stage-one object trigger streams from Konami's ROM.

No hand-authored coordinates, pattern numbers or timing. The source byte
ranges are stage pointers referenced by original routines 90D1 and 62D9.
The records only describe activation. They are NOT a substitute for Konami's
object initialisation (6A72), update dispatch (5DDE/6008) or rendering.
"""
from pathlib import Path
import csv
import hashlib

EXPECTED_SHA256 = '3210f8a0f2309dd4b9a89fc2b24d0f178ce4393a0a1f2854fbce545c361261bc'
CARTRIDGE_BANK_BYTES = 8192


def source(rom, bank, address):
    origin = 0x8000 if bank == 2 else 0x6000
    offset = address - origin
    if not 0 <= offset < CARTRIDGE_BANK_BYTES:
        raise ValueError(f'Out of bank {bank} range: {address:04X}')
    return rom[bank * CARTRIDGE_BANK_BYTES + offset]


def word(rom, bank, address):
    return source(rom, bank, address) | source(rom, bank, address+1) << 8


def read_events(rom, bank, pointer_table, stage=1):
    """The same stage indexing (base+2*stage) as Konami 9100."""
    head = word(rom, bank, pointer_table + 2*stage)
    pointer = head
    result = []
    for index in range(256):
        distance = word(rom, bank, pointer)
        code = source(rom, bank, pointer + 2)
        if distance == 0xFFFF:
            return head, result, pointer
        if result and distance <= result[-1]['distance']:
            raise ValueError(f'Nonascending distance in bank {bank}: {distance:04X}')
        result.append(dict(index=index, distance=distance, flags=code,
                           source_bank=bank, source_address=pointer))
        pointer += 3
    raise ValueError(f'No script sentinel in bank {bank}')


def parse(rom):
    if len(rom) != 131072 or hashlib.sha256(rom).hexdigest() != EXPECTED_SHA256:
        raise ValueError('Expected the exact original Konami RC-742 cartridge')
    # Stage 1 object scripts from p01:62D9 and p02:90D1 respectively.
    background = read_events(rom, 1, 0x64FA)
    flyers = read_events(rom, 2, 0x9262)
    return {'background_objects': background, 'flying_enemies': flyers}


def export_csv(rom, destination):
    streams = parse(rom)
    with open(destination, 'w', newline='') as out:
        w = csv.writer(out)
        w.writerow(['stream','index','distance_hex','distance_decimal','data_hex',
                    'x_source_bits','variant_bits','rom_bank','rom_address_hex'])
        for name, (_, events, _) in streams.items():
            for e in events:
                w.writerow([name,e['index'],f"{e['distance']:04X}",e['distance'],
                            f"{e['flags']:02X}",e['flags']&31,e['flags']>>6,
                            e['source_bank'],f"{e['source_address']:04X}"])
    return streams


if __name__=='__main__':
    import sys
    if len(sys.argv) != 3:
        raise SystemExit('usage: python tools/original_stage1_events.py ROM OUTPUT.csv')
    streams = export_csv(Path(sys.argv[1]).read_bytes(), Path(sys.argv[2]))
    for name, (head, events, sentinel) in streams.items():
        print(f'{name}: {len(events)} events, table at {head:04X}, sentinel at {sentinel:04X}')
        print(' '.join(f"{e['distance']:04X}:{e['flags']:02X}" for e in events))
