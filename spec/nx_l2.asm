; Spectrum Next: Layer 2 and hardware sprites in place of the ULA renderer.
;
; The background is drawn on Layer 2 (256x192, a byte a pixel), two buffers
; flipped as the ULA screens were: screen 0 is banks 9-11, screen 1 banks
; 13-15 (isr_flip writes NEXTREG 12h).  A cell is drawn straight from the
; copies of the MSX pattern and colour tables (page D's and page C's E800),
; each pixel the MSX colour number, and the Layer 2 palette's entries 0-15
; are the TMS9918's colours: the picture is the MSX's.  The cells drawn are
; the dirty ones of the screen being drawn, as before.
;
; Sprites are the Next's.  Konami's 64 patterns (bank 7's copy, F800) are
; 4-bit patterns 0-63, a set pixel = 1, and each sprite's MSX colour is its
; palette offset (sprite palette entry 16 * colour + 1 = that colour).  The
; enemies drawn with characters (lo_chars) are 4-bit patterns 64 on, in
; their characters' own colours (entries 0-15).  lo_render prepares the
; attributes (and patterns) for the screen it draws; lo_sprflip, from the
; interrupt, sends them when that screen is shown, so sprites and screen
; change together.

    macro CELLROW r
        ld c,(ix+r)             ; pattern
        ld a,(iy+r)             ; colour: fg << 4 | bg
        call lo_row
    endm

    macro PIX
        sla c
        sbc a,a
        and d
        xor e
        ld (hl),a
    endm

LO_SPAT     equ 0x2000          ; Konami's sprite patterns as last sent (2K)
LO_CPAT     equ 0x2800          ; the character enemies' 4-bit patterns (22 x 128)
LO_ATTR     equ 0x3300          ; 64 sprites x 5 attributes, for the next screen
LO_PFLAG    equ 0x3440          ; Konami patterns changed (64 bits)
LO_MPAT     equ 0x3500          ; MSX2 line-coloured sprites: 6 x 128 (patterns 96-101)
NMULTI      equ 6
NSPR        equ 64
L2_BANK0    equ 9
L2_BANK1    equ 13

lo_npend:   db 0                ; character enemies' patterns to send
lo_ppend:   db 0                ; some Konami pattern changed

; The TMS9918's colours (msxsim/screen.py) as 9-bit Next colours: RRRGGGBB, B0
lo_tms:
    db 0x00,0, 0x00,0, 0x35,0, 0x79,1, 0x4B,1, 0x6F,1, 0xC9,0, 0x5B,1
    db 0xE9,0, 0xED,1, 0xD5,0, 0xDA,0, 0x35,0, 0xCA,1, 0xDB,0, 0xFF,1

; The 16 colours at HL (two bytes each, Next 9-bit) as Layer 2 entries 0-15,
; sprite entries 0-15 (character enemies) and sprite entries 16 * c + 1 (a
; Konami sprite of colour c).  Preserves HL.
lo_setpal:
    push hl
    db 0xED,0x91,0x43,0x10      ; nextreg 0x43,0x10: write Layer 2's first palette
    db 0xED,0x91,0x40,0x00      ; from index 0
    call .pal16
    db 0xED,0x91,0x43,0x20      ; sprites' first palette
    db 0xED,0x91,0x40,0x00
    call .pal16
    inc hl
    inc hl                      ; colour 1 on
    ld c,0x11
.sp:
    ld a,c
    db 0xED,0x92,0x40           ; nextreg 0x40,a: entry 16 * colour + 1
    ld a,(hl)
    db 0xED,0x92,0x44
    inc hl
    ld a,(hl)
    db 0xED,0x92,0x44
    inc hl
    ld a,c
    add a,0x10
    ld c,a
    jr nc,.sp
    db 0xED,0x91,0x43,0x00      ; first palettes in use, ULANext off
    pop hl
    ret
.pal16:
    push hl
    ld b,32
.p:
    ld a,(hl)
    db 0xED,0x92,0x44
    inc hl
    djnz .p
    pop hl
    ret

; MSX2 graphics (the "Nemesis ENHANCED" patch's, read from the user's own
; ROM and IPS by msx2_pack.py): if the .NEX carries them, Next bank 15 +
; stage holds that stage's MSX2 video memory 0000-37FF as the patched ROM's
; stage load leaves it, its palette at 3800 and a mask at 3900 (a bit per
; byte: written by that load).  After Konami's own load (0:422A, called from
; 0:4100 and 0:414B) the masked bytes of the colour, sprite pattern and
; pattern copies are replaced (the rest keep what earlier screens left, as
; on the MSX2) and the palette set; Konami's later writes (stars, status
; line) go on as before.  Konami's status-line loader (0:5851), run for every
; screen that is not a stage, puts the TMS9918 colours back.
ENH_BANK    equ 16              ; stage 1's (16K bank)
lo_stage:
    call m0_422A
    push hl
    push de
    push bc
    ld a,(0xE061-0x3100)
    ld c,0                      ; every table
    call lo_apply
    pop bc
    pop de
    pop hl
    ret

; Hook: replaces 0:53C8's call to 0:5874 (the screen before each stage, at a
; new game and after a life is lost).  Konami has just loaded its own status
; line and font there; the MSX2 patch loads its own.  Give it the coming
; stage's palette and that stage's bottom third (the status line, as its
; stage load leaves it) now, instead of at the stage load, so the status line
; does not show in the TMS9918 graphics first.  Only the bottom third: the
; other two still hold the font for the turn message.
lo_prestage:
    call m0_5874
    xor a
    ld (lo_title),a
    push hl
    push de
    push bc
    ld a,(0xE061-0x3100)
    or a
    jr nz,.st
    inc a                       ; a new game: stage 1
.st:
    cp 9
    jr c,.go
    sub 9                       ; 9-12: the stages 0:418F maps them to
    and 3
    ld hl,.map
    add a,l
    ld l,a
    jr nc,.nc
    inc h
.nc:
    ld a,(hl)
.go:
    ld c,1                      ; the bottom third
    call lo_apply
    pop bc
    pop de
    pop hl
    ret
.map:
    db 3,4,5,8

