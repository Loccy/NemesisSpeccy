; corre_el_mapa_una_columna's shift (MSX 4695-46A6, patched to jump here):
; Konami's map buffer moves one cell to the left, 22 rows of 31 cells.
; Instead of an LDIR followed by a full comparison at the upload, one pass
; shifts the buffer and name_shadow together and marks the cells whose tile
; changes (both screens).  The queued regions are compared first, so that
; name_shadow equals the buffer before the shift.  Star cells move with the
; map: star_cells and the star lists are shifted rather than rebuilt.
; Konami's registers are dead at 46A8 (it reloads HL and DE), so this
; clobbers AF, BC, DE, HL.

    macro SC_CELL n             ; HL = buffer cell c, DE = cell c + 1
        ld a,(de)
        cp (hl)
        jr z,.same
        ld (hl),a               ; the buffer...
        ld b,h
        ld a,h
        add a,(name_shadow>>8)-((0xED00+KRAM)>>8)
        ld h,a
        ld a,(de)
        ld (hl),a               ; ...and name_shadow
        ld h,b
        set n,c
.same:
        inc l
        inc e
    endm
    macro SC_GROUP
        ld c,0
        SC_CELL 0
        SC_CELL 1
        SC_CELL 2
        SC_CELL 3
        SC_CELL 4
        SC_CELL 5
        SC_CELL 6
        SC_CELL 7
        ld a,c
        or a
        call nz,sc_mark
        inc ixl
    endm

scroll_d:
    push ix
    call nm_flush
    ld hl,0xED00+KRAM
    ld ix,0                     ; IXL = dirty bitmap byte (cell >> 3)
    ld b,22
.row:
    push bc
    ld d,h
    ld e,l
    inc e
    SC_GROUP
    SC_GROUP
    SC_GROUP
    ld c,0                      ; the last 7 (cell 31 keeps its tile)
    SC_CELL 0
    SC_CELL 1
    SC_CELL 2
    SC_CELL 3
    SC_CELL 4
    SC_CELL 5
    SC_CELL 6
    ld a,c
    or a
    call nz,sc_mark
    inc ixl
    inc hl                      ; next row
    pop bc
    dec b
    jp nz,.row
    pop ix
    jp star_shift

; Mark the cells in C of dirty bitmap byte IXL on both screens.
sc_mark:
    push hl
    ld a,ixl
    ld l,a
    ld h,dirty0>>8
    ld a,(hl)
    or c
    ld (hl),a
    set 7,l
    ld a,(hl)
    or c
    ld (hl),a
    pop hl
    ret

; The star cells after the shift: star_cells moves one bit left per row
; (column 31 keeps its bit, its cell kept its tile), and in each list an
; entry moves one column left, an entry in column 0 goes, and one that was
; in column 31 also stays there.
star_shift:
    ld hl,star_cells
    ld b,22
.bits:
    inc l
    inc l
    inc l
    ld a,(hl)
    and 0x80
    ld c,a                      ; column 31
    srl (hl)
    dec l
    rr (hl)
    dec l
    rr (hl)
    dec l
    rr (hl)
    inc l
    inc l
    inc l
    ld a,(hl)
    or c
    ld (hl),a
    inc l
    djnz .bits
    ld a,(star_ovf)
    or a
    ret nz                      ; the lists are not in use
    ld c,0                      ; list k
.list:
    ld a,c
    add a,star_n&0xff
    ld l,a
    ld h,star_n>>8
    ld b,(hl)                   ; entries
    ld a,l
    add a,star_base-star_n
    ld l,a
    ld e,(hl)                   ; first entry's low byte
    ld d,e                      ; (start, for the second pass)
    ld a,b
    or a
    jr z,.lnext
    ld l,e
    ld h,star_l>>8
.ent:
    ld a,(hl)
    and 31
    jr z,.drop
    dec (hl)
    inc l
    djnz .ent
    jr .pass2
.drop:                          ; column 0: the last entry takes its place
    push hl
    ld a,l
    add a,b
    dec a
    ld l,a
    ld a,(hl)
    pop hl
    ld (hl),a
    push hl
    ld a,c
    add a,star_n&0xff
    ld l,a
    ld h,star_n>>8
    dec (hl)
    pop hl
    djnz .ent                   ; the moved entry is examined next
.pass2:                         ; entries now in column 30 were in 31: add 31 back
    ld a,c
    add a,star_n&0xff
    ld l,a
    ld h,star_n>>8
    ld b,(hl)
    ld a,b
    or a
    jr z,.lnext
    ld e,d
.p2:
    ld l,e
    ld h,star_l>>8
    ld a,(hl)
    and 31
    cp 30
    jr nz,.p2next
    ld a,(hl)
    inc a                       ; that cell in column 31
    push af
    ld a,c
    add a,star_n&0xff
    ld l,a
    ld h,star_n>>8
    ld a,(hl)
    cp STAR_CAP
    jr nc,.full
    inc (hl)
    add a,d                     ; append at start + count
    ld l,a
    ld h,star_l>>8
    pop af
    ld (hl),a
    jr .p2next
.full:
    pop af
    ld a,1
    ld (star_dirty),a
.p2next:
    inc e
    djnz .p2
.lnext:
    inc c
    ld a,c
    cp 6
    jr nz,.list
    ret
