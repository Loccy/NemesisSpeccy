; MSX TMS9918 tile (8 pattern rows, 8 colour rows) -> Spectrum tile (8 rows
; and one attribute), at runtime, from Konami's own VRAM uploads.
;
; Same method as the build-time fit the earlier renderers used, restricted so
; it runs in reasonable time: for each bright level, the candidate ZX colours
; are the nearest ZX colour of each MSX colour present; every (ink, paper)
; pair of candidates is scored by summed squared RGB error, with the same
; tie-breaks.  Checked against the full search on every tile of every stage:
; 95% identical, 0.2% more total error (spec/fit_eval.py).  Distances are
; squared RGB distance >> 8, so every sum fits 16 bits.
;
; Tiles are converted lazily: Konami's uploads only mark them (tile_cdirty
; when a colour row changed, tile_pdirty when only pattern rows did), and the
; renderer converts a tile the first time it draws it.  A pattern-only change
; (the twinkling star tiles) keeps the tile's ink and paper and just maps the
; new pixels, which is much cheaper than a full fit.

; A = MSX colour; returns A = 0xFF if it is strictly nearer the chosen ink
; than the paper (and ink != paper), else 0.  Preserves BC, IX, IY.
nearer_ink:
    push bc
    add a,a
    add a,a
    add a,a
    add a,a
    ld c,a                      ; m * 16
    ld a,(cv_best_ink)
    ld b,a
    ld a,(cv_best_pap)
    cp b
    jr z,.zero
    add a,a
    add a,c
    ld l,a
    ld a,(cv_dbase)
    ld h,a
    ld e,(hl)
    inc l
    ld d,(hl)                   ; DE = D[m][paper]
    ld a,b
    add a,a
    add a,c
    ld l,a
    ld a,(hl)
    inc l
    ld h,(hl)
    ld l,a                      ; HL = D[m][ink]
    or a
    sbc hl,de
    jr nc,.zero
    ld a,0xff
    pop bc
    ret
.zero:
    xor a
    pop bc
    ret

cv_pat:     ds 8                ; input: pattern rows
cv_col:     ds 8                ; input: colour rows (fg << 4 | bg)
cv_out:     ds 9                ; output: 8 rows + attribute
cv_best_ink: db 0
cv_best_pap: db 0
cv_dbase:   db 0                ; high byte of cv_dist for this bright

; ---------------------------------------------------------------------------
; Bookkeeping between Konami's uploads and the renderer.

chg_list:   ds 48               ; tiles changed this tick: (third, id, row or 0xFF = whole tile)
nt_row:     db 0xff             ; row for the next note_tile
chg_n:      db 0                ; 0xFF = too many: redraw everything

; Called by the VRAM shim when a byte of tile DE>>3 changed (DE = offset in
; the colour or pattern table).  HL = the bitmap to mark (tile_cdirty or
; tile_pdirty).  Clobbers A, B, HL.
mark_tile:
    ; bitmap byte = DE >> 6, bit = (DE >> 3) & 7
    ld a,e
    rlca
    rlca
    and 3
    ld b,a
    ld a,d
    add a,a
    add a,a
    or b
    add a,l
    ld l,a
    ld a,e
    rrca
    rrca
    rrca
    and 7
    ld b,a
    ld a,1
    jr z,.bit
.sh:
    add a,a
    djnz .sh
.bit:
    ld b,a
    and (hl)
    ret nz                      ; already waiting: its cells are marked already
    ld a,b
    or (hl)
    ld (hl),a
    call flag_tile
    ld a,0xff                   ; the whole tile
    ld (nt_row),a
    ; fall through: the cells showing it must be redrawn

; Note that tile DE>>3 looks different now: its cells are redrawn on both
; screens.  Clobbers A, B, HL.
note_tile:
    ld a,1
    ld (star_stale),a           ; tiles 0/F6/F7 may differ now
    ld a,d                      ; id = (DE >> 3) & 255
    and 7
    ld b,a
    ld a,e
    srl b
    rra
    srl b
    rra
    srl b
    rra
    ld l,a
    ld a,(chg_n)
    cp 16
    jr c,.room
    ld a,0xff
    ld (chg_n),a
    ret
