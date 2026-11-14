; The tile set's bookkeeping between Konami's play and the renderer (the
; native build: the tiles come converted when the game is built and are
; loaded by nl_load, native.asm; nothing here converts MSX characters).
;
; chg_list: tiles whose look changed this tick (a star's row, or a whole
; tile), redrawn where they show at the end of the tick (tick_tiles); after
; a load every cell is redrawn.  The stars (F6, F7) are kept as rows
; (star_rows, star_bytes) for draw_stars and redraw_star_rows.

chg_list:   ds 48               ; tiles changed this tick: (third, id, row or 0xFF = whole tile)
nt_row:     db 0xff             ; row for the next note_tile
chg_n:      db 0                ; 0xFF = too many: redraw everything

; Note that tile DE>>3 (DE = third * 0x800 + id * 8) looks different as a
; whole now: its cells are redrawn on both screens.  Clobbers A, B, HL.
note_whole:
    ld a,0xff
    ld (nt_row),a

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

; End of a tick: the cells showing tiles that changed are redrawn on both
; screens (all cells after a load).
tick_tiles:
    ld a,(chg_n)
    or a
    jr z,.stars
    cp 0xff
    jr nz,.some
    ; a load (or a dissolve's chunk): every cell redrawn
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
    ifdef Z48
    call dirty_all              ; (the 48K: every cell, should a row ever change)
    else
    ifndef NEXT
    call redraw_tile_row
    else
    call 0x0112                 ; Next: lo_rowmark (Layer 2 cells marked)
    endif
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

    ifndef NEXT                 ; (the 128K's renderer: not in the Next build, NX_AT)
    ifndef Z48                  ; (the 48K's stars: z48_stars.asm)
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
    endif
    endif
    NX_AT 0x89CF

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

    ifndef NEXT                 ; (the 128K's renderer: not in the Next build, NX_AT)
    ifndef Z48                  ; (the 48K's stars: z48_stars.asm)
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
    ; (star_rows holds each changed row's screen line and star_bytes its
    ; byte, as blink_native leaves them.  Until 1.2 six entries were walked
    ; here first for a row still to be looked up in the tile set (bit 7), which
    ; only tick_tiles sets, for a note_tile with a row: nothing notes a row
    ; now that the tiles come converted (nt_row is only ever 0xFF).)
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
    endif


    ifndef Z48                  ; (the 48K's stars: z48_stars.asm)
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

    endif                       ; (Z48)
    endif
    NX_AT 0x8BEF

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


; Map page A at C000 for a moment without telling cur_page (Konami's page);
; unborrow_page puts it back.  Interrupts may stay on (out_page).
borrow_page equ out_page

; Native tiles never carry the old "convert me" flag (attribute bit 7), so
; the renderer's checks for it never call this; kept for them.
ensure_tile:
    ret

; ---------------------------------------------------------------------------
; Konami's star twinkle (parpadea_dos_caracteres, 0:475B, patched to come
; here).  Konami rewrites row 0 of the star characters F6 and F7 in each
; third: E062's rotating bit, blanked on some ticks (blink_masks, by E003).
; Here the rows go straight into the tile set.  A star tile is blank when a
; stage loads (attribute 0, as the colour fit made it with no pixel); the
; first time it shows a pixel it takes its stage's attribute (star_attr, from
; nl_load) and its cells are redrawn, as 1.0's conversion did; after that only
; its row changes, which draw_stars and redraw_star_rows bring to the screen
; (star_rows, star_bytes).  native_pack.py checks that a star converts to its
; own row in that attribute for every pixel position.

blink_masks: db 0xFF,0x00,0xFF,0xFF,0x00,0xFF,0xFF,0xFF   ; MSX 4786
bl_v6:      db 0                ; this tick's row for F6 / F7
bl_v7:      db 0
bl_prev:    ds 6                ; each star tile's row 0 as last set (0 after a load)
star_attr:  ds 6                ; [third][F6/F7]: the attribute once lit (nl_load)

    macro BL_TILE kx, tpg, id, var, lnx
        ld a,(var)
        ld hl,bl_prev+kx
        cp (hl)
        jr z,.done
        ld (hl),a
        ld e,a                      ; the row
        ld a,(((tpg+8)<<8)+id)      ; the attribute
        ld d,a
        rrca
        rrca
        rrca
        xor d
        and 7
        jr nz,.lit                  ; lit already: just the row
        ld a,e
        or a
        jr z,.done                  ; still blank
        ld a,(star_attr+kx)         ; first lit since the load: the whole tile
        ld (((tpg+8)<<8)+id),a
        ld a,e
        ld (((tpg)<<8)+id),a
        set kx,b
        jr .done
.lit:
        ld a,e
        ld (((tpg)<<8)+id),a
        ld (star_bytes+kx),a        ; for redraw_star_rows: the row and its line
        ld a,lnx
        ld (star_rows+kx),a
        set kx,c
.done:
    endm
    macro BL_NOTE kx, voff
        bit kx,b
        jr z,.done
        push bc
        ld de,voff
        call note_whole
        pop bc
.done:
    endm

    ifdef NEXT
; The Next: the star rows go into its copy of the pattern table (page D,
; E800: F6 and F7 of each third, row 0), which lo_render compares with what it
; last drew (nx_l2.asm).  The star stays mid-cell (10h): the hardware scroll
; moves it, where on the MSX E062's rotating bit did, a pixel a tick.
blink_native:
    ld a,(0xE003+KRAM)
    and 6
    ld e,a
    ld d,0
    ld hl,blink_masks
    add hl,de
    ld c,(hl)
    inc hl
    ld b,(hl)
    push bc
    ld a,0x10
    and c
    ld e,a
    ld a,0x10
    and b
    ld d,a
    ld a,PAGE_D
    call borrow_page
    ld a,e
    ld (0xE800+0x07B0),a
    ld (0xE800+0x0FB0),a
    ld (0xE800+0x17B0),a
    ld a,d
    ld (0xE800+0x07B8),a
    ld (0xE800+0x0FB8),a
    ld (0xE800+0x17B8),a
    call unborrow_page
    ld hl,tile_pdirty+0x1E      ; F6 and F7 written since the load (they have
    ld a,0xC0                   ; no block in the pool anyway)
    or (hl)
    ld (hl),a
    ld l,(tile_pdirty+0x3E)&0xff
    ld a,0xC0
    or (hl)
    ld (hl),a
    ld l,(tile_pdirty+0x5E)&0xff
    ld a,0xC0
    or (hl)
    ld (hl),a
    pop bc                      ; as the original leaves them
    ld c,b
    ld hl,0x37B9
    ld (vdp_addr),hl
    dec hl
    ld de,0x0800
    ret
    else
    ifdef Z48
    include "z48_stars.asm"
    else
blink_native:
    ifdef DRAW_EVERY
    ifndef TEST                 ; (test builds keep the rows in step with the
    ld a,(logic_ctr)            ; MSX every tick)
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
    ld a,(0xE062+KRAM)
    ld e,a
    and c
    ld (bl_v6),a
    ld a,e
    and b
    ld (bl_v7),a
    push bc
    ld a,PAGE_7                 ; the tile set
    call borrow_page
    ld bc,0                     ; C: rows written; B: tiles lit for the first time
    BL_TILE 0, TILE_PAGES+0, 0xF6, bl_v6, 0
    BL_TILE 1, TILE_PAGES+0, 0xF7, bl_v7, 0
    BL_TILE 2, TILE_PAGES+9, 0xF6, bl_v6, 8
    BL_TILE 3, TILE_PAGES+9, 0xF7, bl_v7, 8
    BL_TILE 4, TILE_PAGES+18, 0xF6, bl_v6, 16
    BL_TILE 5, TILE_PAGES+18, 0xF7, bl_v7, 16
    push bc
    call unborrow_page
    pop bc
    ld a,c
    or a
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
    pop bc                      ; as the original leaves them
    ld c,b
    ld hl,0x37B9
    ld (vdp_addr),hl
    dec hl
    ld de,0x0800
    ret
    endif
    endif

; A stage's load: the star tiles are blank again.
bl_reset:
    xor a
    ld hl,bl_prev
    ld b,6
.z:
    ld (hl),a
    inc hl
    djnz .z
    ret
