; Spectrum Next only: code and buffers in Next RAM mapped at 0000-3FFF
; (MMU0/MMU1 = 8K pages 16 and 17, the 16K bank 8 of the .NEX), set up by
; nx_init.  Assembled on its own after the main build, with the main build's
; symbols (nx_syms.inc, from nemesis_next.sym); the main build reaches it only
; through the jump table at 0100.
;
; Smooth scrolling (nx_tick, plat_spec.asm): the play area is shown nx_off
; pixels right of Konami's map (Layer 2's scroll).  Konami's sprites are the
; Next's hardware sprites (nx_l2.asm, lo_sprites); enemies Konami draws with
; characters (E300 and E500 slots with byte 11 set): lo_tick puts the
; background back in name_shadow under them and keeps their characters as
; 16x16 patterns, drawn as sprites.  Objects Konami moves with the scroll
; (through se_corre_con_el_scroll_ocho, 2:9251, hooked to lo_gnd) move with
; the scenery: their sprites by lo_off, and enemies drawn with characters
; are left in the map.

    device zxspectrum128
    include "nx_syms.inc"

LO_GSET     equ 0x3300          ; per slot: moved with the scroll this tick (lo_gnd)
LO_GND      equ 0x3320          ; the same, for the tick just run
MAPK        equ 0xED00-0x3100   ; Konami's play-area map (22 rows of 32)
OBJ_MAX     equ 22

    org 0x0100
    jp lo_tick                  ; 0100: after each tick, A = nx_off
    jp lo_draw                  ; 0103: render_frame, in place of draw_sprites
    jp lo_gnd                   ; 0106: hook in Konami's 2:9251
    jp lo_init                  ; 0109: nx_init, once (MMU0/1 mapped, interrupts off)
    jp lo_snd                   ; 010C: the interrupt, in place of run_sound
    jp lo_render                ; 010F: the main loop, in place of render_frame
    jp lo_rowmark               ; 0112: tick_tiles, in place of redraw_tile_row
    jp lo_sprflip               ; 0115: nx_frame, when a new screen is shown
    jp lo_shiftrow              ; 0118: the scroll's row moves (0:46A1)
    jp lo_stage                 ; 011B: in place of Konami's calls to 0:422A
    jp lo_marcador              ; 011E: at the start of 0:5851
    jp lo_prestage              ; 0121: in place of 0:53C8's call to 0:5874
    jp lo_shipst                ; 0124: in place of ld a,(E200) at 2:99A1, 2:99C3, 3:A19B

lo_off:     db 0
lo_p30:     db 3
lo_nobj:    db 0

; Hook: replaces `ld a,(E100)` at the start of se_corre_con_el_scroll_ocho,
; which every object that moves with the scroll calls every tick (IX = the
; object, E300 or E500 slot).  Preserves BC, DE, HL.
lo_gnd:
    push hl
    push ix
    pop hl
    ld a,h
    sub 0xE3-0x31               ; E300-E5FF (B200-B4FF) -> slot index 0-31
    cp 4
    jr nc,.out
    add a,a
    add a,a
    add a,a                     ; (h - B2) * 8
    ld h,a
    ld a,l
    rlca
    rlca
    rlca
    and 7                       ; + l / 32
    add a,h
    ld l,a
    ld h,LO_GSET>>8
    ld (hl),1
.out:
    pop hl
    ld a,(0xE100-0x3100)        ; what the hook replaced
    ret

; After each tick (from nx_tick, page C in), A = the offset just set.
lo_tick:
    ld (lo_off),a
    ifdef PACE_30
    ld a,(nx_hz60)              ; at 60 Hz (nx_hz): screens 2 frames apart,
    or a                        ; 30 ticks a second as at 50
    ld a,2
    jr nz,.n3
    ld hl,lo_p30                ; NEM_PACE=30: screens 2, 2, 1 frames apart,
    dec (hl)                    ; at most 30 ticks a second at 50 Hz however
    ld a,2                      ; fast the machine (request_flip takes
    jr nz,.n3                   ; pace_need)
    ld (hl),3
    dec a
.n3:
    ld (pace_need),a
    endif
    ; ground flags: the objects Konami moved with the scroll this tick
    ; (an object can do so only some of the time: a walker, when it stops)
    ld hl,LO_GSET
    ld de,LO_GND
    ld bc,32
    ldir
    ld hl,LO_GSET
    ld b,32