.room:
    ld b,a
    inc a
    ld (chg_n),a
    ld a,b
    add a,a
    add a,b
    add a,chg_list&0xff
    ld b,l                      ; id
    ld l,a
    ld h,chg_list>>8
    jr nc,.nc
    inc h
.nc:
    ld a,d
    rrca
    rrca
    rrca
    and 3
    ld (hl),a
    inc hl
    ld (hl),b
    inc hl
    ld a,(nt_row)
    ld (hl),a
    ret

; Flag tile DE>>3 (DE = offset in the colour or pattern table) in the tile
; set: bit 7 of its attribute tells the renderer to convert it first.
; Clobbers A, B, HL.
flag_tile:
    push af                     ; (a placeholder: the stack layout below counts it)
    ld a,d
    rrca
    rrca
    rrca
    and 3
    ld b,a                      ; third
    add a,a
    add a,a
    add a,a
    add a,b
    add a,TILE_PAGES+8
    ld h,a
    ld a,e
    rrca
    rrca
    rrca
    and 31
    ld l,a
    ld a,d
    and 7
    rrca
    rrca
    rrca
    or l
    ld l,a                      ; id
    ld a,PAGE_7
    call borrow_page
    set 7,(hl)
    call unborrow_page
    pop af
    ret

; End of a tick: the cells showing tiles that changed are redrawn on both
; screens (all cells after a load).
tick_tiles:
    ld a,(chg_n)
    or a
    jr z,.stars
    cp 0xff
    jr nz,.some
    ; a load: every pending tile gets a full conversion, not a recolour
    ld hl,tile_cdirty
    ld b,96
.or:
    set 7,l
    ld a,(hl)
    ld (hl),0
    res 7,l
    or (hl)
    ld (hl),a
    inc l
    djnz .or
    ld a,(dz_on)                ; the dissolve marks only the bits: flag the
    or a                        ; tiles for the renderer here (0.107)
    call nz,dz_flag
    xor a
    ld (chg_n),a
    call star_reset
    jp dirty_all
.some:
    ld b,a
    xor a
    ld (chg_n),a
    ld hl,chg_list
    ; star rows (tiles F6/F7, one row each) are collected for one pass over
    ; the cells known to hold stars; anything else is searched for
.inv:
    ld d,(hl)
    inc hl
    ld e,(hl)
    inc hl
    ld a,(hl)
    inc hl
    push bc
    push hl
    cp 0xff
    jr z,.whole
    ld c,a
    ld a,e
    sub 0xf6
    cp 2
    jr nc,.other
    ; star_rows[third * 2 + (id - F6)] = row
    ld b,a
    ld a,d
    add a,a
    add a,b
    ld hl,star_rows
    add a,l
    ld l,a
    ld a,c
    or 0x80                     ; a row still to look up
    ld (hl),a
    ld a,1
    ld (star_any),a
    jr .done1
.other:
    ld a,c
    ifndef NEXT
    call redraw_tile_row
    else
    call 0x0112                 ; Next: lo_rowmark (Layer 2 cells marked)
    endif
    jr .done1
.whole:
    call invalidate_tile
.done1:
    pop hl
    pop bc
    djnz .inv
.stars:
    ret                         ; the star rows are drawn by render_frame (star_update)

; From render_frame, with the hidden screen chosen: bring its star cells up to
; date (rows that changed this tick, or last tick for the other screen).
star_update:
    ld a,(star_any)
    ld hl,star_carry_any
    or (hl)
    ret z
    ld a,(star_dirty)
    or a
    call nz,star_rebuild
    jp redraw_star_rows

star_reset:
    ld hl,star_rows
    ld b,6
.r:
    ld (hl),0xff
    inc hl
    djnz .r
    xor a
    ld (star_any),a
    ret

; [third][F6/F7] -> 0xFF nothing; 0x80 + row: that row changed (look it up);
; otherwise the screen line (8 * third + row) whose byte is in star_bytes
; (blink_native writes these directly).
star_rows:  db 0xff,0xff,0xff,0xff,0xff,0xff
star_carry: db 0xff,0xff,0xff,0xff,0xff,0xff   ; lines written last tick (to the other screen only)
star_cbyte: ds 6
star_carry_any: db 0
star_bytes: ds 6                ; ... -> the converted row
star_any:   db 0
    assert (star_rows >> 8) == ((star_rows + 26) >> 8)

