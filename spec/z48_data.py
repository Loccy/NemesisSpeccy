"""The 48K demo's data (stage 1 only), made from the 128K build's converted
sets (native_sets.py) and the ROM:

  tiles48.bin    stage 1's complete tile set in the tile set's layout, with
                 Konami's font (the screen before each life, game over) in
                 thirds 0 and 1, where stage 1 has nothing: those two loads
                 then have nothing to do
  spr48.bin      stage 1's 64 sprite patterns (no load changes them)
  z48_data.asm   the Big Core's characters and stage 1's own for the same
                 characters (to put back), each packed with ZX0, and their
                 mask (packed too); stage
                 1's star attributes; Konami's map for stage 1 (its script,
                 with the pieces it uses renumbered, and those pieces)
"""
import os, sys, pickle
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import native_sets, native_pack

def main():
    N = int(os.environ.get('Z48_STAGE', '1'))
    cache = os.path.join(HERE, 'z48_sets.pkl')
    ev = pickle.load(open(cache, 'rb')) if os.path.isfile(cache) else {}
    if ('stage', N) not in ev:
        ev = native_sets.events()
        pickle.dump({k: v for k, v in ev.items() if k[0] in ('stage', 'prestage', 'gameover', 'bigcore') and k[1] <= 8},
                    open(cache, 'wb'))
    st = ev[('stage', N)]
    tiles = dict(st['tiles'])
    font = {}                   # the font's characters that clash with the stage's (a patch)
    for k, v in ev[('prestage', N)]['tiles'].items():
        if k >= 512: assert tiles[k] == v
        elif tiles[k] == v: pass
        elif tiles[k][:8] == bytes(8) and (tiles[k] == bytes(9) or N == 1): tiles[k] = v
        else: font[k] = v
    for k, v in ev[('gameover', N)]['tiles'].items():
        assert font.get(k, tiles[k]) == v, 'game over differs from the merged set at %d:%02X' % (k >> 8, k & 255)
    # Tiles stored once (13 November): an index of two bytes a character
    # (for third t, page IDX48 + 2t the tile's number within its group,
    # page IDX48 + 2t + 1 its group's attribute page), then two groups of
    # 256 tiles, each nine pages: the attributes, then rows 0 to 7.  In both
    # groups numbers 0-7 are kept for tiles with no pixels (the renderer
    # writes zeros for them), 8-13 of group 0 are the star tiles (F6 and F7
    # of each third, whose row 0 blink_native rewrites).
    IDX48, TG48, KBLANK, STAR0 = 0xDB, 0xE1, 8, 8
    store = {}; nxt = [STAR0 + 6, KBLANK]; nblank = [0]; star_t = {}
    def tid(v):
        v = bytes(v)
        if v in store: return store[v]
        if v[:8] == bytes(8):
            assert nblank[0] < KBLANK, 'more than %d tiles with no pixels' % KBLANK
            t = (0, nblank[0]); nblank[0] += 1
        elif nxt[0] < 256: t = (0, nxt[0]); nxt[0] += 1
        else:
            assert nxt[1] < 256, 'more than 504 tiles'
            t = (1, nxt[1]); nxt[1] += 1
        store[v] = t; return t
    def tidx(k, v):
        if (k & 255) in (0xF6, 0xF7):
            th, c = divmod(k, 256); t = (0, STAR0 + 2 * th + (c - 0xF6)); star_t[t] = bytes(v); return t
        return tid(v)
    idx = {k: tidx(k, v) for k, v in tiles.items()}
    tab = bytearray(256 * 24)
    for k, (g, lo) in idx.items():
        th, c = divmod(k, 256)
        tab[(2 * th) * 256 + c] = lo; tab[(2 * th + 1) * 256 + c] = TG48 + 9 * g
    def put(t, v):
        g, lo = t
        base = (6 + 9 * g) * 256
        tab[base + lo] = v[8]
        for r in range(8): tab[base + (1 + r) * 256 + lo] = v[r]
    for v, t in store.items(): put(t, v)
    for t, v in star_t.items(): put(t, v)
    spr = b''.join(st['spr'][i] for i in range(64))
    assert len(spr) == 2048
    open(os.path.join(HERE, 'spr48.bin'), 'wb').write(spr)
    bc = ev.get(('bigcore', N), {'spr': {}, 'tiles': {}})   # (stages 7 and 8: no Big Core)
    assert not bc['spr'], 'the Big Core changes sprite patterns'
    # the Big Core's characters and stage 1's for the same ones (to put
    # back): one mask (bit k: character third * 256 + char), then for each
    # set the marked characters' bytes, row by row (row 0 of every one, then
    # row 1...; the ninth row the attributes), each packed with ZX0
    # a patch: the marked characters' index entries (their tiles are in the
    # store already): one mask (bit k: character third * 256 + char), then
    # the numbers within the group of every marked character, then their
    # groups' attribute pages, packed with ZX0
    def packset(ks):
        mask = bytearray(96)
        for k in ks: mask[k >> 3] |= 1 << (k & 7)
        def pk(d):
            ts = [tidx(k, d[k]) for k in ks]
            return native_pack.zx0(bytes([lo for g, lo in ts] + [TG48 + 9 * g for g, lo in ts]))
        return native_pack.zx0(bytes(mask)), pk
    kb = sorted(bc['tiles']); kf = sorted(font); kr = sorted(set(kb) | set(kf))
    assert not any((k & 255) in (0xF6, 0xF7) for k in kr), 'a patch changes a star tile'
    zmb, pk = packset(kb); zb = pk(bc['tiles']) if kb else bytes(1)
    zmr, pk = packset(kr); zs = pk(tiles)
    blobs = (('z48_mask_z', zmb, 'the Big Core\'s mask'), ('z48_bc_data', zb, 'the Big Core\'s'),
             ('z48_s1_data', zs, 'stage %d\'s own for them' % N))
    if kf: blobs += (('z48_rmask_z', zmr, 'the mask of all patched'),)
    if kf:
        zmf, pk = packset(kf); zf = pk(font)
        blobs += (('z48_fmask_z', zmf, 'the font\'s mask'), ('z48_ft_data', zf, 'the font\'s'))
    for v, t in store.items(): put(t, v)            # (the patches' tiles too)
    open(os.path.join(HERE, 'tiles48.bin'), 'wb').write(bytes(tab))
    print('tiles: %d stored (%d in group 1), %d with no pixels' % (len(store) + len(star_t), max(0, nxt[1] - KBLANK), nblank[0]))
    # the tile numbers no tile uses: in each of a group's nine pages, from
    # the first free number to 255, nothing is read (build48.py: room for the
    # stage's own tables, z48_ovhigh.asm)
    tf = []
    for g, first in ((0, nxt[0]), (1, nxt[1])):
        if first < 256:
            for p in range(9): tf.append('%04X-%04X' % ((TG48 + 9 * g + p) * 256 + first, (TG48 + 9 * g + p) * 256 + 256))
    open(os.path.join(HERE, 'z48_tilefree.txt'), 'w').write('\n'.join(tf) + '\n')
    if os.environ.get('Z48_NOBC') == '1': blobs = ()      # (the preview: no Big Core characters)
    ks = kr; zm = zmr
    pb = bytes(2 * len(kr))
    stars = native_pack.star_attrs(N)
    # the map: stage 1's script (11:97F8-99A7), its pieces renumbered
    rom = open(os.path.join(HERE, '..', 'nem.rom'), 'rb').read()
    b11 = rom[11 * 8192:13 * 8192]     # (banks 11 and 12: stage 8's script runs on into 12)
    gw = [b11[0x17DE + 2 * i] | b11[0x17DF + 2 * i] << 8 for i in range(13)]
    s0 = gw[N]; s1 = min(x for x in gw + [0xA7B8] if x > s0)
    script = b11[s0 - 0x8000:s1 - 0x8000]
    used = []
    for n in script:
        if n not in used: used.append(n)
    new = {n: i for i, n in enumerate(used)}
    # (stages 5, 9, 10 and 12 take their pieces from 11:8FF0, the others
    # from 11:8000: Konami's 0:46F2-4708; 14 November)
    pbase = 0x0FF0 if N in (5, 9, 10, 12) else 0
    pieces = b''.join(b11[pbase + n * 16:pbase + n * 16 + 16] for n in used)
    # every piece where build48.py's layout puts it (z48_place_*: the 48K's
    # free areas), else one after another (the coverage build)
    open(os.path.join(HERE, 'z48_stage.asm'), 'w').write('\n'.join(['; generated by z48_data.py', '',
           'STAGE48 equ %d' % N,
           'z48_n equ %d                  ; the characters the Big Core changes' % len(kb),
           'z48_rnum equ %d                 ; the characters the patches change' % len(kr),
           'z48_fn equ %d                 ; the font\'s characters that clash with the stage\'s' % len(kf)]) + '\n')
    out = ['; generated by z48_data.py', '']
    sizes = []
    def piece(name, lines, n, note=''):
        out.extend(['    ifdef Z48_PLACED', '    z48_place_%s' % name, '    endif', '%s:%s' % (name, note)] + lines)
        sizes.append('%s %d' % (name, n))
    piece('z48_star_attr', ['    db ' + ','.join('0x%02X' % x for x in stars)], len(stars))
    piece('map48_tword', ['    dw map48_script'], 2,
          "                    ; Konami's tabla_de_guiones, its entry for this stage alone")
    out.append('map48_table equ map48_tword-%d' % (2 * N))
    piece('map48_script', ['    db ' + ','.join('0x%02X' % new[n] for n in script[i:i + 18]) for i in range(0, len(script), 18)],
          len(script), '                   ; 11:%04X, %d different pieces' % (s0, len(used)))
    piece('map48_pieces', ['    db ' + ','.join('0x%02X' % x for x in pieces[i:i + 16]) for i in range(0, len(pieces), 16)],
          len(pieces))
    for name, zz, what in blobs:
        piece(name, ['    db ' + ','.join('0x%02X' % x for x in zz[i:i + 16]) for i in range(0, len(zz), 16)],
              len(zz), '                    ; %s, %d packed' % (what, len(zz)))
    if not kf: out.append('z48_rmask_z equ z48_mask_z')
    if not kf: out += ['z48_fmask_z equ 0', 'z48_ft_data equ 0']
    out.append('map48_end:')
    # the shared layout: the stage's header, Konami's table of map scripts and
    # the map's pieces at fixed places at the start of the stage's block
    # (z48_ovhead.asm: OV48; then the jump slots, z48_slots.asm), the rest
    # after the stage's own code (z48_data_sh.asm)
    hdr = ['; generated by z48_data.py: the start of stage %d\'s block (the shared layout)' % N,
           '    org OV48', 'z48_hdr:',
           '    db %d                       ; +0: the stage' % N,
           '    dw z48_mask_z,z48_bc_data,z48_n     ; +1: the Big Core\'s patch',
           '    dw z48_rmask_z,z48_s1_data,z48_rnum ; +7: the stage\'s own characters back',
           '    dw z48_fmask_z,z48_ft_data,z48_fn   ; +13: the font\'s patch (none: 0)',
           '    dw z48_star_attr               ; +19',
           'map48_table:                       ; +21: Konami\'s tabla_de_guiones: every stage is this one',
           '    dw ' + ','.join(['0'] + ['map48_script'] * 12),
           '    assert $ == OV48 + 47',
           '    db ' + ','.join('0x%02X' % (ord(c) - 0x20 if c != ' ' else 0) for c in ('START' if N == 1 else 'WIND ')) + '   ; +47: game over\'s third line, "RE....  R" (z48_go_text)',
           ('    jp z48_logo                 ; +52: the title\'s logo (z48_title calls it)' if N == 1 else '    ret                         ; +52: no logo (z48_title calls it)\n    db 0,0'),
           '    include "z48_slots.asm"',
           '    include "z48_tables.asm"',
           'map48_pieces:',
          ] + ['    db ' + ','.join('0x%02X' % x for x in pieces[i:i + 16]) for i in range(0, len(pieces), 16)] + ['z48_ov_code:']
    open(os.path.join(HERE, 'z48_ovhead.asm'), 'w').write('\n'.join(hdr) + '\n')
    sh = ['; generated by z48_data.py: stage %d\'s data after its own code (the shared layout);' % N,
          '; a piece build48.py places in the block\'s high areas (z48_hplace.asm) goes there', '',
          '    include "z48_hplace.asm"']
    def hp(name, lines):            # (placed: there, and back; else here)
        return (['    ifdef HPLACE_%s' % name, 'z48_back_%s = $' % name, '    org HPLACE_%s' % name, '    endif']
                + lines + ['    ifdef HPLACE_%s' % name, '    org z48_back_%s' % name, '    endif'])
    sh += hp('z48_star_attr', ['z48_star_attr:', '    db ' + ','.join('0x%02X' % x for x in stars)])
    sh += hp('map48_script', ['map48_script:'] + ['    db ' + ','.join('0x%02X' % new[n] for n in script[i:i + 18]) for i in range(0, len(script), 18)])
    for name, zz, what in blobs:
        sh += hp(name, ['%s:                    ; %s, %d packed' % (name, what, len(zz))] + ['    db ' + ','.join('0x%02X' % x for x in zz[i:i + 16]) for i in range(0, len(zz), 16)])
    # Stage 6's boss reads its pieces' sizes and pictures from MSX bank 10
    # (A:AAA6-AF28: two tables of addresses, then the pictures), which the
    # 48K does not otherwise carry: a copy here, its addresses moved with it
    # (gen.py points 2:82CC, 82D1, 831B and 834F at it; 13 November)
    if N == 6:
        b10 = rom[10 * 8192:11 * 8192]; LO, HI = 0xAAA6, 0xAF29     # (to the end of the last picture its tables name, A:AF11, 7 by 3)
        lines = []
        for a in range(LO, 0xAB00, 2):
            v = b10[a - 0xA000] | b10[a - 0xA000 + 1] << 8
            lines.append('    dw ' + ('z48_b10+%d' % (v - LO) if LO <= v < HI else '0x%04X' % v))
        body = b10[0xAB00 - 0xA000:HI - 0xA000]
        lines += ['    db ' + ','.join('0x%02X' % x for x in body[i:i + 16]) for i in range(0, len(body), 16)]
        sh += hp('z48_b10', ['z48_b10:                    ; bank 10 A:AAA6-AF28, stage 6\'s boss'] + lines)
        sizes.append('z48_b10 %d' % (HI - LO))
    else:
        sh += ['z48_b10 equ z48_trap']
    if not kf: sh += ['z48_rmask_z equ z48_mask_z', 'z48_fmask_z equ 0', 'z48_ft_data equ 0']
    if N == 1:                  # the title's logo (z48_logo.py): 5 rows of 32 block characters
        import z48_logo
        ld = z48_logo.data()
        sh += hp('z48_logo', LOGO_ASM + ['    db ' + ','.join('0x%02X' % x for x in ld[i:i + 16]) for i in range(0, len(ld), 16)])
    sh += ['z48_n equ %d' % len(kb), 'z48_rnum equ %d' % len(kr), 'z48_fn equ %d' % len(kf), 'z48_data_end:']
    open(os.path.join(HERE, 'z48_data_sh.asm'), 'w').write('\n'.join(sh) + '\n')
    open(os.path.join(HERE, 'z48_sizes.txt'), 'w').write('\n'.join(sizes) + '\n')
    open(os.path.join(HERE, 'z48_data.asm'), 'w').write('\n'.join(out) + '\n')
    print('z48 data: stage %d: font %d, Big Core %d + own %d + mask %d packed, map %d (%d pieces), a set unpacks to %d' % (N, len(zf) if kf else 0,
        len(zb), len(zs), len(zm), len(script) + len(pieces) + 26, len(used), len(pb)))

