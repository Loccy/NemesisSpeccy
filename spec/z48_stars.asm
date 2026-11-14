; The 48K's stars: F6 and F7 are plain tiles, drawn by draw_cells like any
; other.  On the MSX their row 0 changes every tick (E062's rotating bit:
; the star's pixel moving across its cell, blink_native below); z48_stars
; writes that row at every star cell (star_cells) of a third whose F6 or F7
; row changed since it last did.  A tile first lit (its attribute set) has
; the third's star cells drawn whole instead.  This replaces the 128K's star
; lists, drawn lists, row carrying and star_check (some 1.5K): every star
; that appears or goes is a cell redrawn whole, as any other tile change.

z48_sv:     ds 6                ; [third][F6/F7]: row 0 as last written

z48_stars:
    ld c,0                      ; third
.th:
    ld a,c
    add a,a
    add a,STAR048
    ld l,a                      ; the third's F6 tile (group 0)
    ld h,TG48+1                 ; row 0
    ld d,(hl)                   ; F6's row 0
    inc l
    ld e,(hl)                   ; F7's
    ld a,c
    add a,a
    add a,z48_sv&0xff
    ld l,a
    ld h,z48_sv>>8
    ld a,(hl)
    cp d
    jr nz,.ch
    inc l
    ld a,(hl)
    cp e
    jr z,.nx
    dec l
.ch:
    ld (hl),d
    inc l
    ld (hl),e
    push bc
    call .draw
    pop bc
.nx:
    inc c
    ld a,c
    cp 3
    jr nz,.th
    ret
.draw:                          ; third C: row 0 (D for F6, E for F7) at its star cells
    ld a,c
    add a,name_shadow>>8
    ld (.nmp+1),a
    ld a,c
    add a,a
    add a,a
    add a,a
    add a,0x40
    ld (.scr+1),a               ; row 0 of a cell: (40 + third * 8) << 8 | cell
    ld a,c
    rrca
    rrca
    rrca                        ; third * 32
    add a,star_cells&0xff
    ld l,a
    ld h,star_cells>>8
    ld b,32
.byte:
    ld a,(hl)
    or a
    jr nz,.cells
.nb:
    inc l
    djnz .byte
    ret
.cells:
    push bc
    push hl
    ld c,a                      ; its bits
    ld a,l
    sub star_cells&0xff
    and 31
    add a,a
    add a,a
    add a,a
    ld b,a                      ; the byte's first cell
.bit:
    ld h,lsb_index>>8
    ld l,c
    ld a,(hl)
    add a,b
    ld l,a                      ; the cell
.nmp:
    ld h,0
    ld a,(hl)
    cp 0xf6
    jr z,.s6
    cp 0xf7
    jr nz,.nxb
    ld a,e
    jr .w
.s6:
    ld a,d
.w:
.scr:
    ld h,0
    ld (hl),a
.nxb:
    ld a,c
    dec a
    and c
    ld c,a
    jr nz,.bit
    pop hl
    pop bc
    jr .nb
    assert (z48_sv >> 8) == ((z48_sv + 5) >> 8)

; Konami's 0:475B (each tick): F6's and F7's row 0 in every third from E062
; and the blink masks, as the MSX has them.  A tile still unlit since the
; load (ink = paper) is lit when its row first has a pixel: its attribute
; from star_attr, and the third's star cells drawn whole.
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
    push bc                     ; (as the original leaves them, at the end)
    ld a,(0xE062+KRAM)
    ld e,a
    and c
    ld (bl_v6),a
    ld a,e
    and b
    ld (bl_v7),a
    ld hl,bl_prev               ; [third][F6/F7]; star_attr follows
    ld de,(TG48 << 8) | STAR048 ; the star tiles: group 0, 8 to 13
.t:
    ld a,(bl_v6)
    bit 0,e                     ; F6 even, F7 odd
    jr z,.v
    ld a,(bl_v7)
.v:
    cp (hl)
    jr z,.next
    ld (hl),a
    ld c,a                      ; the row
    ld a,(de)                   ; the attribute
    ld b,a
    rrca
    rrca
    rrca
    xor b
    and 7
    jr nz,.row                  ; lit already: the row alone
    ld a,c
    or a
    jr z,.next                  ; still blank
    push hl
    push bc
    ld bc,6
    add hl,bc
    ld a,(hl)                   ; star_attr[third][F6/F7]
    ld (de),a
    push de
    ld a,e
    sub STAR048
    srl a                       ; the third
    call z48_star_dirty
    pop de
    pop bc
    pop hl
.row:
    inc d                       ; row 0
    ld a,c
    ld (de),a
    dec d
.next:
    inc hl
    inc e
    ld a,e
    cp STAR048+6
    jr nz,.t
    pop bc
    ld c,b
    ld hl,0x37B9
    ld (vdp_addr),hl
    dec hl
    ld de,0x0800
    ret
    assert bl_prev + 6 == star_attr

; A = the third: its star cells into dirty0, to be drawn whole.
z48_star_dirty:
    rrca
    rrca
    rrca                        ; third * 32
    ld l,a
    add a,star_cells&0xff
    ld e,a
    ld d,star_cells>>8
    ld h,dirty0>>8
    ld b,32
.o:
    ld a,(de)
    or (hl)
    ld (hl),a
    inc e
    inc l
    djnz .o
    ret

; ---------------------------------------------------------------------------
; The 48K's sprites never leave the screen for long.  On one screen, drawn
; as it is shown, the 128K's order (every changed cell, then every sprite)
; would leave each sprite off the screen for most of the picture.  Instead
; each sprite's cells that need drawing (dirty0) are drawn just before the
; sprite itself (z48_box, from draw_sprite16 once it has the sprite's box),
; and taken out of dirty0; draw_cells then does the rest, the cells where
; sprites were, after the sprites are up in their new places.  A sprite's
; cells wait in dirty1 for the next picture (z48_dnext adds them to dirty0).

; The box (sp_cx, sp_cy, sp_cols, sp_rows), as draw_sprite16 starts on it:
; its first cell row's dirty cells drawn.  Each later row's are drawn as the
; sprite's lines reach it (z48_next_row, from draw_sprite16's line step), so
; that the cells are without the sprite only while the sprite's own lines
; in that row are being drawn.
z48_rn:     db 0                ; box rows still to draw after this one
z48_rr:     db 0                ; the row being drawn
z48_box:
    ifdef Z48_TWOPASS
    ret
    endif
    push af
    ld a,(sp_rows)
    dec a
    ld (z48_rn),a
    ld a,(sp_cy)
    ld (z48_rr),a
    jr z48_brow
z48_next_row:
    ifdef Z48_TWOPASS
    ret
    endif
    push af
    ld a,(z48_rn)
    or a
    jr z,.done
    dec a
    ld (z48_rn),a
    ld a,(z48_rr)
    inc a
    ld (z48_rr),a
    jr z48_brow
.done:
    pop af
    ret
z48_brow:                       ; (AF pushed) cell row z48_rr, columns sp_cx on
    push bc
    push de
    push hl
    ld a,(z48_rr)
    ld c,a                      ; row
    ld a,(sp_cx)
    ld e,a                      ; column
    ld a,(sp_cols)
    ld b,a
.col:
    push bc
    push de
    ; dirty0 bit: byte row * 4 + column / 8, bit column & 7
    ld a,e
    and 7
    ld l,a
    ld h,bitmask>>8
    ld d,(hl)
    ld a,c
    add a,a
    add a,a
    ld l,a
    ld a,e
    rrca
    rrca
    rrca
    and 3
    or l
    ld l,a
    ld h,dirty0>>8
    ld a,(hl)
    and d
    jr z,.clean
    ld a,d
    cpl
    and (hl)
    ld (hl),a
    ld a,c                      ; the cell: third = row / 8, low = (row & 7) * 32 + column
    rrca
    rrca
    rrca
    and 0xE0
    or e
    ld l,a
    ld a,c
    rrca
    rrca
    rrca
    and 3
    call z48_cell
.clean:
    pop de
    pop bc
    inc e
    djnz .col
    pop hl
    pop de
    pop bc
    pop af
    ret

; Draw cell L of third A from its tile, as draw_cells does.
z48_cell:
    ld b,a
    add a,name_shadow>>8
    ld h,a
    ld e,(hl)                   ; the character
    ld a,b
    add a,0x58
    ld d,a                      ; the attribute's address: D, L
    ld a,b
    add a,a
    add a,a
    add a,a
    ld c,a                      ; 8 * third
    ld a,b
    add a,a
    add a,IDX48
    ld h,a                      ; the third's index
    ld a,l
    ld l,e
    ld e,a                      ; DE = the attribute's address, L = the character
    ld a,(hl)
    inc h
    ld h,(hl)                   ; the tile's group: its attribute page
    ld l,a
    ld a,(hl)
.att:
    ld (de),a
    inc h                       ; row 0's page
    ld a,c
    add a,0x40
    ld d,a
    ld b,8
.r:
    ld a,(hl)
    ld (de),a
    inc h
    inc d
    djnz .r
    ret

; After a picture: the cells its sprites cover, for the next one.
z48_dnext:
    ld hl,dirty1
    ld b,96
.m:
    ld a,(hl)
    or a
    jr nz,.add
    inc l
    djnz .m
    ret
.add:
    ld (hl),0
    res 7,l                     ; dirty0 = dirty1 - 0x80
    or (hl)
    ld (hl),a
    set 7,l
    inc l
    djnz .m
    ret
    assert dirty1 == dirty0 + 0x80 && (dirty0 & 0xff) == 0

    ifdef Z48_ROWS
; ---------------------------------------------------------------------------
; A trial (Z48_ROWS, 1.3): the picture in screen order, a cell row at a time
; (in each row the sprites whose top is there, with their cells, then the
; row's other dirty cells), to race the beam.  Measured (measure48.py) it is
; slower than the order above (a render of 44,000 T-states against 30,000)
; and no better for flicker, with or without starting at an interrupt: the
; drawing goes down the screen at about the beam's own speed, so the beam
; rides along with it.  Kept for later experiments.

z48_vis:    ds 32               ; the sprites on screen (their SPR_ATTR low bytes)
z48_head:   ds 24               ; per cell row: the first of its sprites (0xFF: none)
z48_next:   ds 32               ; per sprite: the next in its row
z48_ct:     db 0                ; draw_cells' patched third (0xFF: none yet)
z48_nvis:   db 0

z48_draw:
    push ix
    ifdef TRIM
    ld a,(spx_stale)
    or a
    call nz,sp_calc
    endif
    ld a,0xff
    ld (z48_ct),a
    ld hl,z48_head
    ld b,24
.h:
    ld (hl),a
    inc hl
    djnz .h
    ld de,z48_vis
    ld a,(spr_on)               ; Konami hid them all (a 0xD0 at VRAM 3B00)
    or a
    jr z,.scanned
    ld hl,SPR_ATTR
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
    jr .scanned
.vis:
    ld a,l
    ld (de),a
    inc de
    jr .skip
.scanned:
    ld a,e
    sub z48_vis&0xff
    ld (z48_nvis),a
    ; each into its row's list (first to last, so that each list runs from
    ; the last to the first: draw_sprites' order, the earlier on top)
    ld c,0
.bk:
    ld a,(z48_nvis)
    cp c
    jr z,.rows
    ld hl,z48_vis
    ld b,0
    add hl,bc
    ld l,(hl)
    ld h,SPR_ATTR>>8
    ld a,(hl)
    inc a
    rrca
    rrca
    rrca
    and 31                      ; its cell row
    ld e,a
    ld d,0
    ld hl,z48_head
    add hl,de
    ld a,(hl)
    ld (hl),c
    ld hl,z48_next
    add hl,bc
    ld (hl),a
    inc c
    jr .bk
.rows:
    ld c,0
.r:
    ld hl,z48_head
    ld b,0
    add hl,bc
    ld a,(hl)
.s:
    cp 0xff
    jr z,.cells
    push bc
    push af
    ld e,a
    ld d,0
    ld hl,z48_vis
    add hl,de
    ld a,(hl)
    ld (spr_vis),a              ; a one-sprite list for draw_sprites' loop
    ld b,1
    call draw_sprites.spr
    pop af
    ld e,a
    ld d,0
    ld hl,z48_next
    add hl,de
    ld a,(hl)
    pop bc
    jr .s
.cells:
    ld a,c
    call z48_row_cells
    inc c
    ld a,c
    cp 24
    jr nz,.r
    pop ix
    ret

; Cell row A's dirty cells (dirty0 bytes row * 4 to + 3), by draw_cells'
; code, its pages patched for the row's third when the third changes.
z48_row_cells:
    push bc
    ld c,a
    rrca
    rrca
    rrca
    and 3
    ld hl,z48_ct
    cp (hl)
    jr z,.same
    ld (hl),a
    ld d,a
    ld (dc_third),a
    add a,name_shadow>>8
    ld (draw_cells.nm+1),a
    ld a,d
    add a,a
    add a,a
    add a,a
    ld e,a                      ; 8 * third
    ld a,d
    add a,a
    add a,IDX48
    ld (draw_cells.ix+1),a      ; the third's index page
    ld a,(r_scr_hi)
    add a,e
    ld (draw_cells.dst+1),a
    ld (draw_cells.bdst+1),a
    ld a,(r_scr_hi)
    add a,0x18
    add a,d
    ld (draw_cells.att+1),a
.same:
    ld a,c
    add a,a
    add a,a
    ld l,a
    ld h,dirty0>>8
    ld b,4
.b:
    ld a,(hl)
    or a
    call nz,draw_cells.cells
    inc l
    djnz .b
    pop bc
    ret
    endif

    ifdef Z48_VSYNC
; A trial (Z48_VSYNC, preview 5; declined: slower to play, no flicker
; benefit to the eye, on the user's machine): wait, by the floating bus (a read of port FF gives
; the byte the ULA is fetching for the screen, FF between fetches and in the
; border; an attribute is never FF here), until the beam has left the foot
; of the screen, so that the picture is drawn while the beam is in the
; border (120 lines, about 27,000 T-states).  wait_shown does not wait.  A
; machine without a floating bus (port FF always FF, or never) gives up
; after some 65,000 reads, a couple of seconds, once.
z48_nofb:   db 0                ; no floating bus seen: never wait again
z48_vsync:
    ld a,(z48_nofb)
    or a
    ret nz
    ld hl,0                     ; (a frame is about 2,000 turns of either loop:
.p:                             ; 65,536 without an answer, and there is none)
    dec hl
    ld a,h
    or l
    jr z,.none
    ld a,r                      ; (9 T-states: each loop must take an odd number,
    in a,(0xff)                 ; or its reads can lock onto the ULA's idle
    inc a                       ; T-states and find FF in the middle of the screen)
    jr z,.p
.paper:                         ; in the screen: until 10 reads in a row (650
.b:                             ; T-states, more than a line) find nothing
    ld b,10
.l:
    dec hl
    ld a,h
    or l
    jr z,.none
    ld a,r
    in a,(0xff)
    inc a
    jr nz,.b
    djnz .l
    ret
.none:                          ; port FF always FF (a +2A/+3) or never: no beam to follow
    ld a,1
    ld (z48_nofb),a
    ret
    endif

; ---------------------------------------------------------------------------
; The beeper (z48_sfx.py has the effects and which code plays which).  A
; request takes over unless the effect sounding outranks it; the interrupt
; plays a frame of it each time (z48_sfx_tick), some 2,000 T-states at most.
z48_sp:     dw 0                ; the sounding effect's next frame (0: none)
z48_spri:   db 0                ; its priority
z48_sfx:                        ; A = Konami's code (0-7F)
    ld e,a
    ld d,0
    ld hl,z48_sfx_code
    add hl,de
    ld a,(hl)
    or a
    ret z
    dec a
    ld e,a
    add a,a
    add a,e                     ; 3 bytes an effect
    ld e,a
    ld hl,z48_sfx_eff
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld a,(z48_sp+1)             ; (an effect's frames are never on page 0)
    or a
    jr z,.take
    ld a,(z48_spri)
    cp (hl)
    ret z                       ; (the same rank: the one sounding goes on)
    ret nc
.take:
    ld a,(hl)
    ld (z48_spri),a
    ld (z48_sp),de              ; (one instruction: safe from the interrupt)
    ret

z48_seed:   dw 0xACE1           ; the noise's LFSR
z48_sfx_tick:                   ; from the interrupt
    ld hl,(z48_sp)
    ld a,h
    or a
    ret z
    ld c,(hl)                   ; the period
    ld a,c
    or a
    jr z,.end
    inc hl
    ld b,(hl)                   ; half-cycles; bit 7: noise
    inc hl
    ld a,(hl)                   ; the sweep, at each half-cycle
    inc hl
    ld (z48_sp),hl
    ld (.dt+1),a
    ld (.dn+1),a
    ld a,b
    and 0x7f
    bit 7,b
    ld b,a
    ld e,0
    jr nz,.noise
.t:
    ld a,e
    xor 0x10
    ld e,a
    out (0xfe),a
    ld d,c
.d:
    dec d
    jr nz,.d
    ld a,c
.dt:
    add a,0
    ld c,a
    djnz .t
    xor a
    out (0xfe),a
    ret
.noise:
    ld hl,(z48_seed)
.n:
    add hl,hl                   ; a Galois LFSR (x^16 + x^5 + x^3 + x^2 + 1):
    jr nc,.n0                   ; the bit out moves the speaker
    ld a,l
    xor 0x2D
    ld l,a
    ld a,e
    xor 0x10
    ld e,a
.n0:
    ld a,e
    out (0xfe),a
    ld d,c
.nd:
    dec d
    jr nz,.nd
    ld a,c
.dn:
    add a,0
    ld c,a
    djnz .n
    ld (z48_seed),hl
    xor a
    out (0xfe),a
    ret
.end:
    ld h,a
    ld l,a
    ld (z48_sp),hl
    ret

    include "z48_sfx.asm"
