; The power-up bar (third 2, tiles 15-42, and 0C, the last cell of a blank
; box once an item is taken for good: Konami's meter on row 22) gets its
; own two-colour design instead of a colour fit.  A plain box is white
; letters on blue (its black gaps and top row go blue too, since a cell has
; only two colours); a lit box is its fill in yellow on black.  Recognised
; by tile number and by the bar's fill colour in the tile's middle row (MSX
; dark blue for plain, dark yellow for lit), so other tiles with those
; numbers (text written in rows 16-19) keep their fit.
; D = third, E = tile; rewrites cv_out from cv_pat / cv_col.  Preserves DE.
BAR_PLAIN equ 0x40 | 1 << 3 | 7         ; bright, white ink on blue paper
BAR_LIT equ 0x40 | 0 << 3 | 6           ; bright, yellow ink on black paper
bs_mode:    db 0                        ; 0 plain, 1 lit
bs_gap:     db 0                        ; plain: letter mask (FE in a box's last cell)
bar_style:
    ld a,d
    cp 2
    ret nz
    ld a,e
    cp 0x0c                     ; a blank box's last cell (an item taken for good)
    jr z,.colours
    cp 0x15
    ret c
    cp 0x43
    ret nc
.colours:
    ld a,(cv_col+4)
    ld b,a
    and 0xf0
    cp 0x40
    jr z,.plain
    ld a,b
    and 15
    cp 4
    jr z,.plain
    ld a,b
    and 0xf0
    cp 0xa0
    jr z,.lit
    ld a,b
    and 15
    cp 0x0a
    ret nz
.lit:
    ld a,1
    ld (bs_mode),a
    ld a,BAR_LIT
    jr .rows
.plain:
    xor a
    ld (bs_mode),a
    ld b,0xff
    ld a,e
    cp 0x0c
    jr z,.gap
    cp 0x29
    jr nc,.nogap
    sub 0x15
    and 3
    cp 3
    jr nz,.nogap
.gap:
    ld b,0xfe                   ; the gap between boxes stays blue
.nogap:
    ld a,b
    ld (bs_gap),a
    ld a,BAR_PLAIN
.rows:
    ld (cv_out+8),a
    push de
    push ix
    ld ix,cv_pat
    ld b,8
    ld e,0                      ; row
.row:
    ld c,(ix+0)                 ; pattern
    ld a,(ix+8)                 ; colours
    ld h,a
    ld d,0                      ; fill: pixels of a colour other than 0 / 1
    rrca
    rrca
    rrca
    rrca
    and 15
    cp 2
    jr c,.nofg
    ld d,c
.nofg:
    ld a,h
    and 15
    cp 2
    jr c,.nobg
    ld a,c
    cpl
    or d
    ld d,a
.nobg:
    ld a,(bs_mode)
    or a
    jr nz,.litrow
    ld a,e                      ; plain: the letters, rows 2-6
    sub 2
    cp 5
    ld a,0
    jr nc,.put
    ld a,(bs_gap)
    ld l,a
    ld a,d
    cpl
    and l
    jr .put
.litrow:
    ld a,e                      ; lit: the fill below the top row
    or a
    ld a,0
    jr z,.put
    ld a,d
.put:
    ld (ix+16),a                ; cv_out
    inc ix
    inc e
    djnz .row
    pop ix
    pop de
    ret
    assert cv_col == cv_pat + 8 && cv_out == cv_pat + 16
