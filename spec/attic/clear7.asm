; Sparse terrain under sprites (build option SPR_CLEAR; page 7, in while the
; renderer draws).  Before any sprite is drawn, every cell under a visible
; sprite that holds terrain on black paper (not empty, not a star tile, not
; a dense tile stored inverted, which has coloured paper) is blanked, so the
; sprite is drawn there on black instead of recolouring the terrain's
; pixels.  The cells are restored from the map when the sprite moves on (the
; erase lists already cover them).  Done for all sprites first, so that one
; sprite's blanking cannot wipe another's pixels in a shared cell.
; Same visibility rules as draw_sprites.  Preserves BC, DE, HL.

sparse_pass:
    push bc
    push de
    push hl
    ld hl,SPR_ATTR
    ld b,32
.spr:
    ld a,(hl)
    cp 0xd0
    jr z,.done
    inc a                       ; one line below Y
    cp 177
    jr nc,.next
    ld (sc_y),a
    inc l
    inc l
    inc l
    ld a,(hl)                   ; colour
    dec l
    dec l
    ld c,a
    and 15
    jr z,.next1                 ; transparent
    ld a,(hl)                   ; X
    bit 7,c
    jr z,.x
    sub 32
    jr c,.next1
.x:
    cp 233
    jr nc,.next1
    push hl
    push bc
    call sparse_cells
    pop bc
    pop hl
.next1:
    dec l
.next:
    ld a,l
    add a,4
    ld l,a
    djnz .spr
.done:
    pop hl
    pop de
    pop bc
    ret

; A = X, sc_y = Y: the sprite's cells.
sparse_cells:
    ld c,a
    rrca
    rrca
    rrca
    and 31
    ld (sc_cx),a
    ld a,c
    and 7
    ld a,2
    jr z,.c2
    inc a
.c2:
    ld (sc_cols),a
    ld a,(sc_y)
    ld c,a
    and 7
    ld a,2
    jr z,.r2
    inc a
.r2:
    ld e,a                      ; rows
    ld a,c
    rrca
    rrca
    rrca
    and 31
    ld d,a                      ; row R
.row:
    ld a,d
    cp 22                       ; the status lines are not terrain
    ret nc
    rrca
    rrca
    rrca
    ld c,a
    and 0xe0
    ld l,a
    ld a,(sc_cx)
    or l
    ld l,a                      ; low byte: (R & 7) * 32 + cx
    ld a,c
    and 3
    ld c,a                      ; third
    add a,name_shadow>>8
    ld h,a
    ld a,(r_scr_hi)
    add a,0x18
    add a,c
    ld (sc_ah),a
    ld a,c
    add a,a
    add a,a
    add a,a
    ld c,a
    ld a,(r_scr_hi)
    or c
    ld (sc_ph),a
    ld a,(sc_cols)
    ld b,a
.col:
    ld a,(hl)
    or a
    jr z,.cnext                 ; empty
    cp 0xf6
    jr c,.cell
    cp 0xf8
    jr c,.cnext                 ; a star
.cell:
    push hl
    ld a,(sc_ah)
    ld h,a
    ld a,(hl)
    and 0x38
    jr nz,.keep                 ; coloured paper: a dense tile, inverted
    ld a,(sc_ph)
    ld h,a
    xor a
    rept 7
    ld (hl),a
    inc h
    endr
    ld (hl),a
.keep:
    pop hl
.cnext:
    inc l
    djnz .col
    inc d
    dec e
    jr nz,.row
    ret

sc_y:       db 0
sc_cx:      db 0
sc_cols:    db 0
sc_ah:      db 0
sc_ph:      db 0
