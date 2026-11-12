"""Stage 8's hatches with lighter dark colours (made by
tools/pool/art/hatch_light_make.py, whose docstring says how)."""
BLOCKS = {
    (0, 0x64): bytes.fromhex('dd0000dddd00dddddd0000dddd00dddddd0000dddd00dddddd0000dddd00dddd000000dddddddddd000000000000000000dddddddddddddd0000000000000000'),
    (0, 0x66): bytes.fromhex('0fdddd0fdd0fdddd0e0e0e0e0e0e0e0e0000000000000000000000dd00dddddd000000dd00dddddd0000000000000000dd0000dddd00dddddd0000dddd00dddd'),
    (0, 0x67): bytes.fromhex('0f0f0fdddd0f0f0f0f0f0f0f0f0f0f0f0000000000000000050505050f0f0f0f050505050f0f0f0f000000000000000000000707070007070000070707000707'),
    (0, 0x69): bytes.fromhex('dddd00dddd0000dddddd00dddd0000dddddd00dddd0000dddddd00dddd0000dddddddddddd0000000000000000000000dddddddddddddd000000000000000000'),
    (0, 0x6B): bytes.fromhex('dddd0fdd0fdddd0f0e0e0e0e0e0e0e0e0000000000000000dddddd00dd000000dddddd00dd0000000000000000000000dddd00dddd0000dddddd00dddd0000dd'),
    (0, 0x6C): bytes.fromhex('0f0f0fdddd0f0f0f0f0f0f0f0f0f0f0f00000000000000000f0f0f0f050505050f0f0f0f05050505000000000000000007070007070700000707000707070000'),
}
PALETTE = {0xDD: (76, 1)}