LOGO_ASM = ['z48_logo:                   ; screen rows 2-6 (third 0: cell n at 4040 + n)', '    ld hl,z48_logo_data', '    ld de,0x4040', '    ld c,160', '.cell:', '    ld a,e                      ; an even cell the high nibble, an odd the low', '    rra', '    ld a,(hl)', '    jr c,.lo', '    rrca', '    rrca', '    rrca', '    rrca', '    jr .got', '.lo:', '    inc hl', '.got:', '    and 0x0F', '    jr z,.next', '    push hl', '    push de', '    ld b,a', '    rrca                        ; the top half: bits 3-2', '    rrca', '    call .half', '    ld a,b                      ; the bottom half: bits 1-0', '    call .half', '    pop de', '    push de', "    ld a,e                      ; the attribute, by the cell's row (e & 0xE0)", '    and 0xE0', '    cp 0x60', '    jr z,.dark', '    cp 0xA0', '    jr z,.dark', '    ld l,0x0C                   ; row 0: white over cyan when the ink is the top half', '    cp 0x40', '    jr z,.white', '    ld l,0x03                   ; row 4: white under cyan when it is the bottom half', '    cp 0xC0', '    jr nz,.cyan', '.white:', '    ld a,b', '    cp l', '    ld a,0x6F                   ; bright, cyan paper, white ink', '    jr z,.put', '.cyan:', '    ld a,0x45                   ; bright, black paper, cyan ink', '    jr .put', '.dark:', '    ld a,0x05                   ; cyan ink, not bright', '.put:', '    ld l,a', '    ld a,d', '    add a,0x18', '    ld d,a', '    ld a,l', '    ld (de),a', '    pop de', '    pop hl', '.next:', '    inc e', '    dec c', '    jr nz,.cell', '    ret', '.half:                          ; 4 pixel lines of the two blocks in bits 1-0 of A', '    and 3', '    ld hl,.tab', '    add a,l', '    ld l,a', '    jr nc,.h1', '    inc h', '.h1:', '    ld a,(hl)', '    ld (de),a', '    inc d', '    ld (de),a', '    inc d', '    ld (de),a', '    inc d', '    ld (de),a', '    inc d', '    ret', '.tab:', '    db 0x00,0x0F,0xF0,0xFF', 'z48_logo_data:']


if __name__ == '__main__':
    main()

