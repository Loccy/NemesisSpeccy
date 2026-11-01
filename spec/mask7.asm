; Sprites over terrain, drawn with a mask (build option SPR_MASK; page 7, so
; it is reached while the renderer has page 7 in for the tiles and sprite
; patterns).
;
; draw_sprite16 calls mask_check once the sprite's cells and screen address
; are known (DE = screen address of its first line, HL = its pattern).  If
; none of the cells under it holds a terrain tile (blank and star tiles do
; not count) mask_check returns and the sprite is ORed in as before.
; Otherwise it drops that return, draws the sprite here and goes on to
; draw_sprite16's colouring: each line becomes
;   screen = (screen AND NOT halo) OR sprite
; where the halo is the sprite's pixels grown by one pixel in each direction
; (within the 16 lines and the bytes the sprite covers), so a black outline
; separates the sprite from the terrain behind it.

mask_check:
    push hl
    push de
    ld a,(sp_cy)                ; name_shadow + cy * 32 + cx
    rrca
    rrca
    rrca
    ld b,a
    and 0xe0
    ld l,a
    ld a,(sp_cx)
    or l
    ld l,a
    ld a,b
    and 0x1f
    add a,name_shadow>>8
    ld h,a
    ld a,(sp_rows)
    ld c,a
.row:
    ld a,(sp_cols)
    ld b,a
    push hl
.col:
    ld a,(hl)
    or a
    jr z,.blank
    cp 0xf6
    jr c,.terrain
    cp 0xf8
    jr nc,.terrain
.blank:                         ; nothing, or a star
    inc l
    djnz .col
    pop hl
    ld de,32
    add hl,de
    dec c
    jr nz,.row
    pop de
    pop hl
    ret
.terrain:
    pop hl
    pop de
    pop hl
    inc sp                      ; not back to draw_sprite16's OR loop
    inc sp

; The sprite shifted into place, three bytes a line, in mk_pix lines 1-16
; (lines 0 and 17 stay zero), then the halo and the drawing line by line.
    push de
    ld a,(sp_x)
    and 7
    ld e,a                      ; shift entry: .p_end - 5 * s
    add a,a
    add a,a
    add a,e
    ld e,a
    ld d,0
    push hl
    ld hl,.p_end
    or a
    sbc hl,de
    ld (.p_jump+1),hl
    pop hl
    ld de,mk_pix+3
    ld a,16
    ld (mk_cnt),a
.p_row:
    ld b,(hl)
    set 4,l
    ld c,(hl)
    res 4,l
    inc l
    xor a
.p_jump:
    jp .p_end
    rept 7
    srl b
    rr c
    rra
    endr
.p_end:
    ex de,hl
    ld (hl),b
    inc l
    ld (hl),c
    inc l
    ld (hl),a
    inc l
    ex de,hl
    ld a,(mk_cnt)
    dec a
    ld (mk_cnt),a
    jr nz,.p_row
    pop de

    ld ix,mk_pix+3
    ld a,16
    ld (mk_cnt),a
.m_row:
    push de
    ld a,(ix-3)                 ; m = this line OR the lines above and below
    or (ix+0)
    or (ix+3)
    ld b,a
    ld a,(ix-2)
    or (ix+1)
    or (ix+4)
    ld c,a
    ld a,(ix-1)
    or (ix+2)
    or (ix+5)
    ld h,a
    or b
    or c
    jr z,.m_skip                ; nothing on this line or next to it
    ld a,c                      ; byte 2: m2 | m2<<1 | m2>>1 | m1<<7
    rrca
    ld a,h
    rra
    or h
    ld l,a
    ld a,h
    add a,a
    or l
    cpl
    ld l,a
    ld a,h                      ; byte 1: m1 | m1<<1 | m2>>7 | m1>>1 | m0<<7
    rlca
    ld a,c
    rla
    or c
    ld e,a
    ld a,b
    rrca
    ld a,c
    rra
    or e
    cpl
    ld e,a
    ld a,c                      ; byte 0: m0 | m0<<1 | m1>>7 | m0>>1
    rlca
    ld a,b
    rla
    or b
    ld d,a
    ld a,b
    srl a
    or d
    cpl
    ld b,a
    ld c,e
    pop de
    push de
    ld a,(de)
    and b
    or (ix+0)
    ld (de),a
    inc e
    ld a,(de)
    and c
    or (ix+1)
    ld (de),a
    ld a,(sp_cols)
    cp 3
    jr nz,.m_skip               ; on a cell boundary: two bytes
    inc e
    ld a,(de)
    and l
    or (ix+2)
    ld (de),a
.m_skip:
    pop de
    inc d                       ; next screen line
    ld a,d
    and 7
    jr nz,.m_ok
    ld a,e
    add a,32
    ld e,a
    jr c,.m_ok
    ld a,d
    sub 8
    ld d,a
.m_ok:
    inc ix
    inc ix
    inc ix
    ld a,(mk_cnt)
    dec a
    ld (mk_cnt),a
    jp nz,.m_row
    jp draw_sprite16.attrs

mk_cnt:     db 0
mk_pix:     ds 18 * 3           ; lines 0 and 17 are always zero