star_dirty: db 1                ; star_cells changed since the lists were made
star_ovf:   db 0                ; a list overflowed: scan star_cells instead

; Lists of the star cells' screen low bytes, one list per (third, F6/F7),
; made from star_cells when it changes (the map scrolled).
star_rebuild:
    xor a
    ld (star_dirty),a
    ld (star_ovf),a
    ld hl,star_base
    ld de,star_wp
    ld bc,6
    ldir
    ld hl,star_cells
    xor a
    call .third
    ld a,1
    call .third
    ld a,2
    call .third
    ; counts
    ld hl,star_wp
    ld de,star_base
    ld bc,star_n
    ld a,6
.cnt:
    push af
    ld a,(de)
    cpl
    inc a
    add a,(hl)
    ld (bc),a
    inc l
    inc e
    inc c
    pop af
    dec a
    jr nz,.cnt
    ret
.third:                         ; A = third; HL = its 32 bytes of star_cells
    ld b,a
    add a,name_shadow>>8
    ld (.nmp+1),a
    ld a,b
    add a,a
    add a,star_wp&0xff
    ld (.kb+1),a
    ld b,32
.byte:
    ld a,(hl)
    or a
    jr nz,.cells
.next:
    inc l
    djnz .byte
    ret
.cells:
    push bc
    push hl
    ld c,a                      ; bits
    ld a,l
    sub star_cells&0xff
    add a,a
    add a,a
    add a,a
    ld b,a                      ; first cell low byte
.bit:
    ld h,lsb_index>>8
    ld l,c
    ld a,(hl)
    add a,b
    ld e,a                      ; cell low byte
    ld l,a
.nmp:
    ld h,0
    ld a,(hl)
    sub 0xf6
    cp 2
    jr nc,.nb
.kb:
    add a,0                     ; star_wp + third * 2 + (F6/F7)
    ld l,a
    ld h,star_wp>>8
    ld a,(hl)
    set 3,l
    cp (hl)
    jr nc,.ovf
    res 3,l
    inc (hl)
    ld l,a
    ld h,star_l>>8
    ld (hl),e
.nb:
    ld a,c
    dec a
    and c
    ld c,a
    jr nz,.bit
    pop hl
    pop bc
    jr .next
.ovf:
    pop hl
    pop bc
    ld a,1
    ld (star_ovf),a
    ret

; Copy the changed star rows into every star cell on both screens.  Star
; cells are tracked in star_cells (one bit per cell) by the map copy.
redraw_star_rows:
    ld a,(cur_page)
    push af
    ld a,PAGE_7
    call set_page
    ; for each (third, F6/F7) whose row changed: the converted row byte and
    ; its screen line (8 * third + row)
    ld ix,star_rows
    ld iy,star_bytes
    ld d,0                      ; third
.prep:
    ld e,0xf6
.prep2:
    ld a,(ix+0)
    cp 0xff
    jr z,.pnext
    bit 7,a
    jr z,.pnext                 ; prepared already
    and 7
    ld c,a                      ; row
    ld a,d
    add a,a
    add a,a
    add a,a
    add a,d
    add a,TILE_PAGES
    add a,c
    ld h,a
    ld l,e
    ld a,(hl)
    ld (iy+0),a                 ; converted row
    ld a,d
    add a,a
    add a,a
    add a,a
    add a,c
    ld (ix+0),a                 ; now: screen line 8 * third + row
.pnext:
    inc ix
    inc iy
    inc e
    ld a,e
    cp 0xf8
    jr nz,.prep2
    inc d
    ld a,d
    cp 3
    jr nz,.prep
    ld a,(star_ovf)
    or a
    jr nz,.slow
    ; the lists: star_n[k] screen low bytes at star_l + star_base[k].  Only
    ; the hidden screen: a row written now is carried to the other screen
    ; next tick.
    xor a
    ld (star_carry_any),a
    ld c,0