; A = stage (1-8), C = 0: the colour, sprite pattern and pattern copies
; whole; 1: the colour and pattern copies' bottom thirds only.  Sets the
; palette and line-colour tables.  Nothing if the .NEX has no MSX2 graphics.
lo_apply:
    dec a
    cp 8
    ret nc
    ld b,a
    ld a,c
    ld (lo_part),a
    ld a,b
    add a,a
    add a,ENH_BANK*2            ; 8K page of VRAM 0000
    ld (lo_spage),a
    inc a
    db 0xED,0x92,0x52           ; its VRAM 2000-3FFF at 4000: is the palette
    ld hl,(0x5802)              ; there? (colour 1 is never 00 00 when it is;
    ld a,h                      ; a .NEX without the banks leaves them zero)
    or l
    jp z,.restore
    push ix
    ld a,0x57                   ; MMU7 now (put back after): the mask at F900
    ld bc,0x243B
    di                          ; (the interrupt selects registers too)
    out (c),a
    inc b
    in a,(c)
    ei
    ld (lo_mmu7),a
    ld a,(lo_spage)
    inc a
    db 0xED,0x92,0x57           ; MMU7 = the stage's second 8K: mask at F900
    dec a
    db 0xED,0x92,0x52           ; MMU2 = this stage's VRAM 0000-1FFF
    db 0xED,0x91,0x53,9         ; bank 4 (page C) E000-FFFF: colours from 6800
    ld a,(lo_part)
    or a
    jr nz,.bottom
    ld hl,0x4000
    ld de,0x6800
    ld ix,0xF900
    ld bc,0x1800/8
    call lo_mcopy
    db 0xED,0x91,0x53,15        ; bank 7 E000-FFFF: sprite patterns from 7800
    ld de,0x7800
    ld bc,0x0800/8
    call lo_mcopy
    ld a,(lo_spage)             ; VRAM 2000-3FFF
    inc a
    db 0xED,0x92,0x52
    db 0xED,0x91,0x53,13        ; bank 6 (page D) E000-FFFF: patterns from 6800
    ld hl,0x4000
    ld de,0x6800
    ld bc,0x1800/8
    call lo_mcopy
    jr .copied
.bottom:
    ld hl,0x5000                ; VRAM 1000-17FF
    ld de,0x7800
    ld ix,0xF900+0x1000/8
    ld bc,0x0800/8
    call lo_mcopy
    ld a,(lo_spage)             ; VRAM 3000-37FF
    inc a
    db 0xED,0x92,0x52
    db 0xED,0x91,0x53,13
    ld hl,0x5000
    ld de,0x7800
    ld ix,0xF900+0x3000/8
    ld bc,0x0800/8
    call lo_mcopy
.copied:
    ld a,(lo_mmu7)
    db 0xED,0x92,0x57
    pop ix
    ld hl,0x5800                ; the palette
    call lo_setpal
    ld hl,0x5820                ; the patch's sprite line-colour tables
    ld de,lo_ltab
    ld bc,144
    ldir
    ld a,1
    ld (lo_enh),a
    ld a,(lo_spage)
    sub ENH_BANK*2
    add a,24*2                  ; bank 24 + stage - 1, its first 8K page
    ld (lo_fpage),a
.restore:
    db 0xED,0x91,0x52,0x0A
    db 0xED,0x91,0x53,0x0B
    ld a,1
    ld (star_stale),a
    jp dirty_all

; Copy the bytes of HL on to DE (8 * BC of them) whose bits are set in the
; mask at IX (a byte per 8, bit 0 first); all move on.
lo_mcopy:
    push bc
    ld c,(ix+0)
    inc ix
    ld b,8
.bit:
    rr c
    jr nc,.skip
    ld a,(hl)
    ld (de),a
.skip:
    inc hl
    inc de
    djnz .bit
    pop bc
    dec bc
    ld a,b
    or c
    jr nz,lo_mcopy
    ret
lo_spage:   db 0
lo_part:    db 0
lo_mmu7:    db 0

lo_marcador:
    xor a
    ld (lo_enh),a
    ld (lo_title),a
    push hl
    push bc
    ld hl,lo_tms
    call lo_setpal
    ld hl,6                     ; called for the title screen (from 0:5B4D)?
    add hl,sp
    ld a,(hl)
    inc hl
    ld h,(hl)
    ld l,a
    ld bc,m0_5B50
    or a
    sbc hl,bc
    call z,lo_logopal
    pop bc
    pop hl
    ld de,m0_5906               ; the instruction the call replaced
    ret

; The title screen: if the .NEX has the MSX2 graphics, the patch's logo
; replaces Konami's (lo_logocell), its palette as Layer 2 entries 10h-1Fh.
LO_LOGO     equ (24*2+1)        ; 8K page: the logo at 0000, its palette at 1800
lo_logopal:
    ld a,i                      ; P/V: interrupts were on
    push af
    di                          ; (6000-7FFF is fixed memory meanwhile)
    db 0xED,0x91,0x53,LO_LOGO   ; at 6000
    ld hl,(0x7802)              ; colour 1 is never 00 00 when it is there
    ld a,h
    or l
    jr z,.out
    db 0xED,0x91,0x43,0x10      ; Layer 2's first palette, from entry 10h
    db 0xED,0x91,0x40,0x10
    ld hl,0x7800
    ld b,32
.p:
    ld a,(hl)
    db 0xED,0x92,0x44
    inc hl
    djnz .p
    db 0xED,0x91,0x43,0x00
    ld hl,lo_cst
    ld b,32
.z:
    ld (hl),0
    inc hl
    djnz .z
    ld a,1
    ld (lo_title),a
.out:
    db 0xED,0x91,0x53,0x0B
    pop af
    ret po
    ei
    ret
lo_title:   db 0

; Once, from nx_init: palettes, both Layer 2 screens black, no sprites,
; every Konami pattern to be sent, stars as plain cells.  Page D was in.
lo_init:
    ld hl,lo_tms
    call lo_setpal
    db 0xED,0x91,0x43,0x20      ; sprite entries 13h-15h: the fire colours
    db 0xED,0x91,0x40,0x13      ; (palette offset 1, pixels 3-5)
    db 0xED,0x91,0x44,0xC4      ; red
    db 0xED,0x91,0x44,0x00
    db 0xED,0x91,0x44,0xF0      ; orange
    db 0xED,0x91,0x44,0x00
    db 0xED,0x91,0x44,0xF8      ; yellow
    db 0xED,0x91,0x44,0x01
    db 0xED,0x91,0x43,0x00
    ; Layer 2: both screens black
    ld a,L2_BANK0
    call .clr48
    ld a,L2_BANK1
    call .clr48
    ld a,12                     ; page D back at C000 (nx_init runs there)
    db 0xED,0x92,0x56
    inc a
    db 0xED,0x92,0x57
    ; all 128 sprites hidden
    xor a
    ld bc,0x303B
    out (c),a
    ld b,128
