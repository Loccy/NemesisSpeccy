; Runs with page 7 mapped (from full_cmp_d), so it lives there, F600 on.

; Can moves between tiles 0, F6 and F7 be left to draw_stars?  All three
; converted in every third (converted here if waiting: F7 is never drawn now
; that F7 stars are sky, so nothing else would), with rows 1-7 equal.  Page
; 7 mapped.
star_check:
    ld a,(star_stale)
    or a
    ret z                       ; no tile has changed since the last check
    xor a
    ld (star_stale),a
    ld (star_ok),a
    ld a,(star_off)
    or a
    ret nz
    ld d,0                      ; third
.third:
    ld e,0
    call .conv
    ld e,0xf6
    call .conv
    ld e,0xf7
    call .conv
    ld a,d
    add a,a
    add a,a
    add a,a
    add a,d
    add a,TILE_PAGES
    ld h,a
    ld c,7
.rows:
    inc h
    ld l,0
    ld a,(hl)
    ld l,0xf6
    cp (hl)
    ret nz
    inc l
    cp (hl)
    ret nz
    dec c
    jr nz,.rows
    inc d
    ld a,d
    cp 3
    jr nz,.third
    xor a
    ld (star_stale),a           ; (the conversions above set it)
    inc a
    ld (star_ok),a
    ret
.conv:                          ; tile E of third D converted if waiting
    ld a,d
    add a,a
    add a,a
    add a,a
    add a,d
    add a,TILE_PAGES+8
    ld h,a
    ld l,e
    bit 7,(hl)
    ret z
    push de
    push hl
    call ensure_tile
    pop hl
    pop de
    res 7,(hl)
    ret