.fl:
    ld hl,star_rows
    ld a,l
    add a,c
    ld l,a
    ld a,(hl)
    cp 0xff
    jr z,.carried
    ld b,a                      ; line
    ld a,l
    add a,star_bytes-star_rows
    ld l,a
    ld a,(hl)                   ; the converted row
    ld e,a
    ld a,l
    add a,star_cbyte-star_bytes
    ld l,a
    ld (hl),e                   ; carry it to the other screen
    ld a,l
    add a,star_carry-star_cbyte
    ld l,a
    ld (hl),b
    ld a,1
    ld (star_carry_any),a
    jr .draw
.carried:
    ld a,l
    add a,star_carry-star_rows
    ld l,a
    ld a,(hl)
    cp 0xff
    jr z,.fnext
    ld (hl),0xff
    ld b,a                      ; line
    ld a,l
    add a,star_cbyte-star_carry
    ld l,a
    ld e,(hl)                   ; the row
.draw:
    ld a,(r_scr_hi)
    or b
    ld d,a                      ; hidden screen line high byte
    ld h,star_l>>8
    ld a,c
    add a,star_n&0xff
    ld l,a
    ld a,(hl)
    or a
    jr z,.fnext
    ld b,a                      ; cells in list k
    ld a,l
    add a,star_base-star_n
    ld l,a
    ld l,(hl)                   ; list k's start
    ld a,e
.fc:
    ld e,(hl)
    inc l
    ld (de),a
    djnz .fc
.fnext:
    inc c
    ld a,c
    cp 6
    jr nz,.fl
    call star_reset
    pop af
    jp set_page
.slow:
    ld hl,star_cells
    ld b,96
.byte:
    ld a,(hl)
    or a
    jr nz,.cells
.next:
    inc l
    djnz .byte
    call star_reset
    pop af
    jp set_page
.cells:
    push bc
    push hl
    ld c,a
    ld a,l
    sub star_cells&0xff
    ld b,a
    rrca
    rrca
    rrca
    rrca
    rrca
    and 3
    ld d,a                      ; third
    add a,name_shadow>>8
    ld h,a
    ld a,b
    add a,a
    add a,a
    add a,a
    ld l,a                      ; first cell of the byte
    ld a,d
    add a,a
    ld e,a                      ; star table index base: third * 2
.bit:
    push hl
    ld h,lsb_index>>8           ; next set bit, lowest first
    ld a,l
    ld l,c
    add a,(hl)
    pop hl
    push hl
    ld l,a
    ld a,(hl)
    sub 0xf6
    cp 2
    jr nc,.skip
    add a,e
    ld hl,star_rows
    add a,l
    ld l,a
    ld a,(hl)                   ; screen line or 0xFF
    cp 0xff
    jr z,.skip
    ld b,a
    ld a,l
    add a,star_bytes-star_rows
    ld l,a
    ld a,(hl)                   ; the row
    pop hl
    push hl
    ld h,b
    set 6,h
    ld (hl),a                   ; screen 0
    set 7,h
    ld (hl),a                   ; screen 1
.skip:
    pop hl
    ld a,c
    dec a
    and c
    ld c,a
    jr nz,.bit
    pop hl
    pop bc
    jr .next


; Only row A of tile E (third D) changed (a star twinkling): copy that row
; into every cell showing the tile, on both screens.
rtr_row:    db 0
redraw_tile_row:
    ld (rtr_row),a
    ld a,(cur_page)
    push af
    ld a,PAGE_7
    call set_page
    ; the converted row byte
    ld a,d
    add a,a
    add a,a
    add a,a
    ld b,a                      ; 8 * third
    add a,d
    add a,TILE_PAGES
    ld c,a
    ld a,(rtr_row)
    add a,c
    ld h,a
    ld l,e
    ld a,(hl)
    ld (.byte+1),a
    ld a,(rtr_row)
    add a,b
    ld (.s0+1),a                ; screen 0 high byte - 0x40
    ; scan the third
    ld a,d
    add a,name_shadow>>8
    ld h,a
    ld l,0
    ld bc,256
    ld a,e