.hide:
    out (0x57),a
    out (0x57),a
    out (0x57),a
    out (0x57),a                ; attribute 3 = 0: not visible (4 attributes)
    djnz .hide
    ; every Konami pattern differs from the copy
    ld hl,LO_SPAT
    ld de,LO_SPAT+1
    ld bc,2047
    ld (hl),0x5A
    ldir
    ld a,1
    ld (star_off),a             ; stars as plain cells (the map comparison marks them)
    ld (star_stale),a
    jp dirty_all
.clr48:                         ; three 16K banks from A: zero
    ld b,3
.cb:
    push bc
    push af
    add a,a
    db 0xED,0x92,0x56
    inc a
    db 0xED,0x92,0x57
    ld hl,0xC000
    ld de,0xC001
    ld bc,0x3FFF
    ld (hl),0
    ldir
    pop af
    inc a
    pop bc
    djnz .cb
    ret

; The interrupt's sound (and nx_frame), in place of run_sound: with the
; ordinary map at 4000-7FFF and whatever page Konami has, whatever the
; renderer had mapped (MMU2, MMU3, MMU6, MMU7), put back afterwards.
lo_snd:
    ld bc,0x243B
    ld a,0x52
    call .rd
    push af
    ld a,0x53
    call .rd
    push af
    ld a,0x56
    call .rd
    push af
    ld a,0x57
    call .rd
    push af
    db 0xED,0x91,0x52,0x0A
    db 0xED,0x91,0x53,0x0B
    call run_sound
    pop af
    db 0xED,0x92,0x57
    pop af
    db 0xED,0x92,0x56
    pop af
    db 0xED,0x92,0x53
    pop af
    db 0xED,0x92,0x52
    ret
.rd:
    out (c),a
    inc b
    in a,(c)
    dec b
    ret

; tick_tiles, in place of redraw_tile_row: row A of tile E in third D
; changed: mark the cells showing it (both screens).
lo_rowmark:
    ld a,d
    add a,name_shadow>>8
    ld h,a
    ld l,0
    ld b,0
.f:
    ld a,(hl)
    cp e
    jr nz,.n
    ld b,d
    ld c,l
    call dirty_cell
    ld b,0
.n:
    inc l
    jr nz,.f
    ret

