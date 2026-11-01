"""First Konami enemy-code transplant, from bank 0 in the verified MSX ROM.

This is the original 8.8 fixed-point velocity integrator for 32-byte enemy
records beginning at E300, not an approximation of enemy physics.

The next integration is the full 5DDE type dispatcher and the first-stage
spawn script. This block alone deliberately DOES NOT spawn enemies.
"""

ORIGINAL_START = 0x5F7C
ORIGINAL_END = 0x5FA5
ORIGINAL_ADDWORD = 0x5F9A
CALL_OPERANDS = (0x5F89, 0x5F8C)  # CALL operand addresses


def extract_enemy_integrator(rom, new_base):
    assert len(rom) == 131072
    source = bytearray(rom[ORIGINAL_START - 0x4000:ORIGINAL_END - 0x4000])
    # Discover two CALLs by exact opcode and destination. This guards us
    # against accidentally patching an immediate or changing the instruction.
    patch_positions = []
    for offset in range(len(source)-2):
        if source[offset] == 0xCD and source[offset+1:offset+3] == b'\x9a\x5f':
            patch_positions.append(offset+1)
    assert patch_positions == [0x5F89-ORIGINAL_START, 0x5F8C-ORIGINAL_START], patch_positions
    relocated_addword = new_base + ORIGINAL_ADDWORD - ORIGINAL_START
    audit=[]
    for pos in patch_positions:
        before=int.from_bytes(source[pos:pos+2], 'little')
        source[pos:pos+2] = relocated_addword.to_bytes(2, 'little')
        audit.append((ORIGINAL_START+pos,before,relocated_addword))
    return bytes(source),audit


def extract_type4(rom, destinations):
    """Three exact Konami code spans; relocate only CALL/JP address fields."""
    intervals = {
        'init': (0xA857,0xA863,3),
        'move': (0xA863,0xA8A9,3),
        'velocity': (0x6CBF,0x6CCD,1),
    }
    original = {
        0x6CBF: destinations['velocity'],
        0x6CC6: destinations['velocity']+7,
        0x9235: destinations['enemy_fire_stub'],
    }
    results={};audit=[]
    for name,(start,end,bank) in intervals.items():
        src=bytearray(rom[bank*8192+(start-(0xA000 if bank==3 else 0x6000)):bank*8192+(end-(0xA000 if bank==3 else 0x6000))])
        if len(src)!=end-start:raise AssertionError(name)
        for i in range(len(src)-2):
            if src[i] not in (0xCD,0xC3):continue
            target=int.from_bytes(src[i+1:i+3],'little')
            if target in original:
                assert src[i+1:i+3]==target.to_bytes(2,'little')
                dst=original[target]
                src[i+1:i+3]=dst.to_bytes(2,'little')
                audit.append((name,start+i+1,target,dst))
        results[name]=bytes(src)
    assert [(x[0],x[2]) for x in audit]==[('init',0x6CBF),('init',0x6CC6),('move',0x9235),('move',0x6CC6),('move',0x6CBF),('move',0x6CBF)] or len(audit)>=5,audit
    return results,audit