.find:
    cpir
    jr nz,.out
    push hl
    dec hl
.s0:
    ld a,0                      ; patched: 8 * third + row
    add a,0x40
    ld h,a
.byte:
    ld (hl),0                   ; patched: the row
    add a,0x80
    ld h,a
    ld a,(.byte+1)
    ld (hl),a
    pop hl
    ld a,b
    or c
    jr z,.out
    ld a,e
    jr .find
.out:
    pop af
    jp set_page

; A pattern byte of tile DE>>3 (row E & 7, DE = offset in the pattern table)
; changed to vw_val.  If the tile is converted and its ink and paper differ,
; map the new row straight into the tile set (the twinkling stars), and
; return carry set; otherwise carry clear.  Preserves BC, DE.
ru_row:     db 0
ru_id:      db 0
ru_third:   db 0
row_update:
    push bc
    push de
    ld a,e
    and 7
    ld (ru_row),a
    ld a,d                      ; id = (DE >> 3) & 255
    and 7
    ld b,a
    ld a,e
    srl b
    rra
    srl b
    rra
    srl b
    rra
    ld (ru_id),a
    and 7
    ld l,a
    ld h,bitmask>>8
    ld c,(hl)                   ; this tile's bit
    ld a,d
    rrca
    rrca
    rrca
    and 3
    ld (ru_third),a
    rrca
    rrca
    rrca                        ; third * 32
    ld b,a
    ld a,(ru_id)
    rrca
    rrca
    rrca
    and 31
    or b
    ld l,a
    ld h,tile_cdirty>>8
    ld a,(hl)
    set 7,l
    or (hl)
    and c
    jp nz,.fail                 ; not converted yet: the renderer will
    push af                     ; (a placeholder: the stack layout below counts it)
    ; the tile's attribute (page 7)
    ld a,PAGE_7
    call borrow_page
    ld a,(ru_third)
    ld b,a
    add a,a
    add a,a
    add a,a
    add a,b
    add a,TILE_PAGES+8
    ld h,a
    ld a,(ru_id)
    ld l,a
    ld b,(hl)
    ld a,b
    rrca
    rrca
    rrca
    xor b
    and 7
    jp z,.fail_ei               ; ink = paper: needs a full conversion
    ld a,b
    and 7
    ld (cv_best_ink),a
    ld a,b
    rrca
    rrca
    rrca
    and 7
    ld (cv_best_pap),a
    ld a,b
    rlca
    rlca
    and 1
    add a,cv_dist>>8
    ld (cv_dbase),a
    ; the row's colour byte (page C)
    ld a,PAGE_C
    call borrow_page
    pop af
    pop de
    push de
    push af
    ld hl,COL_SHADOW
    add hl,de
    ld a,(hl)
    push af
    rrca
    rrca
    rrca
    rrca
    and 15
    call nearer_ink
    ld c,a                      ; fg -> ink mask
    pop af
    and 15
    call nearer_ink
    ld b,a                      ; bg -> ink mask
    ld a,(vw_val)
    and c
    ld c,a
    ld a,(vw_val)
    cpl
    and b
    or c
    ld c,a                      ; the converted row
    ld a,PAGE_7
    call borrow_page
    ld a,(ru_third)
    ld b,a
    add a,a
    add a,a
    add a,a
    add a,b
    add a,TILE_PAGES
    ld b,a
    ld a,(ru_row)
    add a,b
    ld h,a
    ld a,(ru_id)
    ld l,a
    ld (hl),c
    call unborrow_page
    pop af
.ok:
    pop de
    pop bc
    scf
    ret
.fail_ei:
    call unborrow_page
    pop af
.fail:
    pop de
    pop bc
    or a
    ret