.clr:
    ld (hl),0
    inc l
    djnz .clr
    ld a,(0xE000-0x3100)        ; Konami's state: 0, 1 the title (the screen is
    cp 2                        ; written directly, the map is stale)
    jr c,.nochars
    ld a,(spr_on)               ; and while Konami has the sprites hidden (a
    or a                        ; restart's wipe), none of these either
    jr z,.nochars
    call lo_chars
    call lo_pieces
    jp lo_boss
.nochars:
    xor a
    ld (LO_QN),a
    ld (LO_QG),a
    ld (lo_nobj),a
    ld (lo_bon),a
    ret
; The enemies drawn with characters.  An object of E300 or E500 with byte 11
; set has its characters written into Konami's map during the tick, at the
; cell in bytes 30-31 (2x2, or 2 side by side when byte 11 > 1), and the
; background put back afterwards; the map comparison has meanwhile copied
; them into name_shadow.  For each: the characters are taken from
; name_shadow, the background (Konami's map now) put back there, its cells
; marked, and its pattern made for lo_draw.
lo_chars:
    xor a
    ld (lo_nobj),a
    ld ix,0xE300-0x3100
    ld iy,LO_GND
    ld b,12
    call .tab
    ld ix,0xE500-0x3100
    ld iy,LO_GND+16
    ld b,10
    call .tab
    ld a,(lo_nobj)
    or a
    ret z
    call lo_patterns
    ret
.tab:
    push bc
    call .obj
    pop bc
    ld de,32
    add ix,de
    inc iy
    djnz .tab
    ret
.obj:
    ld a,(ix+0)
    or a
    ret z
    cp 0x19
    ret z
    ld a,(ix+0x0b)
    or a
    ret z
    ld a,(iy+0)                 ; moved with the scroll: left in the scenery
    or a                        ; (our drawings of the turrets and capsules are
    ret nz                      ; in the character pool, lo_pcell)
    ld a,(ix+6)
    cp 0xf8
    ret nc
    ld a,(ix+4)
    cp 0xb8
    ret nc
    ld a,(lo_nobj)
    cp OBJ_MAX
    ret nc
    ; cell index
    ld l,(ix+0x1e)
    ld h,(ix+0x1f)
    ld de,-MAPK
    add hl,de
    ld a,h                      ; rows 0-21 only (index below 2C0): the map
    cp 2                        ; holds no background for the status rows,
    jr c,.inmap                 ; and taking a character out there wrote 00
    ret nz                      ; over the power-up bar (the black block)
    ld a,l
    cp 0xC0
    ret nc
.inmap:
    ; record: x, y, row, 4 characters, size (1: four characters; 2: two;
    ; 3: four, the top two only)
    push hl
    ld a,(lo_nobj)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl                   ; * 8
    ld de,lo_objs
    add hl,de
    push hl
    pop iy                      ; (iy borrowed; restored below)
    pop hl
    ld a,(ix+6)
    ld (iy+0),a
    ld a,(ix+4)
    ld (iy+1),a
    ld a,l                      ; row = index / 32
    rlca
    rlca
    rlca
    and 7
    ld e,a
    ld a,h
    add a,a
    add a,a
    add a,a
    or e
    ld (iy+2),a
    ld a,(ix+0x0b)
    ld (iy+7),a
    push hl                     ; its frame (byte 12): LO_OFRM (lo_pconv)
    ld a,(lo_nobj)
    add a,LO_OFRM&0xff
    ld l,a
    ld h,LO_OFRM>>8
    ld a,(ix+0x0c)
    ld (hl),a
    pop hl
    xor a                       ; anything taken?
    ld (lo_took),a
    ld de,0
    call .cell
    ld (iy+3),a
    ld de,1
    call .cell
    ld (iy+4),a
    ld a,(iy+7)
    dec a
    jr nz,.two
    ld a,(iy+2)
    cp 21
    jr nc,.half                 ; no row below in the map
    ld de,32
    call .cell
    ld (iy+5),a
    ld de,33
    call .cell
    ld (iy+6),a
    jr .took
.half:
    ld (iy+7),3                 ; four characters, the top two only (lo_pconv)
    jr .took
.two:
    ld (iy+7),2                 ; two characters (Konami's byte 11 above 1)
.took:
    ; restore iy (the ground flag pointer): iy was LO_GND + slot; recompute
    ; from ix: (ix - B200) / 32
    push ix
    pop de
    ld a,d
    sub 0xB2
    add a,a
    add a,a
    add a,a
    ld d,a
    ld a,e
    rlca
    rlca
    rlca
    and 7
    add a,d
    add a,LO_GND&0xff
    ld e,a
    ld d,LO_GND>>8
    push de
    pop iy
    ld a,(lo_took)
    or a
    ret z                       ; not drawn this tick
    ld hl,lo_nobj
    inc (hl)
    ret
; cell HL + DE: the character name_shadow has (returned in A), and the map's
; put in its place; lo_took set if they differed.  Preserves HL, IX, IY.
.cell:
    push hl
    add hl,de
    push hl
    ld de,MAPK
    add hl,de
    ld e,(hl)                   ; the map: the background
    pop hl
    push hl
    ld bc,name_shadow
    add hl,bc
    ld a,(hl)
    cp e
    jr z,.same
    ld (hl),e
    pop hl                      ; the index: third H, low byte L
    push af
    ld b,h
    ld c,l
    call dirty_cell
    ld a,1
    ld (lo_took),a
    pop af
    pop hl
    ret
.same:
    pop hl
    pop hl
    ret
lo_took:    db 0
lo_best:    db 0                ; lo_patterns: the most pixels in a row so far,
lo_bcol:    db 0                ; that row's colours,
lo_rc:      dw 0                ; the character looked at,
lo_patp:    dw 0                ; this object's 32 pattern bytes

; Patterns (page D's copy of the pattern table) and inks (page C's colours)
; for the objects recorded: 32 bytes each in TMS order (left column top,
; bottom, right column top, bottom).
lo_patterns:
    ld a,PAGE_D
    call borrow_page
    ld a,(lo_nobj)
    ld b,a
    ld ix,lo_objs
    ld de,lo_pats
.p:
    push bc
    ld a,(ix+2)                 ; row
    ld c,(ix+3)                 ; top left
    call .ch
    ld c,(ix+5)                 ; bottom left
    call .low
    ld a,(ix+2)
    ld c,(ix+4)                 ; top right
    call .ch
    ld c,(ix+6)                 ; bottom right
    call .low
    ld bc,8
    add ix,bc
    pop bc
    djnz .p
    ; and their colours, the same way from page C's copy of the colour table
    ld a,PAGE_C
    call borrow_page
    ld a,(lo_nobj)
    ld b,a
    ld ix,lo_objs
    ld de,lo_cols
.c:
    push bc
    ld a,(ix+2)
    ld c,(ix+3)
    call .ch
    ld c,(ix+5)
    call .low
    ld a,(ix+2)
    ld c,(ix+4)
    call .ch
    ld c,(ix+6)
    call .low
    ld bc,8
    add ix,bc
    pop bc
    djnz .c
    jp unborrow_page
; HL = E800 + third(row A) * 0x800 + C * 8
.addr:
    and 0x18                    ; row / 8 * 8 = the third * 0x800 / 0x100
    add a,0xE8
    ld h,a
    ld l,c
    ld a,h                      ; + C * 8
    ld b,0
    sla l
    rl b
    sla l
    rl b
    sla l
    rl b
    add a,b
    ld h,a
    ret
.low:                           ; the bottom row's character C, or nothing
    ld a,(ix+7)
    cp 1
    jr nz,.zero
    ld a,(ix+2)
    inc a
.ch:                            ; 8 pattern bytes of character C, row A, to (DE)
    push af
    push bc
    call .addr
    ld bc,8
    ldir
    pop bc
    pop af
    ret
.zero:
    push af
    xor a
    ld b,8
.z:
    ld (de),a
    inc de
    djnz .z
    pop af
    ret

; In place of draw_sprites (render_frame, page 7 in): the character enemies,
; then the sprites over them.
lo_draw:                        ; (the ULA renderer's hook; unused with Layer 2)
    jp draw_sprites

    include "nx_l2.asm"

lo_objs:    ds OBJ_MAX*8
lo_pats:    ds OBJ_MAX*32       ; 1-bit patterns, TMS order
lo_end:
    assert lo_end <= LO_SPAT
    assert NX_PQ == lo_pq && NX_PBLK == lo_pblk && NX_PPAL == lo_ppal && NX_CSLOTS == OBJ_MAX && LO_CPAT == 0x2800 && NX_ST1PAL == ENH_BANK*2+1

    savebin "nx_low.bin", 0x0000, 0x4000