; The main loop, in place of render_frame: draw the hidden screen.
lo_render:
    ld a,(lo_org)               ; this screen's Layer 2 X scroll (nx_frame sets it
    add a,a                     ; when the screen is shown): origin * 8 - offset
    add a,a
    add a,a
    ld hl,lo_off
    sub (hl)
    ld (nx_pend),a
    ; stars: a twinkle changed F6/F7, so every star cell is drawn again.
    ; Their rows are compared here with the copy last drawn (row_update
    ; patches the ULA's tile set in place and does not tell tick_tiles).
    db 0xED,0x91,0x52,13        ; page D's pattern copy at 4800
    ld de,lo_starpat
    ld c,0                      ; changed?
    ld hl,0x4800+0xF6*8
    call .stc
    ld hl,0x5000+0xF6*8
    call .stc
    ld hl,0x5800+0xF6*8
    call .stc
    db 0xED,0x91,0x52,0x0A
    ld a,(star_any)
    ld hl,star_carry_any
    or (hl)
    or c
    jr z,.nostar
    xor a
    ld (star_any),a
    ld (hl),a
    ld hl,name_shadow
.st:
    ld a,(hl)
    and 0xfe
    cp 0xf6
    jr nz,.stn
    ld b,h
    ld a,b
    sub name_shadow>>8
    ld b,a
    ld c,l
    call dirty_cell
.stn:
    inc hl
    ld a,h
    cp (name_shadow+704)>>8
    jr c,.st
    ld a,l
    cp (name_shadow+704)&0xff
    jr c,.st
.nostar:
    ; which screen: screen 1 shown -> draw screen 0
    ld a,(port_bits)
    and 8
    ld a,L2_BANK0
    ld c,0                      ; its dirty bitmap: dirty0 + C
    jr nz,.scr
    ld a,L2_BANK1
    ld c,0x80
.scr:
    ld (lo_l2bank),a
    ld a,c
    ld (lo_dlow),a
    call lo_cells
    call lo_sprites
    jp unborrow_page            ; Konami's page back at C000

; 16 bytes (F6, F7) at HL against DE, copied; C set if they differed.
lo_render.stc:
    ld b,16
.s:
    ld a,(de)
    cp (hl)
    jr z,.e
    ld a,(hl)
    ld (de),a
    ld c,1
.e:
    inc hl
    inc de
    djnz .s
    ret
lo_starpat: ds 48
lo_l2bank:  db 0
lo_dlow:    db 0
lo_org:     db 0                ; Layer 2 column of map column 0 (rows 0-21)
lo_srow:    db 0

; In place of nm_ldi31_full (0:46A1): Konami moves a row of its map one
; character left (HL = DE + 1, BC = 31).  The same row of name_shadow and of
; both dirty bitmaps is turned one column left (column 0 to 31), so they go
; on describing what each Layer 2 screen holds, now one column further on;
; after the last row (21) the origin moves on a column.
lo_shiftrow:
    ld a,e                      ; the row: (DE - map) / 32
    rlca
    rlca
    rlca
    and 7
    ld (lo_srow),a
    ld a,d
    sub MAPK>>8
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,(lo_srow)
    add a,b
    ld (lo_srow),a
    ld bc,31
    ldir                        ; Konami's move
    push hl
    push de
    ld a,(lo_srow)              ; name_shadow row: turned left
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,name_shadow
    add hl,de
    ld a,(hl)
    ld d,h
    ld e,l
    inc hl
    ld bc,31
    ldir
    ld (de),a
    ld a,(lo_srow)              ; dirty bitmaps: bit c of the row's 32 = column c
    add a,a
    add a,a
    ld l,a
    ld h,dirty0>>8
    call .rot
    set 7,l
    call .rot
    ld a,(lo_srow)
    cp 21
    jr nz,.out
    ld hl,lo_org
    ld a,(hl)
    inc a
    and 31
    ld (hl),a
.out:
    pop de
    pop hl
    ld bc,0
    jp nm_set_full
.rot:                           ; 32 bits at HL (byte 0 low): right one, bit 0 to 31
    ld a,(hl)
    rra
    inc l
    inc l
    inc l
    rr (hl)
    dec l
    rr (hl)
    dec l
    rr (hl)
    dec l
    rr (hl)
    ret

; Every dirty cell of the screen chosen, drawn into its Layer 2 screen.
; MMU2 = page D's upper half (the pattern copy at 4800), MMU3 = page C's
; (the colour copy at 6800), MMU6/7 = the Layer 2 third.
lo_cells:
    db 0xED,0x91,0x52,13        ; bank 6 (page D), E000-FFFF at 4000
    db 0xED,0x91,0x53,9         ; bank 4 (page C), E000-FFFF at 6000
    xor a
.third:
    ld (lo_third),a
    ld b,a
    ld a,(lo_l2bank)
    add a,b
    add a,a
    db 0xED,0x92,0x56
    inc a
    db 0xED,0x92,0x57
    ld a,b                      ; this third's 32 bitmap bytes
    add a,a
    add a,a
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,(lo_dlow)
    add a,b
    ld l,a
    ld h,dirty0>>8
    ld b,32
.byte:
    ld a,(hl)
    or a
    jr z,.nextb
    ld (hl),0
    push bc
    push hl
    ld c,a                      ; bit k: column (l & 3) * 8 + k
    ld a,l
    and 3
    add a,a
    add a,a
    add a,a
    ld e,a
    ld a,l
    and 0x1c
    rrca
    rrca
    ld d,a                      ; row in the third
.bit:
    srl c
    jr nc,.nob
    push bc
    push de
    call lo_cell
    pop de
    pop bc
.nob:
    inc e
    ld a,c
    or a
    jr nz,.bit
    pop hl
    pop bc
.nextb:
    inc l
    djnz .byte
    ld a,(lo_third)
    inc a
    cp 3
    jr c,.third
    db 0xED,0x91,0x52,0x0A      ; the ordinary map back
    db 0xED,0x91,0x53,0x0B
    ret
lo_third:   db 0
lo_colx:    db 0

; Cell: row D (0-7) of third lo_third, column E.
lo_cell:
    ld a,(lo_third)
    add a,a
    add a,a
    add a,a
    add a,d                     ; cy
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl                   ; cy * 32
    ld a,l
    or e
    ld l,a
    ld bc,name_shadow
    add hl,bc
    ld l,(hl)                   ; the character
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl                   ; * 8
    ld a,(lo_third)
    add a,a
    add a,a
    add a,a
    add a,0x48                  ; 4800 + third * 0x800
    add a,h
    ld h,a
    push hl
    pop ix                      ; pattern bytes
    set 5,h                     ; 6800 + the same: colour bytes
    push hl
    pop iy
    ld a,d                      ; destination C000 + D * 0x800 + column * 8
    add a,a
    add a,a
    add a,a
    add a,0xC0
    ld h,a
    ld a,(lo_third)             ; rows 0-21 (the play area) turn with the scroll
    add a,a
    add a,a
    add a,a
    add a,d
    cp 22
    ld a,e
    jr nc,.col
    ld a,(lo_org)
    add a,e
    and 31
.col:
    add a,a
    add a,a
    add a,a
    ld l,a
    ld (lo_colx),a
    ld a,(lo_title)
    or a
    jp nz,lo_logocell
.draw:
    CELLROW 0
    CELLROW 1
    CELLROW 2
    CELLROW 3
    CELLROW 4
    CELLROW 5
    CELLROW 6
    CELLROW 7
    ret


; The title screen with the patch's logo: Konami's logo panel is rows 4-8,
; columns 2-29; the patch's logo (256 x 48) is drawn over rows 3-8, all
; columns.  A column shows the logo while any of its panel cells is not
; blank (columns 0-1 and 30-31 go with 2 and 29), so it goes as Konami's
; curtain clears the screen column by column.  Drawing a panel cell marks
; the cells that go with it but whose own names do not change: row 3 above
; it, and the side columns.  D, E, HL as lo_cell has them (HL the
; destination).
lo_logocell:
    ld a,(lo_third)
    add a,a
    add a,a
    add a,a
    add a,d
    sub 3
    cp 6
    jp nc,lo_cell.draw
    ld (lo_lr),a                ; logo row 0-5 (screen row 3-8)
    ld a,e
    ld (lo_lc),a
    push hl
    cp 2                        ; the panel column
    jr nc,.c1
    ld a,2
.c1:
    cp 30
    jr c,.c2
    ld a,29
.c2:
    ld c,a
    ld hl,name_shadow+4*32
    add a,l
    ld l,a
    jr nc,.c3
    inc h
.c3:
    ld de,32
    xor a
    ld b,5
.or:
    or (hl)
    add hl,de
    djnz .or
    or a
    jr z,.st
    ld a,1
.st:
    ld (lo_lon),a
    ld b,0                      ; changed since this column was last drawn?
    ld hl,lo_cst
    add hl,bc
    cp (hl)
    jr z,.same
    ld (hl),a                   ; then every cell of the logo in it, both
    ld a,c                      ; screens (its other cells' names have not
    cp 2                        ; changed), and the side columns with it
    jr nz,.r1
    xor a
    call lo_markcol
    ld a,1
    call lo_markcol
    ld a,2
.r1:
    cp 29
    jr nz,.r2
    call lo_markcol
    ld a,30
    call lo_markcol
    ld a,31
.r2:
    call lo_markcol
.same:
    pop hl
    ld a,(lo_lon)
    or a
    jp z,lo_cell.draw
    db 0xED,0x91,0x53,LO_LOGO   ; the logo at 6000
    ld a,(lo_lr)                ; 6000 + logo row * 1024 + column * 4
    add a,a
    add a,a
    add a,0x60
    ld d,a
    ld a,(lo_lc)
    add a,a
    add a,a
    ld e,a
    ld a,8
.line:
    push af
    ld b,4
.byte:
    ld a,(de)
    ld c,a
    rrca
    rrca
    rrca
    rrca
    and 15
    jr z,.p0
    add a,0x10
.p0:
    ld (hl),a
    inc l
    ld a,c
    and 15
    jr z,.p1
    add a,0x10
.p1:
    ld (hl),a
    inc l
    inc de
    djnz .byte
    ld a,e
    add a,124
    ld e,a
    jr nc,.nc
    inc d
.nc:
    ld a,(lo_colx)
    ld l,a
    inc h
    pop af
    dec a
    jr nz,.line
    db 0xED,0x91,0x53,9         ; the colour copy back (lo_cells)
    ret
lo_lr:      db 0
lo_lc:      db 0
lo_lon:     db 0
lo_cst:     ds 32               ; per panel column: showing the logo when last drawn

; Mark rows 3-8 of column A, both screens.  Preserves BC, DE, HL.
lo_markcol:
    push bc
    or 96                       ; row 3: third 0, row 3
    ld c,a
    ld b,0
.r:
    call dirty_cell             ; rows 3-7
    ld a,c
    add a,32
    ld c,a
    jr nc,.r
    ld b,1                      ; row 8: third 1, row 0
    call dirty_cell
    pop bc
    ret

; One pixel row: C pattern, A colours, HL the row's first pixel; HL moves
; to the next line, the same column.
lo_row:
    ld b,a
    and 15
    ld e,a                      ; bg
    ld a,b
    rrca
    rrca
    rrca
    rrca
    and 15
    xor e
    ld d,a                      ; fg ^ bg
    ld a,c
    or a
    jr nz,.pix
    ld a,e
    ld (hl),a
    inc l
    ld (hl),a
    inc l
    ld (hl),a
    inc l
    ld (hl),a
    inc l
    ld (hl),a
    inc l
    ld (hl),a
    inc l
    ld (hl),a
    inc l
    ld (hl),a
    jr .end
.pix:
    PIX
    inc l
    PIX
    inc l
    PIX
    inc l
    PIX
    inc l
    PIX
    inc l
    PIX
    inc l
    PIX
    inc l
    PIX
.end:
    ld a,(lo_colx)
    ld l,a
    inc h
    ret


; Konami's sprites and the character enemies, for the screen just drawn:
; changed patterns noted (sent by lo_sprflip), attributes into LO_ATTR.
lo_sprites:
    db 0xED,0x91,0x52,15        ; bank 7's F800-FFFF: Konami's patterns at 5800
    ld hl,0x5800
    ld de,LO_SPAT
    ld c,0                      ; pattern
.pat:
    push hl
    push de
    ld b,32
.pc:
    ld a,(de)
    cp (hl)
    jr nz,.diff
    inc hl
    inc de
    djnz .pc
    pop de
    pop hl
    jr .adv
.diff:
    pop de
    pop hl
    push hl
    push de
    push bc
    ld bc,32
    ldir                        ; the copy brought up to date
    pop bc
    call lo_pflag
    pop de
    pop hl
.adv:
    ld a,l
    add a,32
    ld l,a
    jr nc,.a1
    inc h
.a1:
    ld a,e
    add a,32
    ld e,a
    jr nc,.a2
    inc d
.a2:
    inc c
    ld a,c
    cp 64
    jr c,.pat
    db 0xED,0x91,0x52,0x0A
    ; the character enemies' 4-bit patterns
    ld a,(lo_nobj)
    ld (lo_npend),a
    or a
    jr z,.attrs
    ld b,a
    ld ix,lo_pats
    ld iy,lo_cols
    ld de,LO_CPAT
.cp:
    push bc
    call lo_conv
    ld bc,32
    add ix,bc
    add iy,bc
    pop bc
    djnz .cp
.attrs:
    ld a,(lo_par)               ; alternate screens: the patch's other buffer
    xor 32
    ld (lo_par),a
    xor a
    ld (lo_mn),a
    ld (lo_skip1),a
    ld (lo_firesh),a
    ld hl,0xEC80-0x3100         ; Konami's 32 entries -> sprites 0-31
    ld de,LO_ATTR
    ld c,0
.ent:
    ld a,(spr_on)
    or a
    jr z,.hideall
    ld a,(hl)
    cp 0xd0
    jr z,.hideall               ; the end marker: none from here on
    call lo_attr
    ld a,l
    add a,4
    ld l,a
    inc c
    ld a,c
    cp 32
    jr c,.ent
    jr .cobj
.hideall:
    call lo_mdone
    ld a,c
    cp 32
    jr nc,.cobj
    call lo_hide
    inc c
    jr .hideall
.cobj:
    call lo_mdone
    call lo_shield
    ; the character enemies: sprites 32 on, patterns 64 on, colours as drawn
    ld a,(lo_nobj)
    or a
    jr z,.rest
    ld b,a
    ld ix,lo_objs
    ld c,64
.co:
    push bc
    ld l,(ix+0)                 ; X + 32
    ld h,0
    ld a,l
    add a,32
    ld l,a
    jr nc,.cx
    inc h
.cx:
    ld a,l
    ld (de),a
    inc de
    ld a,(ix+1)                 ; Y + 1 + 32
    add a,33
    ld (de),a
    inc de
    ld b,0
    jr nc,.cy
    inc b
.cy:
    ld a,h                      ; palette offset 0, X bit 8
    ld (de),a
    inc de
    ld a,c
    srl a
    or 0xC0                     ; visible, a fifth attribute
    ld (de),a
    inc de
    ld a,c
    and 1
    rrca
    rrca                        ; N6
    or 0x80                     ; a 4-bit pattern
    or b                        ; Y bit 8
    ld (de),a
    inc de
    ld bc,8
    add ix,bc
    pop bc
    inc c
    djnz .co
.rest:
    ld hl,LO_ATTR+NSPR*5        ; the rest hidden
.rh:
    ld a,e
    cp l
    jr nz,.rh1
    ld a,d
    cp h
    ret z
.rh1:
    call lo_hide
    jr .rh

; The ship's shield with the MSX2 graphics.  Konami draws it by replacing
; the ship's second sprite (its white layer) with the barrier, 8 pixels
; ahead; the patch keeps the ship whole (its code always takes the plain
; ship's sprites: 2:99A1 and 2:99CF) and draws the barrier as a sprite of
; its own, white and grey on alternate screens.  lo_shipst stands in for
; Konami's two reads of the ship's state there: the plain ship (1) when the
; MSX2 graphics are in.  Preserves all but AF.
lo_shipst:
    ld a,(lo_enh)
    or a
    ld a,1
    ret nz
    ld a,(0xE200-0x3100)
    ret

; The barrier as one more sprite at DE (moved on), when the ship has the
; shield (E200 = 3) and the MSX2 graphics are in: Konami's pattern for it
; (2C, 24 with the stick down; 4 more on the blink's ticks, E003 bit 2),
; at the ship's Y and its X + 8.
lo_shield:
    ld a,(lo_enh)
    or a
    ret z
    ld a,(spr_on)
    or a
    ret z
    ld a,(0xE200-0x3100)
    cp 3
    ret nz
    ld hl,0xEC80-0x3100         ; the ship's entry
    ld a,(hl)
    cp 0xD0
    ret z
    ld (lo_shent),a
    inc hl
    ld a,(hl)
    add a,8
    ret c
    ld (lo_shent+1),a
    ld hl,0xE009-0x3100         ; the stick (in pause, E10D), as 2:99AB
    ld a,(0xE10B-0x3100)
    rra
    jr nc,.st
    ld hl,0xE10D-0x3100
.st:
    ld a,(hl)
    and 3
    cp 2
    ld b,0x2C
    jr nz,.p
    ld b,0x24
.p:
    ld a,(0xE003-0x3100)
    and 4
    ld a,b
    jr z,.nb
    add a,4
.nb:
    ld (lo_shent+2),a
    ld a,(lo_par)
    or a
    ld a,0x0F
    jr z,.c
    dec a
.c:
    ld (lo_shent+3),a
    ld hl,lo_shent
    ld c,10                     ; coloured as Konami's objects: its own colour
    jp lo_attr
lo_shent:   ds 4

; Note Konami pattern C as changed.  Preserves BC, DE, HL.
lo_pflag:
    push hl
    push bc
    ld a,c
    rrca
    rrca
    rrca
    and 7
    add a,LO_PFLAG&0xff
    ld l,a
    ld h,LO_PFLAG>>8
    ld a,c
    and 7
    ld b,a
    ld a,1
    jr z,.m
.s:
    add a,a
    djnz .s
.m:
    or (hl)
    ld (hl),a
    ld a,1
    ld (lo_ppend),a
    pop bc
    pop hl
    ret

; Konami's entry at HL (Y, X, pattern, colour) -> 5 attributes at DE (moved
; on), sprite C.  Preserves HL, C.
lo_attr:
    push hl
    ld a,(hl)
    inc a                       ; shown a line lower
    ld (lo_ay),a
    inc l
    ld a,(hl)
    ld (lo_ax),a
    inc l
    ld a,(hl)
    rrca
    rrca
    and 63
    ld (lo_ap),a
    inc l
    ld a,(hl)
    ld (lo_ac),a
    xor a
    ld (lo_mpi),a
    ld a,(lo_enh)
    or a
    jr z,.flat
    call lo_ecol                ; the MSX2 colours: carry = not shown
    jp c,.hid
    ld a,(lo_mpi)
    or a
    jr nz,.vis                  ; line-coloured: shown
.flat:
    ld a,(lo_ac)
    and 15
    jp z,.hid                   ; transparent
.vis:
    ; on the ground? entries 10-21: E300 slots 0-11, 22-31: E500 slots 0-9
    ld b,0
    ld a,c
    sub 10
    jr c,.x
    cp 12
    jr c,.g
    add a,4
.g:
    add a,LO_GND&0xff
    ld l,a
    ld h,LO_GND>>8
    ld a,(hl)
    or a
    jr z,.x
    ld a,(lo_off)               ; moves with the scenery: as far right
    ld b,a
.x:
    ld a,(lo_ax)                ; X + 32 (+ 0 with the early clock) + B
    ld l,a
    ld h,0
    ld a,(lo_ac)
    bit 7,a
    jr nz,.ec
    ld a,l
    add a,32
    ld l,a
    jr nc,.ec
    inc h
.ec:
    ld a,l
    add a,b
    ld l,a
    jr nc,.x2
    inc h
.x2:
    ld a,l
    ld (de),a                   ; X bits 0-7
    inc de
    ld a,(lo_ay)                ; Y: from 0xD1 on, above the top
    ld b,0
    cp 0xd1
    jr c,.yp
    add a,32                    ; (y - 256) + 32
    jr .y2
.yp:
    add a,32
    jr nc,.y2
    inc b
.y2:
    ld (de),a
    inc de
    ld a,(lo_mpi)
    or a
    jr z,.pal
    ld a,(lo_mpo)               ; line-coloured: palette offset 0 (fire 1),
    or h                        ; pattern lo_mpi (96 on)
    ld (de),a
    inc de
    ld a,(lo_mpi)
    srl a
    or 0xC0
    ld (de),a
    inc de
    ld a,(lo_mpi)
    jr .n6
.pal:
    ld a,(lo_ac)
    and 15
    rlca
    rlca
    rlca
    rlca                        ; palette offset = the colour
    or h                        ; X bit 8
    ld (de),a
    inc de
    ld a,(lo_ap)
    srl a
    or 0xC0
    ld (de),a
    inc de
    ld a,(lo_ap)
.n6:
    and 1
    rrca
    rrca
    or 0x80
    or b
    ld (de),a
    inc de
    pop hl
    ret
.hid:
    pop hl
lo_hide:                        ; 5 attributes at DE: not visible (attribute 3
    xor a                       ; bit 6 set: still 5 of them, so the stream
    ld (de),a                   ; stays in step)
    inc de
    ld (de),a
    inc de
    ld (de),a
    inc de
    ld a,0x40
    ld (de),a
    inc de
    xor a
    ld (de),a
    inc de
    ret

; The MSX2 patch's sprite colours for Konami's entry C (HL at its colour
; byte).  The options (2, 3) are drawn in fire colours (lo_fire; our
; choice, not the patch's).  Entries 4-9 and 22-31 have fixed colours (the
; patch's tables: it shows its two sprite lists alternately, two frames
; each, and some colours differ between them; here they alternate screen
; by screen, lo_par).  10-21 (E300 objects) keep Konami's, 0 shown as 8 (5
; in stage 3) and 0A on alternate screens, 60/70/80 as line-colour tables.
; 0 and 1 (the ship) are line-coloured, 1 ORed into 0 where they meet; any
; other pattern of 0 (the explosion) in fire colours.  Sets lo_ac's low
; nibble or lo_mpi (and converts the pattern); carry if not to be shown.
; Preserves BC, DE, HL.
lo_ecol:
    ld a,c
    cp 2
    jr c,.ship
    cp 4
    jp c,lo_fire                ; the options: fire colours (as the arcade's)
    cp 10
    jr c,.fixed
    cp 22
    jr nc,.fixed
    ld a,(lo_ac)
    and 0x7f
    cp 0x10
    jr nc,.tab
    or a
    ret nz                      ; Konami's own (carry clear)
    ld a,(lo_par)               ; 0: 8 (5 in stage 3); other screens 0A
    or a
    ld a,0x0A
    jr nz,.c0
    ld a,(0xE061-0x3100)
    cp 3
    ld a,8
    jr nz,.c0
    ld a,5
.c0:
    call .setc
    or a
    ret
.fixed:
    push hl
    ld hl,lo_efix
    ld a,(lo_par)
    add a,c
    add a,l
    ld l,a
    jr nc,.f1
    inc h
.f1:
    ld a,(hl)
    pop hl
    call .setc
    or a
    ret
.setc:                          ; colour A in lo_ac, early clock kept
    push bc
    ld b,a
    ld a,(lo_ac)
    and 0x80
    or b
    ld (lo_ac),a
    pop bc
    ret
.tab:                           ; table 60/70/80 (others: Konami's low nibble)
    cp 0x90
    jr nc,.tabx
    and 0xF0
    push hl
    ld hl,lo_ltab
    add a,l
    ld l,a
    jr nc,.t1
    inc h
.t1:
    ld (lo_mt),hl
    ld hl,0
    ld (lo_mt2),hl
    pop hl
    jp lo_multi
.tabx:
    or a
    ret
.ship:
    or a
    jr nz,.s1
    ld a,(lo_ap)                ; pattern 0, 8, 16 (the byte; lo_ap is /4):
    cp 0                        ; its table (the last one otherwise)
    jr z,.sk
    cp 2
    jr z,.sk
    cp 4
    jr z,.sk
    ld a,1                      ; another pattern (the explosion): fire
    ld (lo_firesh),a
    jp lo_fire
.sk:
    add a,a
    add a,a
    add a,a
    add a,a                     ; 0, 0x20, 0x40
    ld (lo_shipt),a
.sl:
    push hl
    ld a,(lo_shipt)
    ld hl,lo_ltab
    add a,l
    ld l,a
    jr nc,.s2
    inc h
.s2:
    ld (lo_mt),hl
    ld a,16
    add a,l
    ld l,a
    jr nc,.s3
    inc h
.s3:
    ld (lo_mt2),hl
    pop hl
    push hl                     ; entry 1 at the same place: ORed in
    dec l
    dec l
    dec l
    ld a,(hl)                   ; Y
    inc l
    inc l
    inc l
    inc l
    cp (hl)
    jr nz,.solo
    dec l
    dec l
    dec l
    ld a,(hl)                   ; X
    inc l
    inc l
    inc l
    inc l
    cp (hl)
    jr nz,.solo
    inc l
    ld a,(hl)                   ; entry 1's pattern
    rrca
    rrca
    and 63
    ld (lo_ap1),a
    ld a,1
    ld (lo_skip1),a
    pop hl
    jp lo_multi
.solo:
    pop hl
    ld hl,0
    ld (lo_mt2),hl
    jp lo_multi_hl
.s1:                            ; entry 1: hidden if ORed into 0
    ld a,(lo_firesh)
    or a
    jp nz,lo_fire
    ld a,(lo_skip1)
    or a
    scf
    ret nz
    push hl
    ld a,(lo_shipt)
    add a,16
    ld hl,lo_ltab
    add a,l
    ld l,a
    jr nc,.s4
    inc h
.s4:
    ld (lo_mt),hl
    ld hl,0
    ld (lo_mt2),hl
    pop hl
    jp lo_multi

; Konami pattern lo_ap's fire-coloured copy (Next bank 24 + stage, made
; by msx2_pack.py) -> LO_MPAT slot lo_mn, palette offset 1.
lo_fire:
    ld a,(lo_mn)
    cp NMULTI
    ccf
    ret c
    push bc
    push de
    push hl
    ld a,(lo_fpage)
    db 0xED,0x92,0x52           ; MMU2: the copies at 4000
    ld a,(lo_ap)
    rrca                        ; * 128 + 4000
    ld l,a
    and 0x80
    ld h,a
    ld a,l
    and 0x3f
    add a,0x40
    ld l,h
    ld h,a
    ld a,(lo_mn)
    rrca
    ld e,a
    and 0x80
    ld d,a
    ld a,e
    and 0x7f
    add a,LO_MPAT>>8
    ld e,d
    ld d,a
    ld bc,128
    ldir
    db 0xED,0x91,0x52,0x0A
    ld a,(lo_mn)
    inc a
    ld (lo_mn),a
    add a,95
    ld (lo_mpi),a
    ld a,0x10
    ld (lo_mpo),a
    pop hl
    pop de
    pop bc
    or a
    ret

lo_multi_hl:
lo_multi:
    ; Konami pattern lo_ap in the line colours at lo_mt (and lo_ap1 in
    ; lo_mt2's, ORed, if lo_mt2) -> LO_MPAT slot lo_mn, pattern 96 + it
    ld a,(lo_mn)
    cp NMULTI
    ccf
    ret c                       ; (no room: not shown)
    push bc
    push de
    push hl
    push ix
    push iy
    ld hl,(lo_mt)
    call .cols
    ld a,(lo_ap)
    call .src
    ld a,(lo_mn)
    rrca                        ; * 128
    ld e,a
    and 0x80
    ld d,a
    ld a,e
    and 0x7f
    add a,LO_MPAT>>8
    ld e,d
    ld d,a
    push de
    call lo_conv
    pop de
    ld hl,(lo_mt2)
    ld a,h
    or l
    jr z,.one
    push de
    call .cols
    ld a,(lo_ap1)
    call .src
    ld de,lo_tmp
    call lo_conv
    pop de
    ld hl,lo_tmp
    ld b,128
.or:
    ld a,(de)
    or (hl)
    ld (de),a
    inc de
    inc hl
    djnz .or
.one:
    ld a,(lo_mn)
    inc a
    ld (lo_mn),a
    add a,95
    ld (lo_mpi),a
    xor a
    ld (lo_mpo),a
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    or a
    ret
.cols:                          ; 16 line colours at HL -> lo_lcol (both halves)
    ld de,lo_lcol
    ld b,16
.c:
    ld a,(hl)
    and 15
    rlca
    rlca
    rlca
    rlca
    ld (de),a
    push de
    ld a,e
    add a,16
    ld e,a
    jr nc,.c2
    inc d
.c2:
    ld a,(hl)
    and 15
    rlca
    rlca
    rlca
    rlca
    ld (de),a
    pop de
    inc de
    inc hl
    djnz .c
    ld iy,lo_lcol
    ret
.src:                           ; IX = Konami pattern A's copy
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,LO_SPAT
    add hl,de
    push hl
    pop ix
    ret

; After the 32 entries: the line-coloured patterns to send.
lo_mdone:
    ld a,(lo_mn)
    ld (lo_mpend),a
    ret

lo_enh:     db 0                ; the MSX2 graphics are in
lo_par:     db 0
lo_firesh:  db 0                ; entry 0 drawn in fire colours
lo_mpo:     db 0                ; palette offset of the line-coloured pattern
lo_fpage:   db 0                ; 8K page of this stage's fire patterns                ; 0 or 32: which of the patch's two sprite tables
lo_ltab:    ds 144              ; their sprite line colours (F800-F88F)
lo_lcol:    ds 32
lo_mt:      dw 0
lo_mt2:     dw 0
lo_mn:      db 0
lo_mpend:   db 0
lo_mpi:     db 0
lo_ap1:     db 0
lo_shipt:   db 0
lo_skip1:   db 0
; fixed colours of entries 0-31 (0 = Konami's): this frame, the other frame
lo_efix:
    db 0,0,3,3,15,15,15,11,11,11, 0,0,0,0,0,0,0,0,0,0,0,0, 15,15,15,15,15,15,15,15,15,15
    db 0,0,8,8,15,15,15,11,11,11, 0,0,0,0,0,0,0,0,0,0,0,0, 15,15,15,15,15,15,15,15,15,14
lo_ax:      db 0
lo_ay:      db 0
lo_ap:      db 0
lo_ac:      db 0

; 32 pattern bytes at IX (TMS order: left column rows 0-15, right column)
; in the colours at IY (the same order; fg << 4 | bg) -> 128 bytes of
; 4-bit pattern at DE (moved on).  Preserves IX, IY.
lo_conv:
    ld b,0
.row:
    push bc
    ld a,b
    ld (.r+2),a
    ld (.rc+2),a
    add a,16
    ld (.r2+2),a
    ld (.rc2+2),a
.r:
    ld c,(ix+0)
.rc:
    ld a,(iy+0)
    call .half
.r2:
    ld c,(ix+16)
.rc2:
    ld a,(iy+16)
    call .half
    pop bc
    inc b
    ld a,b
    cp 16
    jr c,.row
    ret
.half:                          ; C's 8 pixels in colours A -> 4 bytes at DE
    ld l,a
    and 15
    ld h,a                      ; bg
    ld a,l
    rrca
    rrca
    rrca
    rrca
    and 15
    ld l,a                      ; fg
    ld b,4
.hb:
    sla c
    ld a,h
    jr nc,.p0
    ld a,l
.p0:
    add a,a
    add a,a
    add a,a
    add a,a
    ld (de),a
    sla c
    ld a,h
    jr nc,.p1
    ld a,l
.p1:
    ex de,hl
    or (hl)
    ld (hl),a
    ex de,hl
    inc de
    djnz .hb
    ret

; From nx_frame (the interrupt) when a new screen has just been shown: send
; the patterns and attributes prepared for it.  Konami's changed patterns
; are converted from the copy (LO_SPAT) in one colour (1).
lo_sprflip:
    ld a,(lo_ppend)
    or a
    jr z,.cobj
    xor a
    ld (lo_ppend),a
    ld ix,LO_SPAT
    ld c,0
.kp:
    ld a,c                      ; changed?
    rrca
    rrca
    rrca
    and 7
    add a,LO_PFLAG&0xff
    ld l,a
    ld h,LO_PFLAG>>8
    ld a,c
    and 7
    ld b,a
    ld a,1
    jr z,.km
.ks:
    add a,a
    djnz .ks
.km:
    and (hl)
    jr z,.kn
    cpl
    and (hl)
    ld (hl),a                   ; (cleared)
    push bc
    ld iy,lo_ones
    ld de,lo_tmp
    call lo_conv
    pop bc
    push bc
    ld a,c
    ld hl,lo_tmp
    call .send
    pop bc
.kn:
    ld de,32
    add ix,de
    inc c
    ld a,c
    cp 64
    jr c,.kp
.cobj:
    ld a,(lo_npend)
    or a
    jr z,.attr
    ld b,a
    ld hl,LO_CPAT
    ld c,64
.cs:
    push bc
    push hl
    ld de,lo_tmp
    ld bc,128
    ldir
    pop hl
    ld bc,128
    add hl,bc
    pop bc
    ld a,c
    push bc
    push hl
    ld hl,lo_tmp
    call .send
    pop hl
    pop bc
    inc c
    djnz .cs
.attr:
    ld a,(lo_mpend)             ; the line-coloured patterns, 96 on
    or a
    jr z,.att
    ld b,a
    ld hl,LO_MPAT
    ld c,96
.ms:
    push bc
    ld a,c
    call .send                  ; (HL moved on 128)
    pop bc
    inc c
    djnz .ms
.att:
    xor a
    ld bc,0x303B
    out (c),a                   ; sprite 0
    ld hl,LO_ATTR
    ld c,0x57
    ld b,0
    otir                        ; 256 bytes...
    ld b,NSPR*5-256
    otir                        ; ...and the rest
    ret
.send:                          ; 4-bit pattern A from HL (moved on)
    ld b,a
    srl a
    rr b                        ; bit 0 -> b bit 7
    ld e,a
    ld a,b
    and 0x80
    or e
    ld bc,0x303B
    out (c),a
    ld c,0x5B
    ld b,128
    otir
    ret

lo_ones:    ds 32,0x10          ; Konami's sprites: set pixels colour 1, clear 0
lo_tmp:     ds 128