; parpadea_dos_caracteres (MSX 475B), done here rather than through six
; WRTVRM calls: row 0 of the star tiles F6 and F7 in the three thirds is
; (E062) AND a mask from the table at 4786 picked by the tick counter.  The
; pattern shadow is kept as before; the converted row is worked out from a
; cached fit of the row's two MSX colours to the tile's ink and paper (kept
; per tile with the attribute and colour byte it was worked out for).
blink_masks: db 0xFF,0x00,0xFF,0xFF,0x00,0xFF,0xFF,0xFF   ; MSX 4786
bl_v6:      db 0                ; this tick's row for F6 / F7
bl_v7:      db 0
blrec:       ds 6*5              ; per tile: colour byte, cached attribute, colour, fg mask, bg mask

    macro BL_PAT kx, addr, var
        ld a,(var)
        ld hl,addr
        cp (hl)
        jr z,.same
        ld (hl),a
        set kx,c
.same:
    endm
    macro BL_COL kx, addr
        bit kx,c
        jr z,.skip
        ld a,(addr)
        ld (blrec+kx*5),a
.skip:
    endm
    macro BL_TILE kx, tpg, id, drt, msk, var, lnx
        bit kx,c
        jr z,.done
        ld a,(tile_cdirty+drt)
        ld l,a
        ld a,(tile_pdirty+drt)
        or l
        and msk
        jr nz,.whole                ; not converted yet
        ld a,(((tpg+8)<<8)+id)
        ld e,a                      ; attribute
        rrca
        rrca
        rrca
        xor e
        and 7
        jr z,.whole                 ; ink = paper: needs a full conversion
        ld a,e
        ld hl,blrec+kx*5+1
        cp (hl)
        jr nz,.fit
        inc hl
        ld a,(blrec+kx*5)
        cp (hl)
        jr z,.fitted
.fit:
        ld hl,blrec+kx*5
        call bl_fit
.fitted:
        ld hl,blrec+kx*5+3
        ld a,(var)
        and (hl)
        ld d,a
        inc hl
        ld a,(var)
        cpl
        and (hl)
        or d
        ld (((tpg)<<8)+id),a
        ld (star_bytes+kx),a        ; for redraw_star_rows: the row and its line
        ld a,lnx
        ld (star_rows+kx),a
        jr .done
.whole:
        set kx,b
.done:
    endm
    macro BL_NOTE kx, voff
        bit kx,b
        jr z,.done
        push bc
        ld de,voff
        ld hl,tile_pdirty
        call mark_tile
        pop bc
.done:
    endm

blink_native:
    ifdef DRAW_EVERY
    ifndef TEST                 ; (test builds keep the pattern copy in step
    ld a,(logic_ctr)            ; with the MSX every tick, for the lockstep)
    dec a                       ; only for a tick that will be drawn: the
    ret nz                      ; star rows of an undrawn one are never shown
    endif
    endif
    ld a,(0xE003+KRAM)
    and 6
    ld e,a
    ld d,0
    ld hl,blink_masks
    add hl,de
    ld c,(hl)
    inc hl
    ld b,(hl)
    ifndef NEXT
    ld a,(0xE062+KRAM)
    ld e,a
    else
    ld a,0x10                   ; Next: the star stays mid-cell; the hardware
    nop                         ; scroll moves it (on the MSX, E062's rotating
    ld e,a                      ; bit did, a pixel a tick)
    endif
    and c
    ld (bl_v6),a
    ld a,e
    and b
    ld (bl_v7),a
    push bc
    push af                     ; (a placeholder: the stack layout below counts it)
    ld a,PAGE_D                 ; the pattern shadow; C = which changed
    call borrow_page
    ld c,0
    BL_PAT 0, PAT_SHADOW+0x07B0, bl_v6
    BL_PAT 1, PAT_SHADOW+0x07B8, bl_v7
    BL_PAT 2, PAT_SHADOW+0x0FB0, bl_v6
    BL_PAT 3, PAT_SHADOW+0x0FB8, bl_v7
    BL_PAT 4, PAT_SHADOW+0x17B0, bl_v6
    BL_PAT 5, PAT_SHADOW+0x17B8, bl_v7
    ld a,c
    or a
    jp z,.out
    ld a,PAGE_C                 ; their colour bytes
    call borrow_page
    BL_COL 0, PAT_SHADOW+0x07B0
    BL_COL 1, PAT_SHADOW+0x07B8
    BL_COL 2, PAT_SHADOW+0x0FB0
    BL_COL 3, PAT_SHADOW+0x0FB8
    BL_COL 4, PAT_SHADOW+0x17B0
    BL_COL 5, PAT_SHADOW+0x17B8
    ld a,PAGE_7                 ; the converted rows; B = tiles needing conversion
    call borrow_page
    ld b,0
    BL_TILE 0, TILE_PAGES+0, 0xF6, 30, 0x40, bl_v6, 0
    BL_TILE 1, TILE_PAGES+0, 0xF7, 30, 0x80, bl_v7, 0
    BL_TILE 2, TILE_PAGES+9, 0xF6, 62, 0x40, bl_v6, 8
    BL_TILE 3, TILE_PAGES+9, 0xF7, 62, 0x80, bl_v7, 8
    BL_TILE 4, TILE_PAGES+18, 0xF6, 94, 0x40, bl_v6, 16
    BL_TILE 5, TILE_PAGES+18, 0xF7, 94, 0x80, bl_v7, 16
    push bc
    call unborrow_page
    pop bc
    pop af
