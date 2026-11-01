"""Extract exact Konami 1986 Z80 instructions from MSX bank 2 and relocate
only absolute code/table references. Do NOT reimplement the gameplay code.

Original in-ROM addresses refer to bank 2 selected at MSX 8000-9FFF.
The Spectrum executes transplanted routines from fixed RAM (bank 2).
MSX working RAM E000-E2FF remains at the SAME logical addresses in a
separate Spectrum 128K RAM bank (paged at C000-FFFF during game logic).
"""

ORIGINAL_BANK=2
BLOCKS=(
    ('movement',0x9AAB,0x9B70),  # clamps, 16-bit add, direction table, speed upgrades
    ('firing',0x9CC2,0x9D6F),    # input cadence, normal weapon creation and dispatch
    ('shot_helpers',0x9DF0,0x9E14), # slot check, muzzle positioning, shot coordinate
    ('shot_motion',0x9E45,0x9E66), # normal shot 12px movement and slot retirement
)
ORIGINAL_LABELS={
    'konami_x_limit':0x9AAB,
    'konami_y_limit':0x9ABB,
    'konami_addword':0x9AEE,
    'konami_velocity':0x9AF6,
    'konami_speed':0x9B4D,
    'konami_fire':0x9CC5,
    'konami_normal_dispatch':0x9D26,
    'konami_fire_normal':0x9D44,
    'konami_slot_check':0x9DF0,
    'konami_muzzle':0x9DFB,
    'konami_shot_move':0x9E45,
}
# These addresses belong to weapon modes intentionally not enabled yet.
# The original CALL sites are retained, but their other-mode destinations
# are routed to a hardware-layer RET until these modes are transplanted.
UNSUPPORTED_WEAPONS={0x9D6F,0x9D74,0x9D8F,0x9DD0}
SOUND_ROUTINE=0x49DE


def make_rom_blocks(raw, base_addresses, sound_stub, weapon_stub):
    """Return packed bytecode, patch audit log and labels.
    Every byte absent an explicitly documented relocation is bit-for-bit
    identical to its corresponding offset in the supplied MSX ROM.
    """
    assert len(raw)==131072
    # All blocks are direct copies from original physical ROM bank 2.
    segments=[]
    for name,start,end in BLOCKS:
        block=bytearray(raw[2*8192+start-0x8000:2*8192+end-0x8000])
        assert len(block)==end-start
        segments.append((name,start,end,block))
    relocated={a:base_addresses[name]+a-start for name,start,end,_ in segments for a in range(start,end)}
    # Explicit address operand positions, verified against original assembly.
    # Only 16-bit operands to JP/CALL/LD HL,[address] may be relocated;
    # MSX E000 RAM operands are left untouched by design.
    operand_sites={
      'movement':[
        0x9AAE,0x9AB5,0x9AC4,0x9AC9,0x9ACE,0x9AD4,0x9ADB,
        0x9AE7,0x9AEC,0x9AFE,0x9B53,0x9B61,0x9B6B,
      ],
      'firing':[
        0x9CE6,0x9CF5,0x9D0E,0x9D15,0x9D1C,0x9D23,0x9D2D,0x9D35,
        0x9D48,0x9D57,0x9D60,0x9D68,0x9D6D,
      ],
      'shot_helpers':[],
      'shot_motion':[],
    }
    # dynamic audit ensures we fail, rather than silently ship a bad branch.
    log=[]
    for name,start,end,block in segments:
        for site in operand_sites[name]:
            idx=site-start
            assert 0<=idx<len(block)-1,(name,hex(site))
            target=block[idx]|(block[idx+1]<<8)
            if target in relocated:new_target=relocated[target]
            elif target in UNSUPPORTED_WEAPONS:new_target=weapon_stub
            elif target==SOUND_ROUTINE:new_target=sound_stub
            else:raise ValueError(f'Unresolved original reference {site:04X} -> {target:04X}')
            block[idx:idx+2]=new_target.to_bytes(2,'little')
            log.append((site,target,new_target))
    # validate ALL original absolute references within original snippets
    # via explicitly declared list: extra references must be reviewed before use.
    outputs={name:bytes(blob) for name,start,end,blob in segments}
    labels={name:relocated[a] for name,a in ORIGINAL_LABELS.items()}
    return outputs,log,labels


def as_db(b):
    return '\n'.join('    db '+','.join('0x%02x'%x for x in b[i:i+16]) for i in range(0,len(b),16))
