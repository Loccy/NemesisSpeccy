; Renderer: draws Konami's name table (name_shadow, VRAM 3800-3AFF) with the
; converted tile set, and Konami's 32 hardware sprites from its attribute
; buffer at EC80, into the hidden screen.
;
; Each screen has a bitmap of cells it must redraw (dirty0 / dirty1, one bit
; per cell).  A cell is marked in both when its name changes (found while
; Konami's map is copied each tick, or written through the VDP port), when
; its tile is re-converted, and in one screen when a sprite is drawn over it
; there (draw_sprite16: the cell is drawn again, without the sprite, at that
; screen's next picture).
; Sprites are ORed in, and their cells take the sprite's colour as ink.

    ifndef NEXT
SPR_ATTR equ 0xEC80+KRAM
    else
SPR_ATTR equ 0x3F80              ; Next: lo_sat (nx_low.asm), Konami's list with X corrected
    endif

r_scr_hi:   db 0                ; hidden screen pixel high byte base (0x40 / 0xC0)
r_dirty:    db 0                ; its dirty bitmap low byte (0x00 / 0x80)
r_erase:    dw 0                ; (the Next's: its erase list; the 128K has none since 1.2)
r_eptr:     dw 0                ; (erase list write pointer)

; Mark every cell of both screens.
dirty_all:
    ld hl,dirty0
    ld b,96
.l:
    ld (hl),0xff
    set 7,l
    ld (hl),0xff
    res 7,l
    inc l
    djnz .l
    ret

; Mark cell (third B, low byte C) in both screens.  Preserves BC, DE, HL.
dirty_cell:
    push hl
    ld a,c
    and 7
    ld l,a
    ld h,bitmask>>8
    ld a,(hl)
    push af
    ld a,c
    rrca
    rrca
    rrca
    and 31
    ld l,a
    ld a,b
    rrca
    rrca
    rrca
    or l
    ld l,a
    ld h,dirty0>>8
    pop af
    push af
    or (hl)
    ld (hl),a
    set 7,l
    pop af
    or (hl)
    ld (hl),a
    pop hl
    ret

    ifndef NEXT                 ; (the 128K's renderer: not in the Next build, NX_AT)
render_frame:
    ld a,(cur_page)
    push af
    ld a,PAGE_7
    call set_page
    ; screen 1 shown (bit 3) -> draw screen 0
    ld a,(port_bits)
    and 8
    ld a,0x40
    ld b,0
    jr nz,.set
    ld a,0xC0
    ld b,0x80
.set:
    ld (r_scr_hi),a
    ld a,b
    ld (r_dirty),a
    call star_update
    call draw_stars
rf_erased:
    call draw_cells
rf_cells:
    push ix
    call draw_sprites
    pop ix
rf_sprites:
    pop af
    jp set_page

; Redraw every marked cell of the hidden screen.  For each bitmap byte (8
; cells of one third) the page bases are patched into the loop; a tile whose
; attribute in the tile set has bit 7 set is waiting for conversion.
; Character 0 is blank in every third (no load writes it, and the dissolve
; leaves it zeros), and over a third of the cells drawn hold it: its eight
; rows are written as zeros without reading the tile set (.blank).  Its
; attribute is still the tile set's.
draw_cells:
    xor a
    call .third
    ld a,1
    call .third
    ld a,2
.third:                         ; A = third: patch its page bases, then its 32 bytes
    ld d,a
    ld (dc_third),a
    add a,name_shadow>>8
    ld (.nm+1),a
    ld a,d
    add a,a
    add a,a
    add a,a
    ld e,a                      ; 8 * third
    add a,d
    add a,TILE_PAGES
    ld (.src+1),a
    add a,8
    ld (.srca+1),a
    ld a,(r_scr_hi)
    add a,e
    ld (.dst+1),a
    ld (.bdst+1),a
    ld a,(r_scr_hi)
    add a,0x18
    add a,d
    ld (.att+1),a
    ld a,d
    rrca
    rrca
    rrca
    ld l,a                      ; third * 32
    ld a,(r_dirty)
    or l
    ld l,a
    ld h,dirty0>>8
    ld b,8                      ; 32 bytes, four at a time
.quad:
    ld a,(hl)
    inc l
    or (hl)
    inc l
    or (hl)
    inc l
    or (hl)
    jr nz,.found
    inc l
    djnz .quad
    ret
.found:
    dec l
    dec l
    dec l
    push bc
    ld b,4
.four:
    ld a,(hl)
    or a
    call nz,.cells
    inc l
    djnz .four
    pop bc
    djnz .quad
    ret
.cells:
    ld (hl),0
    push bc
    push hl
    ld c,a                      ; cells to do
    ld a,l
    add a,a
    add a,a
    add a,a
    ld b,a                      ; low byte of the byte's first cell ((L & 31) * 8)
.bit:
    ld h,lsb_index>>8           ; next set bit, lowest first
    ld l,c
    ld a,(hl)
    add a,b
    ld e,a                      ; the cell
    ld l,a
.nm:
    ld h,0
    ld l,(hl)                   ; its tile
.srca:
    ld h,0
    ld a,(hl)                   ; attribute
    or a
    jp m,.conv
.att:
    ld d,0
    ld (de),a
    inc l
    dec l
    jr z,.blank                 ; character 0
.src:
    ld h,0
.dst:
    ld d,0
    ld a,(hl)
    ld (de),a
    inc h
    inc d
    ld a,(hl)
    ld (de),a
    inc h
    inc d
    ld a,(hl)
    ld (de),a
    inc h
    inc d
    ld a,(hl)
    ld (de),a
    inc h
    inc d
    ld a,(hl)
    ld (de),a
    inc h
    inc d
    ld a,(hl)
    ld (de),a
    inc h
    inc d
    ld a,(hl)
    ld (de),a
    inc h
    inc d
    ld a,(hl)
    ld (de),a
    ld a,c
    dec a
    and c
    ld c,a
    jp nz,.bit
    pop hl
    pop bc
    ret
.blank:
.bdst:
    ld d,0
    xor a
    ld (de),a
    inc d
    ld (de),a
    inc d
    ld (de),a
    inc d
    ld (de),a
    inc d
    ld (de),a
    inc d
    ld (de),a
    inc d
    ld (de),a
    inc d
    ld (de),a
    ld a,c
    dec a
    and c
    ld c,a
    jp nz,.bit
    pop hl
    pop bc
    ret
.conv:
    push de
    ld e,l
    ld a,(dc_third)
    ld d,a
    call ensure_tile
    pop de
    res 7,(hl)
    ld a,(hl)
    jp .att
    endif
    NX_AT 0x8E12


; ---------------------------------------------------------------------------
; The star layer.  When the map scrolls, every star (tile F6/F7 on empty
; tile 0) moves a cell, and redrawing both cells of each, on both screens,
; is most of the scroll's drawing.  The three tiles differ only in row 0 and
; the attribute (star_check), so the full comparison leaves those changes
; out of the dirty bitmaps, and draw_stars instead writes row 0 and the
; attribute of tile 0 over the stars this screen showed (drawn lists,
; DRAWN) and those of F6/F7 at every star now (the star lists).
stars_moved: db 0               ; bit 0: screen 0's stars moved (draw them), bit 1: screen 1's
stars_listed: db 0              ; the same, but drawn whole: only the drawn lists need them
star_ok:    db 0                ; set by star_check: the full comparison may leave stars out
star_stale: db 1                ; a tile changed or was converted: check again
star_off:   db 0                ; a star list overflowed once: stars are plain cells from then on

    ifndef NEXT                 ; (the 128K's renderer, to the end of this file: not in the Next build)
; From render_frame (page 7, after erase_sprites): bring this screen's stars
; up to date if the star lists changed since it was last drawn.
draw_stars:
    ld a,(r_dirty)
    rlca
    inc a                       ; this screen's bit: 1 or 2
    ld b,a
    cpl
    ld c,a
    ld hl,stars_listed
    ld a,(hl)
    and b
    ld e,a                      ; nonzero: the drawn lists need the star lists
    ld a,(hl)
    and c
    ld (hl),a
    ld hl,stars_moved
    ld a,(hl)
    and b
    jr nz,.moved
    or e
    ret z
    ld a,(star_off)
    or a
    ret nz
    ld a,(star_dirty)
    or a
    call nz,star_rebuild
    ld a,(star_ovf)
    or a
    jp nz,.off
    jp .copy
.moved:
    ld a,(hl)
    and c
    ld (hl),a
    ld a,(star_off)
    or a
    ret nz
    ld a,(star_dirty)
    or a
    call nz,star_rebuild
    ld a,(star_ovf)
    or a
    jp nz,.off
    push ix
    ld a,(r_dirty)
    rlca
    and 1
    ld c,a
    add a,DRAWN>>8
    ld (.dhi),a
    ld a,c
    add a,a
    add a,a
    add a,drawn_n&0xff
    ld (.dn),a                  ; low byte of this screen's drawn_n
    xor a
    call .third
    ld a,1
    call .third
    ld a,2
    call .third
    pop ix
    ret
.copy:                          ; drawn lists := star lists (the cells were drawn whole)
    ld a,(r_dirty)
    rlca
    and 1
    ld c,a
    add a,DRAWN>>8
    ld d,a
    ld a,c
    add a,a
    add a,a
    add a,drawn_n&0xff
    ld (.dn),a
    ld c,0                      ; third
.cthird:
    ld a,c
    add a,star_t80&0xff
    ld l,a
    ld h,star_t80>>8
    ld e,(hl)                   ; DE = this third's drawn list
    push de
    ld a,c
    add a,a                     ; list k = third * 2 (F6), then F7
    call .clist
    ld a,c
    add a,a
    inc a
    call .clist
    pop hl                      ; L = the list's start
    ld a,e
    sub l
    ld b,a                      ; count
    ld a,(.dn)
    add a,c
    ld l,a
    ld h,drawn_n>>8
    ld (hl),b
    inc c
    ld a,c
    cp 3
    jr nz,.cthird
    ret
.clist:                         ; append list A to DE
    ld l,a
    add a,star_n&0xff
    ld l,a
    ld h,star_n>>8
    ld a,(hl)
    or a
    ret z
    ld b,a
    ld a,l
    add a,star_base-star_n
    ld l,a
    ld l,(hl)
    ld h,star_l>>8
.cl:
    ld a,(hl)
    ld (de),a
    inc l
    inc e
    djnz .cl
    ret
.off:                           ; too many stars for the lists: plain cells from now on
    ld a,1
    ld (star_off),a
    ld (star_stale),a
    jp dirty_all
.third:
    ld (.t),a
    ld d,a
    add a,name_shadow>>8
    ld (.nm+1),a
    ld a,d
    add a,a
    add a,a
    add a,a
    ld e,a                      ; 8 * third
    add a,d
    add a,TILE_PAGES
    ld (.tsrc),a                ; the tile set's row 0 page for this third
    ld a,(r_scr_hi)
    add a,e
    ld (.epix+1),a
    ld (.dpix+1),a
    ld a,(r_scr_hi)
    add a,0x18
    add a,d
    ld (.eatt+1),a
    ld (.datt+1),a
    ld e,0
    call .fetch
    ld a,b
    ld (.erow+1),a
    ld a,c
    ld (.eav+1),a
    ; erase what this screen showed (cells still empty or a star)
    ld a,(.dn)
    ld l,a
    ld a,(.t)
    add a,l
    ld l,a
    ld h,drawn_n>>8
    ld b,(hl)
    ld a,b
    or a
    jr z,.draw
    ld a,(.t)
    ld l,a
    ld h,star_t80>>8
    ld a,l
    add a,star_t80&0xff
    ld l,a
    ld l,(hl)
    ld a,(.dhi)
    ld h,a
.el:
    ld e,(hl)
    inc l
.nm:
    ld d,0
    ld a,(de)
    or a
    jr z,.ew
    sub 0xf6
    cp 2
    jr nc,.en
.ew:
.epix:
    ld d,0
.erow:
    ld a,0
    ld (de),a
.eatt:
    ld d,0
.eav:
    ld a,0
    ld (de),a
.en:
    djnz .el
.draw:
    ; draw the stars now, noting them in the drawn list
    ld a,(.t)
    ld l,a
    ld h,star_t80>>8
    ld a,l
    add a,star_t80&0xff
    ld l,a
    ld a,(hl)
    ld (.dstart),a
    ld c,a
    ld a,(.dhi)
    ld b,a                      ; BC = drawn list write pointer
    ld e,0xf6
    call .tile
    ld e,0xf7
    call .tile
    ld a,(.dn)
    ld l,a
    ld a,(.t)
    add a,l
    ld l,a
    ld h,drawn_n>>8
    ld a,(.dstart)
    cpl
    inc a
    add a,c
    ld (hl),a
    ret
.tile:                          ; E = F6 or F7
    ld a,(.t)
    add a,a
    add a,e
    sub 0xf6
    ld l,a                      ; list k = third * 2 + (tile - F6)
    ld h,star_n>>8
    add a,star_n&0xff
    ld l,a
    ld a,(hl)
    or a
    ret z
    ld (.cnt),a
    ld a,l
    add a,star_base-star_n
    ld l,a
    ld a,(hl)
    ld (.lst),a
    push bc
    call .fetch                 ; (may convert the tile: IX is not kept)
    ld a,b
    ld (.drow+1),a
    ld a,c
    ld (.dav+1),a
    pop bc
    ld a,(.cnt)
    ld ixh,a
    ld a,(.lst)
    ld l,a
    ld h,star_l>>8
.dl:
    ld e,(hl)
    inc l
.dpix:
    ld d,0
.drow:
    ld a,0
    ld (de),a
.datt:
    ld d,0
.dav:
    ld a,0
    ld (de),a
    ld a,e
    ld (bc),a
    inc c
    dec ixh
    jr nz,.dl
    ret
.fetch:                         ; tile E of this third: B = row 0, C = attribute (converted)
    push hl
    push de
    ld a,(.tsrc)
    add a,8
    ld h,a
    ld l,e
    bit 7,(hl)
    jr z,.conv
    push hl
    ld a,(.t)
    ld d,a
    call ensure_tile
    pop hl
    res 7,(hl)
.conv:
    ld c,(hl)
    ld a,(.tsrc)
    ld h,a
    ld b,(hl)
    pop de
    pop hl
    ret
.t:     db 0
.dhi:   db 0
.dn:    db 0
.tsrc:  db 0
.lst:   db 0
.cnt:   db 0
.dstart: db 0
    assert (star_n >> 8) == ((star_n + 5) >> 8) && (star_l >> 8) == (star_base >> 8)

dc_third:   db 0

; ---------------------------------------------------------------------------
; Konami's sprite buffer: 32 x [Y, X, pattern, colour]; Y = 0xD0 ends the list.
sp_x:       db 0                ; (spr_edge's: 0 or 240)
sp_y:       db 0
sp_ink:     db 0
sp_cx:      db 0                ; the box of cells the sprite's pixels reach:
sp_cy:      db 0                ; its first column and row,
sp_cols:    db 0                ; columns (1-3)
sp_rows:    db 0                ; and rows (1-3)
; Each sprite pattern's extent (1.1.2; used for the drawing too since 1.2):
; sp_ext (plat_spec.asm, page-aligned) holds, for each of Konami's 64
; patterns (bank 7, F800 + n * 32) at sp_ext + n * 4 and for the ship's three
; frames (ship_pat) from sp_exts = sp_ext + 256, [first row with pixels
; (FF: none), last row, leftmost pixel 0-15, rightmost pixel].  draw_sprite16
; draws only the rows from the first to the last, and colours and marks only
; the cells the pixels reach at the sprite's position.  Worked out again at
; the first drawing after a graphics load (nl_done sets spx_stale).
; NEM_TRIM=0: every extent is the whole pattern (the boxes of 1.1.1), fixed.
    ifdef TRIM
spx_stale:  db 1
sp_tmp:     db 0

; The extents of every pattern (page 7 in).
sp_calc:
    xor a
    ld (spx_stale),a
    push ix
    ld hl,SPR_PAT
    ld de,sp_ext
    ld b,64
.p:
    call .one
    djnz .p
    ld hl,ship_pat
    ld b,3
.s:
    call .one
    djnz .s
    pop ix
    ret
.one:                           ; HL = a pattern, DE = its entry; both stepped on
    push bc
    push de
    ld bc,0x00FF                ; B last row, C first (FF: none yet)
    ld ix,0                     ; IXH, IXL: OR of the left, right columns
    ld d,0
.r:
    set 4,l
    ld a,(hl)                   ; right
    res 4,l
    ld e,(hl)                   ; left
    inc l
    ld (sp_tmp),a
    or e
    jr z,.e
    ld a,c
    inc a
    jr nz,.nf
    ld c,d
.nf:
    ld b,d
    ld a,ixh
    or e
    ld ixh,a
    ld a,(sp_tmp)
    or ixl
    ld ixl,a
.e:
    inc d
    ld a,d
    cp 16
    jr nz,.r
    ld de,16
    add hl,de
    pop de
    ld a,c
    ld (de),a
    inc de
    ld a,b
    ld (de),a
    inc de
    push hl
    push ix
    pop hl                      ; the 16 columns that have pixels, the leftmost in bit 15
    ld a,h
    or l
    jr z,.z                     ; (no pixels: the rest of the entry is not read)
    push hl
    ld b,0xff
.lm:
    inc b
    add hl,hl
    jr nc,.lm
    pop hl
    ld c,16
.rm:
    dec c
    srl h
    rr l
    jr nc,.rm
    ld a,b
    ld (de),a                   ; the leftmost pixel
    inc de
    ld a,c
    ld (de),a                   ; the rightmost
    inc de
    pop hl
    pop bc
    ret
.z:
    inc de
    inc de
    pop hl
    pop bc
    ret
    endif

draw_sprites:
    ifdef TRIM
    ld a,(spx_stale)
    or a
    call nz,sp_calc
    endif
    ld a,(spr_on)               ; Konami hid them all (a 0xD0 at VRAM 3B00)
    or a
    ret z
    ; one pass (0.109): the entries on screen, up to the end marker, into
    ; spr_vis; then they are drawn from the last to the first, so that on
    ; shared cells the higher-priority (earlier) sprite's colour wins.
    ; Konami's list is usually full, with most entries parked below the screen.
    ld hl,SPR_ATTR
    ld de,spr_vis
    ld b,32
.scan:
    ld a,(hl)
    inc a                       ; the TMS9918 shows a sprite one line below Y
    cp 177
    jr c,.vis
    cp 0xd1                     ; the end marker (0xD0)
    jr z,.scanned
.skip:
    ld a,l
    add a,4
    ld l,a
    djnz .scan
.scanned:
    ld a,e
    sub spr_vis&0xff
    ret z
    ld b,a                      ; sprites on screen
    jr .spr
.vis:                           ; on screen (above the top: not clipped yet)
    ld a,l
    ld (de),a
    inc e
    jr .skip
.spr:
    ld a,b
    add a,(spr_vis&0xff)-1
    ld l,a
    ld h,spr_vis>>8
    ld l,(hl)
    ld h,SPR_ATTR>>8
    ld a,(hl)
    inc a
    ld (sp_y),a
    inc l
    ld e,(hl)                   ; X
    inc l
    ld a,(hl)                   ; pattern: 4-7, 12-15, 20-23 are the ship's
    ld d,a
    cp 24                       ; second colour, never drawn (ship.asm), so
    jr nc,.drawn                ; not worth a colour either (0.109)
    and 4
    jr nz,.next
.drawn:
    inc l
    ld c,(hl)                   ; colour, and the early clock in bit 7
    ld a,c
    and 15
    jr z,.next                  ; transparent
    push bc
    ld b,a
    ; The sprite's ink (1.2: here, out of bank 7's contended memory):
    ; spr_ink[colour], unless spr_pmap (page 7; two bytes for each pattern)
    ; gives this pattern its own ink when it has that MSX colour (or any, for
    ; 0x10), or flags it (0x20: bit 7 of sp_ink) for attrs_keep.
    ld a,d
    rrca
    and 0x7e
    or spr_pmap&0xff
    ld l,a
    ld h,spr_pmap>>8
    ld a,(hl)
    cp b
    jr z,.own
    cp 0x10                     ; 0x10: whatever its MSX colour
    jr z,.own
    sub 0x20                    ; 0x20: the usual ink, flagged for attrs_keep
    ld h,0x80
    jr z,.map
    ld h,0
.map:
    ld l,b
    ld a,h
    ld h,spr_ink>>8
    or (hl)
    jr .set
.own:
    inc l
    ld a,(hl)
.set:
    ld (sp_ink),a
    ld a,e                      ; X
    bit 7,c                     ; early clock: 32 pixels to the left
    jr z,.x
    sub 32
    jp c,spr_edge               ; partly off the left edge (or wholly)
.x:
    cp 241
    jp nc,spr_edge              ; partly off the right edge
    call draw_sprite16
    pop bc
.next:                          ; (spr_edge comes back here, with BC popped)
    djnz .spr
    ret
    assert (spr_ink & 0xff) == 0

    macro SPR_ADDR              ; DE = the hidden screen's byte for line B, column C
    ld a,b
    and 0xc0
    rrca
    rrca
    rrca
    ld d,a
    ld a,b
    and 7
    or d
    ld d,a
    ld a,(r_scr_hi)
    or d
    ld d,a
    ld a,b
    and 0x38
    add a,a
    add a,a
    or c
    ld e,a
    endm

; OR a 16x16 sprite (TMS layout: left column bytes 0-15, right 16-31) into
; the hidden screen at (A, sp_y), A = X (0-240), D = its pattern number as
; Konami's list has it; colour its cells with sp_ink, and mark them in this
; screen's dirty bitmap.
draw_sprite16:
    ld ixh,a                    ; X
    and 7
    ld c,a                      ; its offset in the cell
    ld a,d
    and 0xfc
    ld d,a
    cp 24
    jr nc,.kext
    rrca                        ; the ship's (0, 8, 16): its extent at sp_exts + 0, 4, 8
    add a,sp_exts&0xff
    ld l,a
    ld h,sp_exts>>8
    jr .ext
.kext:
    ld l,a                      ; Konami's: its extent at sp_ext + pattern
    ld h,sp_ext>>8
.ext:
    ld a,(hl)                   ; first row with pixels
    cp 0xff
    ret z                       ; none: nothing to draw, colour or mark
    ld b,a
    inc l
    ld a,(hl)                   ; last row with pixels
    sub b
    inc a
    ld ixl,a                    ; rows to draw
    inc l
    ld a,(hl)                   ; leftmost pixel
    add a,c
    rrca
    rrca
    rrca
    and 3
    ld e,a                      ; the first column with pixels: 0-2
    inc l
    ld a,(hl)                   ; rightmost pixel
    add a,c
    rrca
    rrca
    rrca
    and 3
    sub e
    inc a
    ld (sp_cols),a
    ld a,ixh
    rrca
    rrca
    rrca
    and 31
    ld c,a                      ; the column drawn from
    add a,e
    ld (sp_cx),a
    ld a,(sp_y)
    add a,b
    ld e,a                      ; the first row's line
    rrca
    rrca
    rrca
    and 31
    ld (sp_cy),a
    ld h,a
    ld a,ixl
    add a,e
    dec a                       ; the last row's line
    rrca
    rrca
    rrca
    and 31
    sub h
    inc a
    ld (sp_rows),a
    ld a,d                      ; the pattern's bytes, from its first row with pixels
    cp 24
    jr nc,.kpat
    add a,a
    add a,a                     ; the ship's: ship_pat + pattern * 4
    add a,b
    add a,ship_pat&0xff
    ld l,a
    ld h,ship_pat>>8
    jr .pat
.kpat:
    ld l,a                      ; Konami's: SPR_PAT + pattern * 8
    ld h,SPR_PAT>>11
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,l
    add a,b
    ld l,a
.pat:
    ld b,e
    ld a,ixh
    and 7
    jr z,.c0                    ; on a cell boundary: no shifting
    ; shift entry: .shift_end - 5 * s for s 1-4; for s 5-7 the sprite is
    ; shifted left by 8 - s instead, into the same three bytes (.lrow)
    cp 5
    jr nc,.lset
    ld e,a
    add a,a
    add a,a
    add a,e
    neg
    add a,.shift_end&0xff
    ld (.shift_jump+1),a
    SPR_ADDR
    jp .row
.lset:
    neg
    add a,8
    ld e,a
    add a,a
    add a,a
    add a,e
    neg
    add a,.lshift_end&0xff
    ld (.lshift_jump+1),a
    SPR_ADDR
    jp .lrow
; spr_edge comes in here: HL = edge_pat (all 16 rows, no shift), B = columns
; to colour (sp_cx set), C = the column drawn from.
.cols:
    ld a,b
    ld (sp_cols),a
    ld a,(sp_y)
    ld b,a
    rrca
    rrca
    rrca
    and 31
    ld (sp_cy),a
    ld a,b
    and 7
    ld a,2
    jr z,.erows
    inc a
.erows:
    ld (sp_rows),a
    ld ixl,16
.c0:
    SPR_ADDR
    jp .row0
.row:
    ld b,(hl)
    set 4,l
    ld c,(hl)
    res 4,l
    inc l
    ld a,b
    or c
    jr z,.next                  ; an empty row
    xor a
.shift_jump:
    jp .shift_end
    srl b
    rr c
    rra
    srl b
    rr c
    rra
    srl b
    rr c
    rra
    srl b
    rr c
    rra
.shift_end:
    ex af,af'
    ld a,(de)
    or b
    ld (de),a
    inc e
    ld a,(de)
    or c
    ld (de),a
    inc e
    ex af,af'
    ld b,a
    ld a,(de)
    or b
    ld (de),a
    dec e
    dec e
.next:
    inc d                       ; next screen line
    ld a,d
    and 7
    jr nz,.line_ok
    ld a,e
    add a,32
    ld e,a
    jr c,.line_ok
    ld a,d
    sub 8
    ld d,a
.line_ok:
    dec ixl
    jp nz,.row
    jr .attrs
.lrow:                          ; shifts 5-7: left by 8 - s, overflow into A
    ld b,(hl)
    set 4,l
    ld c,(hl)
    res 4,l
    inc l
    ld a,b
    or c
    jr z,.lnext                 ; an empty row
    xor a
.lshift_jump:
    jp .lshift_end
    sla c
    rl b
    rla
    sla c
    rl b
    rla
    sla c
    rl b
    rla
.lshift_end:
    ex de,hl
    or (hl)
    ld (hl),a
    inc l
    ld a,b
    or (hl)
    ld (hl),a
    inc l
    ld a,c
    or (hl)
    ld (hl),a
    dec l
    dec l
    ex de,hl
.lnext:
    inc d                       ; next screen line
    ld a,d
    and 7
    jr nz,.lline_ok
    ld a,e
    add a,32
    ld e,a
    jr c,.lline_ok
    ld a,d
    sub 8
    ld d,a
.lline_ok:
    dec ixl
    jp nz,.lrow
    jp .attrs
.row0:                          ; on a cell boundary: two bytes, no shifting
    ld b,(hl)
    set 4,l
    ld c,(hl)
    res 4,l
    inc l
    ld a,b
    or c
    jr z,.next0
    ld a,(de)
    or b
    ld (de),a
    inc e
    ld a,(de)
    or c
    ld (de),a
    dec e
.next0:
    inc d
    ld a,d
    and 7
    jr nz,.ok0
    ld a,e
    add a,32
    ld e,a
    jr c,.ok0
    ld a,d
    sub 8
    ld d,a
.ok0:
    dec ixl
    jp nz,.row0
.attrs:
    ; attributes: ink = sprite colour
    ld a,(sp_cy)
    ld b,a
    rrca
    rrca
    rrca
    and 3
    add a,0x18
    ld d,a
    ld a,(r_scr_hi)
    add a,d
    ld d,a
    ld a,b
    and 7
    rrca
    rrca
    rrca
    ld e,a
    ld a,(sp_cx)
    or e
    ld e,a
    ld a,(sp_ink)
    or a
    jp m,attrs_keep             ; flagged (the missile): terrain keeps its colours (page 7)
    and 7
    ld l,a                      ; the sprite's ink without its bright
    ld a,(sp_rows)
    ld c,a
.arow:
    ld a,(sp_cols)
    ld b,a
    push de
.acol:
    ld a,(de)
    and 0x38
    jr z,.ablack                ; black paper: the sprite's ink and bright
    ld a,(de)                   ; coloured paper (solid terrain): keep its
    and 0x78                    ; paper and bright, so only the ink changes
    or l
    jr .aput
.ablack:
    ld a,(sp_ink)
.aput:
    ld (de),a
    inc e
    djnz .acol
    pop de
    ld a,e
    add a,32
    ld e,a
    jr nc,.anc
    inc d
.anc:
    dec c
    jr nz,.arow
    ; The box's cells in this screen's dirty bitmap (attrs_keep comes back
    ; here): draw_cells has had this picture's bits, so they wait for this
    ; screen's next picture, which draws the cells again without the sprite.
    ; (1.2; until then each screen kept a list of boxes for erase_sprites
    ; to mark at its next picture.)  The columns, as bits (bit cx & 7 of byte
    ; cy * 4 + cx / 8), are one mask for every row, which may run into the
    ; next byte (never past column 31, so never into the next row's).
.arec:
    ld a,(sp_cx)
    ld c,a
    and 7
    add a,a
    ld e,a
    ld a,(sp_cols)
    dec a
    add a,a
    add a,a
    add a,a
    add a,a
    or e
    add a,sp_mask&0xff
    ld l,a
    ld h,sp_mask>>8
    ld d,(hl)                   ; the columns' bits in the first byte,
    inc l
    ld e,(hl)                   ; and in the next
    ld a,(sp_cy)
    add a,a
    add a,a
    ld l,a
    ld a,c
    rrca
    rrca
    rrca
    and 3
    or l
    ld l,a
    ld a,(r_dirty)
    or l
    ld l,a
    ld h,dirty0>>8
    ld a,(sp_rows)
    ld b,a
    ld a,e
    or a
    jr z,.m1
.m2:
    ld a,(hl)
    or d
    ld (hl),a
    inc l
    ld a,(hl)
    or e
    ld (hl),a
    inc l
    inc l
    inc l
    djnz .m2
    ret
.m1:
    ld a,(hl)
    or d
    ld (hl),a
    ld a,l
    add a,4
    ld l,a
    djnz .m1
    ret
    assert ((.shift_end - 20) >> 8) == (.shift_end >> 8) && ((.lshift_end - 15) >> 8) == (.lshift_end >> 8)
    assert (ship_pat & 0xff) + 96 <= 256 && (sp_exts & 0xff) <= 0xf4 && (sp_ext & 0xff) == 0
    else
    NX_AT 0x8FF8
draw_sprites:                   ; (nx_low.asm's lo_draw, itself never called, still names it)
    endif