.di1:
    ld a,c                      ; rows written: redraw_star_rows has work
    xor b
    jr z,.nostars
    ld a,1
    ld (star_any),a
.nostars:
    BL_NOTE 0, 0x07B0
    BL_NOTE 1, 0x07B8
    BL_NOTE 2, 0x0FB0
    BL_NOTE 3, 0x0FB8
    BL_NOTE 4, 0x17B0
    BL_NOTE 5, 0x17B8
    jr .regs
.out:
    call unborrow_page
    pop af
.regs:
    pop bc                      ; as the original leaves them
    ld c,b
    ld hl,0x37B9
    ld (vdp_addr),hl
    dec hl
    ld de,0x0800
    ret

; Fit for blink_native: HL = the tile's record (colour byte first), E = its
; attribute.  Stores the attribute and colour as the cache key and the two
; masks (MSX foreground / background colour nearer the ink).
bl_fit:
    push bc
    ld a,(hl)                   ; colour byte
    inc hl
    ld (hl),e
    inc hl
    ld (hl),a
    inc hl
    push hl
    push af
    ld a,e
    and 7
    ld (cv_best_ink),a
    ld a,e
    rrca
    rrca
    rrca
    and 7
    ld (cv_best_pap),a
    ld a,e
    rlca
    rlca
    and 1
    add a,cv_dist>>8
    ld (cv_dbase),a
    pop af
    push af
    rrca
    rrca
    rrca
    rrca
    and 15
    call nearer_ink
    ld c,a
    pop af
    and 15
    call nearer_ink
    pop hl
    ld (hl),c
    inc hl
    ld (hl),a
    pop bc
    ret

