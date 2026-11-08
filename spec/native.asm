; The native build's graphics (claude/native-128k-plan.md): Konami's
; graphics loads become loads of sets converted when the game is built
; (native_sets.py, packed by native_pack.py into native_data.asm), and
; Konami's screen dissolve works on the converted tiles.  Fixed memory, after
; Konami's bank 0 (whose loaders the native build leaves out).
;
; The packed pieces are in the switched banks, as is the tile set (bank 7,
; DB00-F5FF), and only one bank can be at C000 at a time; ZX0 reads its input
; in order, so the unpacker reads it through nl_buf (256 bytes, refilled from
; the source bank) and writes straight into the destination bank.  A patch is
; unpacked into page D's work area (E800) and copied in a character at a time.

NL_WORK equ 0xE800              ; page D: a patch, unpacked

nl_srcpg:   db 0                ; the source's page
nl_src:     dw 0                ; the next source byte to copy into nl_buf
nl_dstpg:   db 0                ; the destination's page
nl_w:       dw 0                ; scatter: the next byte of the patch
nl_m:       db 0                ; scatter: the mask byte's index
nl_mb:      db 0                ; scatter: the mask byte, turning
nl_count:   db 0                ; loads and dissolve chunks so far (for the checks)

; ---- the event entry points (Konami's sites, reloc/gen.py) -------------------

; 0:422A, carga_los_graficos_de_la_fase: the stage's set, then E100 = 1 and
; the mapper put back as Konami's routine leaves them.
nl_stage:
    call nl_save
    ld a,(0xE061+KRAM)
    call nl_full
    pop ix
    pop af
    pop bc
    pop de
    pop hl
    ld a,1
    ld (0xE100+KRAM),a
    jp m0_4299                  ; devuelve_el_reparto_de_siempre

nl_bigcore:                     ; 0:4A8A (the Big Core's characters)
    call nl_save
    ld a,(0xE061+KRAM)
    dec a
    ld l,a
    add a,a
    add a,l
    ld l,a
    ld h,0
    ld de,nl_bigcore_tab
    add hl,de
    jr nl_desc
nl_title:                       ; 0:5300
    call nl_save
    ld hl,nl_title_d
    jr nl_desc
nl_prestage:                    ; 0:53D4
    call nl_save
    ld hl,nl_prestage_d
    jr nl_desc
nl_gameover:                    ; 0:54DD
    call nl_save
    ld hl,nl_gameover_d
    jr nl_desc
nl_marcador:                    ; 0:4C2E
    call nl_save
    ld hl,nl_marcador_d
    jr nl_desc
nl_ending:                      ; 0:4B04
    call nl_save
    ld hl,nl_ending_d
nl_desc:                        ; HL = a patch's descriptor (page, address)
    call nl_patch
    jp nl_restore

nl_save:                        ; every register kept for Konami
    ex (sp),hl
    push de
    push bc
    push af
    push ix
    push hl
    ret
nl_restore:                     ; (jumped to, with nl_save's pushes on the stack)
    pop ix
    pop af
    pop bc
    pop de
    pop hl
    ret

; ---- loading -------------------------------------------------------------------

; A = stage 1-12: its complete set.
nl_full:
    dec a
    ld l,a
    add a,a                     ; 15 bytes an entry
    add a,a
    add a,a
    add a,a
    sub l
    ld l,a
    ld h,0
    ld de,nl_stage_tab
    add hl,de
    push hl
    ld de,0xDB00                ; the tiles
    call nl_unpack7
    pop hl
    inc hl
    inc hl
    inc hl
    push hl
    ld a,(hl)                   ; a patch over them (stages 10-12)
    inc a
    call nz,nl_patch
    ld hl,nl_spr_common         ; sprite patterns 0-39
    ld de,0xF800
    call nl_unpack7
    pop hl
    inc hl
    inc hl
    inc hl
    push hl
    ld de,0xFD00                ; 40-63
    call nl_unpack7
    pop hl
    inc hl
    inc hl
    inc hl
    ld de,star_attr
    ld bc,6
    ldir
    call bl_reset
    jr nl_done

; HL = a descriptor (page, address): unpack it into bank 7 at DE.
nl_unpack7:
    ld a,PAGE_7
    ld (nl_dstpg),a
    ld a,(hl)
    inc hl
    push af
    ld a,(hl)
    inc hl
    ld h,(hl)
    ld l,a
    pop af
    call nl_unpack
    jp unborrow_page

; HL = a patch's descriptor: unpack it into the work area, then copy its
; characters and sprite patterns into place.
nl_patch:
    ld a,PAGE_D
    ld (nl_dstpg),a
    ld a,(hl)
    inc hl
    push af
    ld a,(hl)
    inc hl
    ld h,(hl)
    ld l,a
    pop af
    ld de,NL_WORK
    call nl_unpack
    call nl_scatter
    call unborrow_page
nl_done:                        ; every cell redrawn at the end of the tick
    ld a,0xff
    ld (chg_n),a
    ld a,1
    ld (star_stale),a
    ld hl,nl_count
    inc (hl)
    ret

; The patch in the work area: a 96-byte mask (bit k = character
; third * 256 + char), the 9 bytes of each marked character, an 8-byte mask
; of sprite patterns, 32 bytes each.
nl_scatter:
    ld hl,NL_WORK+96
    ld (nl_w),hl
    xor a
    ld (nl_m),a
.mbyte:
    ld a,PAGE_D
    call out_page
    ld a,(nl_m)
    ld l,a
    ld h,NL_WORK>>8
    ld a,(hl)
    ld (nl_mb),a
    ld b,0                      ; bit
.bit:
    ld a,(nl_mb)
    rrca
    ld (nl_mb),a
    call c,.one
    inc b
    ld a,b
    cp 8
    jr nz,.bit
    ld hl,nl_m
    inc (hl)
    ld a,(hl)
    cp 96
    jr nz,.mbyte
    ; the sprite patterns
    ld a,PAGE_D
    call out_page
    ld hl,(nl_w)
    ld de,nl_buf+32             ; the mask, out of the way of the patterns' copies
    ld bc,8
    ldir
    ld (nl_w),hl
    ld de,0xF800                ; pattern 0
    ld hl,nl_buf+32
    ld c,8
.sbyte:
    ld b,8
    ld a,(hl)
.sbit:
    rrca
    call c,.spr
    push hl
    ld hl,32
    add hl,de
    ex de,hl
    pop hl
    djnz .sbit
    inc hl
    dec c
    jr nz,.sbyte
    ret
.spr:                           ; 32 bytes to DE in bank 7.  Keeps A, BC, DE, HL
    push af
    push bc
    push de
    push hl
    push de
    ld a,PAGE_D
    call out_page
    ld hl,(nl_w)
    ld de,nl_buf
    ld bc,32
    ldir
    ld (nl_w),hl
    ld a,PAGE_7
    call out_page
    pop de
    ld hl,nl_buf
    ld bc,32
    ldir
    pop hl
    pop de
    pop bc
    pop af
    ret
.one:                           ; character nl_m * 8 + B: its 9 bytes from the work area
    push bc
    ld hl,(nl_w)
    ld de,nl_buf
    ld bc,9
    ldir                        ; (page D is in)
    ld (nl_w),hl
    pop bc
    ld a,(nl_m)                 ; third = m >> 5, char = (m & 31) * 8 + bit
    ld c,a
    and 31
    add a,a
    add a,a
    add a,a
    add a,b
    ld e,a                      ; char
    ld a,c
    rlca
    rlca
    rlca
    and 3
    ld d,a
    add a,a
    add a,a
    add a,a
    add a,d
    add a,TILE_PAGES
    ld d,a                      ; row 0's page
    push bc
    ld a,PAGE_7
    call out_page
    ld hl,nl_buf
    ld b,9
.row:
    ld a,(hl)
    ld (de),a
    inc hl
    inc d
    djnz .row
    ld a,PAGE_D
    call out_page
    pop bc
    ret

; ---- the unpacker: ZX0 (Einar Saukas's format; tape/dzx0_standard.asm),
; its input read through nl_buf -----------------------------------------------

; A = the source's page, HL = its address, DE = the destination in page
; nl_dstpg (left mapped).
nl_unpack:
    ld (nl_srcpg),a
    ld (nl_src),hl
    push de
    call nl_fill
    pop de
    ld bc,0xffff
    push bc
    inc bc
    ld a,0x80
.literals:
    call .elias
    push af
.lit:
    call nl_get
    ld (de),a
    inc de
    dec bc
    ld a,b
    or c
    jr nz,.lit
    pop af
    add a,a
    jr c,.new_offset
    call .elias
.copy:
    ex (sp),hl
    push hl
    add hl,de
    ldir
    pop hl
    ex (sp),hl
    add a,a
    jr nc,.literals
.new_offset:
    pop bc
    ld c,0xfe
    call .elias_loop
    inc c
    ret z
    ld b,c
    push af
    call nl_get
    ld c,a
    pop af
    rr b
    rr c
    push bc
    ld bc,1
    call nc,.elias_backtrack
    inc bc
    jr .copy
.elias:
    inc c
.elias_loop:
    add a,a
    jr nz,.elias_skip
    call nl_get
    rla
.elias_skip:
    ret c
.elias_backtrack:
    add a,a
    rl c
    rl b
    jr .elias_loop

; A = the next input byte (HL in nl_buf).  Keeps the flags' carry, BC, DE.
nl_get:
    ld a,(hl)
    inc l
    ret nz
    push af
    call nl_fill
    pop af
    ret
; nl_buf = the next 256 source bytes; HL = nl_buf.  Keeps BC, DE.
nl_fill:
    push bc
    push de
    ld a,(nl_srcpg)
    call out_page
    ld hl,(nl_src)
    ld de,nl_buf
    ld bc,256
    ldir
    ld (nl_src),hl
    ld a,(nl_dstpg)
    call out_page
    pop de
    pop bc
    ld hl,nl_buf
    ret

; ---- Konami's screen dissolve on the converted tiles ----------------------------

; come_un_trozo (MSX 3:A765, patched to come here): one chunk of the
; dissolve, A = its first character, DE = the table (colours 0000/0800/1000,
; patterns 2000/2800/3000; the third from bits 11-12).  Konami's chunks: 64
; characters, 60 from 44 (the score and bar spared), 54 from C0 (F6-FF
; spared).  The colour pass turns every background black: a tile stored the
; other way round (nl_inv7/nl_inv8) goes back to ink on paper with its old
; paper as the ink; every tile's paper becomes black.  After its last chunk
; (Konami's pass does all of them in one tick, third 0's C0 last), the
; stage's patch (nl_dz7_d, nl_dz8_d) gives the tiles for which that rule is
; not what 1.0 shows (native_sets.dz_patch: 1.0's dz_tile, where the pixels
; are the MSX's foreground).  Each pattern pass ANDs
; the rows with Konami's mask for the pass (E1A2, turned three bits a row
; after the first pass, E1A0).  EA00, Konami's chunk buffer, is not kept:
; nothing reads it after the dissolve (the census).
dz_chunk:
    ld c,64
    cp 0x44
    jr nz,.c1
    ld c,60
.c1:
    cp 0xc0
    jr nz,.c2
    ld c,54
.c2:
    ld e,a                      ; first character
    ld a,d
    rrca
    rrca
    rrca
    and 3
    ld b,a                      ; third
    ld a,d
    cp 0x20
    push af
    ld a,PAGE_7
    call out_page
    ld a,b
    add a,a
    add a,a
    add a,a
    add a,b
    add a,TILE_PAGES
    ld d,a                      ; DE = row 0 of the first character
    pop af
    jr nc,.pat
    call dz_col
    ld a,b                      ; the colour pass's last chunk (third 0, C0-F5)?
    or a
    jr nz,.out
    ld a,e
    cp 0xF6
    jr nz,.out
    call unborrow_page          ; then 1.0's tiles where the rule is not
    ld a,(0xE061+KRAM)
    ld hl,nl_dz7_d
    cp 7
    jp z,nl_patch
    ld hl,nl_dz8_d
    cp 8
    jp z,nl_patch
    jp nl_done
.pat:
    call dz_pat
.out:
    call unborrow_page
    jp nl_done

; C characters from DE (row 0's address, page 7 in), B = third.
dz_col:
    ld a,(0xE061+KRAM)
    ld hl,nl_inv7
    cp 7
    jr z,.inv
    ld hl,nl_inv8
    cp 8
    jr z,.inv
    ld hl,0
.inv:
    ld (.ib+1),hl
.tile:
    push de
    ld hl,(.ib+1)               ; stored the other way round?
    ld a,h
    or l
    jr z,.plain
    ld a,b                      ; bit third * 256 + char
    add a,a
    add a,a
    add a,a
    add a,a
    add a,a
    ld l,a
    ld a,e
    rrca
    rrca
    rrca
    and 31
    add a,l
    ld l,a
    ld h,0
    push de
.ib:
    ld de,0
    add hl,de
    pop de
    ld a,e
    and 7
    inc a
    push bc
    ld b,a
    ld a,(hl)
.sh:
    rrca
    djnz .sh
    pop bc
    jr nc,.plain
    push de                     ; rows inverted, ink = the old paper
    ld l,8
.ir:
    ld a,(de)
    cpl
    ld (de),a
    inc d
    dec l
    jr nz,.ir
    ld a,(de)                   ; the attribute
    ld h,a
    rrca
    rrca
    rrca
    and 7
    ld l,a
    ld a,h
    and 0x40
    or l
    ld (de),a
    pop de
    jr .next
.plain:
    ld a,d
    add a,8
    ld h,a
    ld l,e
    ld a,(hl)
    and 0x47                    ; black paper
    ld (hl),a
.next:
    pop de
    inc e
    dec c
    jr nz,.tile
    ret

dz_pat:
    ld a,(0xE1A0+KRAM)
    ld h,a                      ; 0: the same mask every row
    ld a,(0xE1A2+KRAM)
    ld l,a
.tile:
    push de
    push bc
    ld a,l
    ld b,8
.row:
    ld c,a
    ex de,hl                    ; (keep the mask's turning in C)
    and (hl)
    ld (hl),a
    inc h
    ex de,hl
    ld a,h
    or a
    ld a,c
    jr z,.same
    rrca
    rrca
    rrca
.same:
    djnz .row
    pop bc
    pop de
    inc e
    dec c
    jr nz,.tile
    ret