; Map page A at C000 for a moment without telling cur_page (Konami's page);
; unborrow_page puts it back.  Interrupts may stay on (out_page).
borrow_page equ out_page

; Before drawing tile E of third D: convert it if Konami changed it.
; Called with page 7 at C000; returns with page 7.  Preserves BC, DE, HL.
ensure_tile:
    ld a,1
    ld (star_stale),a
    push hl
    ; bitmap byte = third * 32 + id >> 3, bit = id & 7
    ld a,e
    rrca
    rrca
    rrca
    and 31
    ld l,a
    ld a,d
    rrca
    rrca
    rrca
    add a,l
    ld l,a
    push bc
    ld a,e
    and 7
    ld c,a
    ld b,bitmask>>8
    ld a,(bc)
    ld c,a
    ld h,tile_cdirty>>8
    and (hl)
    jr nz,.full
    set 7,l                     ; tile_pdirty
    ld a,c
    and (hl)
    jr z,.clean
    ld a,(dz_on)                ; Konami's dissolve under way: the full path,
    or a                        ; where conv_dz takes it (0.107)
    jr nz,.pfull
    ld a,c
    cpl
    and (hl)
    ld (hl),a
    pop bc
    pop hl
    push bc
    push de
    push hl
    call load_tile_inputs
.ponly:
    pop hl                      ; DE again: load_tile_inputs used it (before
    pop de                      ; 0.99a the attribute below was read from an
    push de                     ; address made of cv_col's, a byte of bank 2
    push hl                     ; holding 02: red ink on black)
    ; current attribute from the tile set: keep its ink and paper unless
    ; they are the same colour (then there was nothing to keep)
    ld a,d
    add a,a
    add a,a
    add a,a
    add a,d
    add a,TILE_PAGES+8
    ld h,a
    ld l,e
    ld a,(hl)
    and 0x7f
    ld (cv_out+8),a
    ld b,a
    rrca
    rrca
    rrca
    xor b
    and 7
    jr z,.refit
    call recolour_e
    jr .store
.refit:
    call convert_cached
    jr .store
.pfull:
    res 7,l
.full:
    ld a,c
    cpl
    and (hl)
    ld (hl),a
    set 7,l
    ld a,c
    cpl
    and (hl)
    ld (hl),a
    pop bc
    pop hl
    push bc
    push de
    push hl
    call load_tile_inputs
    call conv_dz                ; convert_cached, or the dissolve's own (0.107)
.store:
    pop hl
    pop de
    push de
    push hl
    call bar_style              ; the power-up bar: its own Spectrum colours
    ifndef NO_INVERT
    call tile_post              ; mostly ink: stored the other way round; the nuke capsule cyan
    endif
    ld a,d
    add a,a
    add a,a
    add a,a
    add a,d
    add a,TILE_PAGES
    ld h,a
    ld l,e
    ld de,cv_out
    ld b,9
.put:
    ld a,(de)
    ld (hl),a
    inc de
    inc h
    djnz .put
    pop hl
    pop de
    pop bc
    ret
.clean:
    pop bc
    pop hl
    ret

; convert_tile through a cache of 16 recent conversions in page B (FE00-FFFF,
; 32 bytes each: pattern, colour, result, valid), direct-mapped by a hash of
; the 16 input bytes.  Tiles that change back and forth (the power-up bar,
; animated scenery) then cost a lookup.  Called and returns with page 7.
CC_BASE equ 0xFE00
cc_entry:   dw 0
convert_cached:
    ld hl,cv_pat
    ld b,16
    xor a
.h:
    rlca
    add a,(hl)
    inc hl
    djnz .h
    and 15
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,CC_BASE
    add hl,de
    ld (cc_entry),hl
    ld a,PAGE_B
    call set_page
    ld de,cv_pat
    ld b,16
.c:
    ld a,(de)
    cp (hl)
    jr nz,.miss
    inc hl
    inc de
    djnz .c
    ld de,9
    add hl,de
    ld a,(hl)                   ; valid
    or a
    jr z,.miss
    sbc hl,de
    ld de,cv_out
    ld bc,9
    ldir
    ld a,PAGE_7
    jp set_page
.miss:
    call convert_tile           ; (in page B, mapped)
    ld de,(cc_entry)
    ld hl,cv_pat
    ld bc,25
    ldir
    ex de,hl
    ld (hl),1
    ld a,PAGE_7
    jp set_page
    assert cv_col == cv_pat + 8 && cv_out == cv_col + 8

; Copy tile E of third D's colour and pattern rows from the shadows into
; cv_col / cv_pat; leaves page 7 at C000.
load_tile_inputs:
    ld l,e
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,d
    add a,a
    add a,a
    add a,a
    add a,h
    ld h,a                      ; third * 0x800 + id * 8
    push hl
    ld bc,COL_SHADOW
    add hl,bc
    ld a,PAGE_C
    call set_page
    ld de,cv_col
    ld bc,8
    ldir
    pop hl
    ld bc,PAT_SHADOW
    add hl,bc
    ld a,PAGE_D
    call set_page
    ld de,cv_pat
    ld bc,8
    ldir
    ld a,PAGE_7
    jp set_page

; Both screens redraw every cell of third D that shows tile E.
invalidate_tile:
    ld a,d
    add a,name_shadow>>8
    ld h,a
    ld l,0
    ld bc,256
    ld a,e
.find:
    cpir
    ret nz                      ; no (further) match in this third
    push bc
    push hl
    dec hl
    ld b,d
    ld c,l
    call dirty_cell
    pop hl
    pop bc
    ld a,b
    or c
    ret z
    ld a,e
    jr .find
