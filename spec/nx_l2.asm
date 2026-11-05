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
LO_ATTR     equ 0x3880          ; 96 sprites x 5 attributes, for the next screen
LO_PFLAG    equ 0x3440          ; Konami patterns changed (64 bits)
LO_MPAT     equ 0x3500          ; MSX2 line-coloured sprites: 6 x 128 (patterns 96-101)
NMULTI      equ 6
NSPR        equ 96
LO_RPAT     equ 0x3800          ; the volcano rocks' fire pattern (pattern 102)
RPAT        equ 102
BPAT        equ 104             ; the boss: 24 patterns, 104-127
LO_QOK      equ 0x3340          ; lo_pieces: the pieces' patterns made (1; 2: no pool)
LO_QN       equ 0x3341          ; the pieces shown,
LO_QTAB     equ 0x3342          ; and each one's X, Y, drawing (8 x 3)
LO_QK       equ 0x335A          ; the boss kind they were made for (E152: 1, 5, 6)
LO_QPP      equ 0x335B          ; lo_qspr: the kind's pattern table (2 bytes)
LO_QG       equ 0x335D          ; the ghosts' sprites (nx_tur: tu_qtick), or 0
L2_BANK0    equ 9
L2_BANK1    equ 13

; Our own drawings of Konami's sprite enemies, after the arcade game's
; (nx_pack.py, art_page(): the drawings in 8K page LO_ART, their tables in
; LO_TAB), in stages whose patterns are stage 1's; the stage's table copied by
; lo_apply.  The character enemies are drawn from the stage's character pool
; (lo_pconv).
LO_ART      equ (25*2+1)
LO_ART2     equ (28*2+1)        ; our drawings 65 on (nx_pack.py ART2_PAGE)
LO_TAB      equ (26*2+1)
TAB_PAL     equ 0x0000          ; LO_TAB: sprite palettes 2-12, then 14 and 15, entries 2-15
TAB_APAL    equ 0x0180          ; the sprite drawings' palette bytes
TAB_PAL6    equ 0x1320          ; stage 6's palette 15 (its brains, lo_pal1415)
TAB_PAL7    equ 0x1340          ; stage 7's (its amoeba)
TAB_STAGE   equ 0x0200          ; 512 bytes a stage: LO_OVR, and at + 40h the
                                ; stage's scenery palette (Layer 2 D1-DF)
TAB_FRAMES  equ 0x1200          ; Konami's frames' four characters (MSX 5:91D1)
TAB_BONUS   equ 0x1400          ; the bonus stages' tables (9-12), 512 bytes each
BONUS_BANK  equ 46              ; the bonus stages' stage file (nx_pack.py)
BONUS_MAPS_BANK equ 47          ; and their character pool maps, 2K each
NART        equ 90              ; sprite drawings at most (LO_APAL: 3CA6-3CFF)
LO_OVR      equ 0x3B00          ; Konami pattern -> our drawing (1 on; 0 none)
LO_APAL     equ 0x3CA6          ; the sprite drawings' palette bytes (palette * 16,
                                ; + 1: the next palette for those leaving a capsule)
LO_OPAL     equ 0x3C70          ; the character enemies recorded: palette offsets (lo_pconv)
LO_OFRM     equ 0x3C90          ; and their frames (byte 12; lo_chars)
lo_cols     equ 0x3D00          ; lo_chars: the recorded characters' colour bytes
                                ; (OBJ_MAX * 32, TMS order; lo_pats has the patterns)
LO_PAL16    equ 0x3FC0          ; the stage's 16 colours (lo_fadestep)
lo_pch      equ 0x3FE0          ; lo_pconv: the frame's four characters,
lo_pblk     equ 0x3FE4          ; their blocks (page, number),
lo_popal    equ 0x3FEC          ; the record's LO_OPAL entry,
lo_pours    equ 0x3FEE          ; bit 7: a block of our drawings,
lo_ppal     equ 0x3FEF          ; its palette * 16
lo_fade     equ 0x3FF0          ; lo_fadestep: 0 before the dissolve's first screen, 1 after
                                ; (29: no fade on this screen, lo_ovclr)
lo_flv      equ 0x3FF1          ; the fade's step (0-21, lo_fprog)
LO_FMAP     equ 0x3FF3          ; and each level (0-7) of a channel at that step (8 bytes)
lo_pq       equ 0x3FF2          ; lo_pconv: the blocks to make (4, or 2: the top two)

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

; The stage graphics (spec/nxgfx, packed by nx_pack.py; they began as the
; MSX2 patch "Nemesis - Gradius ENHANCED"'s): Next bank 15 + stage holds that
; stage's video memory 0000-37FF as its stage load leaves it, its palette at
; 3800 and a mask at 3900 (a bit per byte: written by that load).  After Konami's own load (0:422A, called from
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

; A = stage (1-12: 9-12 the bonus stages, which share a stage file, bank 46,
; and have their maps in bank 47), C = 0: the colour, sprite pattern and pattern copies
; whole; 1: the colour and pattern copies' bottom thirds only.  Sets the
; palette and line-colour tables.
lo_apply:
    push af
    push bc
    call lo_ovclr               ; none of our drawings unless this stage's
    pop bc
    pop af
    dec a
    cp 12
    ret nc
    ld b,a
    ld a,c
    ld (lo_part),a
    ld a,b
    sub 8
    jr c,.norm
    ; a bonus stage (9-12; A = 0-3): its stage file (bank 46, the four share
    ; it) and maps (bank 47), its tables after Konami's frames, stage 2's fire
    ; patterns
    add a,a
    ld b,a
    add a,(0x4000+TAB_BONUS)>>8
    ld (lo_tabh),a
    ld a,b
    add a,a
    add a,a
    add a,0x40
    ld (lo_mbh),a
    ld a,BONUS_MAPS_BANK*2
    ld (lo_mpage),a
    ld a,24*2+2
    ld (lo_fpage),a
    ld a,BONUS_BANK*2
    jr .spg
.norm:                          ; stage - 1 in B
    ld a,b
    add a,a
    ld c,a
    add a,(0x4000+TAB_STAGE)>>8 ; its tables: TAB_STAGE + (stage - 1) * 512
    ld (lo_tabh),a
    ld a,c
    add a,24*2                  ; its fire patterns: bank 24 + stage - 1
    ld (lo_fpage),a
    ld a,b                      ; its map: bank 32, 2K a stage
    rrca
    rrca
    and 1
    add a,64
    ld (lo_mpage),a
    ld a,b
    and 3
    add a,a
    add a,a
    add a,a
    add a,0x40
    ld (lo_mbh),a
    ld a,c
    add a,ENH_BANK*2            ; 8K page of VRAM 0000
.spg:
    ld (lo_spage),a
    inc a
    db 0xED,0x92,0x52           ; its VRAM 2000-3FFF at 4000
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
    ld de,LO_PAL16              ; (and kept for lo_fadestep)
    ld bc,32
    ldir
    xor a
    ld (lo_fade),a
    ld hl,0x5820                ; the patch's sprite line-colour tables
    ld de,lo_ltab
    ld bc,144
    ldir
    ld a,1
    ld (lo_enh),a
    ld a,LO_TAB                 ; our drawings: palettes 2-12 (entries 2-15)
    db 0xED,0x92,0x52
    db 0xED,0x91,0x43,0x20
    ld hl,0x4000+TAB_PAL        ; (and as Layer 2's entries 22h-CFh, for the
    ld c,0x22                   ; character pool's blocks of our drawings)
.pl:
    db 0xED,0x91,0x43,0x20
    call .p28
    db 0xED,0x91,0x43,0x10
    call .p28
    ld de,28
    add hl,de
    ld a,c
    add a,0x10
    ld c,a
    cp 0xD2
    jr c,.pl
    call lo_pal1415             ; and palettes 14 and 15, sprites only
    db 0xED,0x91,0x43,0x00
    ld a,(lo_tabh)              ; this stage's tables
    ld h,a
    ld l,0
    ld de,LO_OVR
    ld bc,64
    ldir
    inc hl                      ; the stage's scenery palette (+ 40h; entry
    inc hl                      ; D0 unused): Layer 2 entries D1-DF
    db 0xED,0x91,0x43,0x10
    db 0xED,0x91,0x40,0xD1
    ld b,30
.sp:
    ld a,(hl)
    db 0xED,0x92,0x44
    inc hl
    djnz .sp
    db 0xED,0x91,0x43,0x00
    ld hl,0x4000+TAB_APAL       ; the sprite drawings' palette bytes
    ld de,LO_APAL
    ld bc,NART
    ldir
    call lo_ovflag              ; patterns 30-63 sent again, as ours
    ld hl,tile_cdirty           ; nothing written since
    ld b,96
.tz:
    ld (hl),0
    set 7,l
    ld (hl),0
    res 7,l
    inc l
    djnz .tz
    ld a,(lo_part)              ; 1: the whole screen; 2: the bottom third
    inc a
    ld (lo_pool),a
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
lo_tabh:    db 0                ; high byte of the stage's tables at 4000 (page LO_TAB)
lo_part:    db 0
lo_mmu7:    db 0
lo_apply.p28:                   ; 28 bytes at HL from entry C (HL kept)
    ld a,c
    db 0xED,0x92,0x40
    push hl
    ld b,28
.b:
    ld a,(hl)
    db 0xED,0x92,0x44
    inc hl
    djnz .b
    pop hl
    ret

; None of our drawings (LO_OVR clear, the character pool off, no fade), and
; Konami's patterns 30-63 sent again (lo_ovflag; lo_sprflip: as ours or
; Konami's).  Preserves DE.
lo_ovclr:
    xor a
    ld (lo_pool),a
    ld a,29
    ld (lo_fade),a
    ld hl,LO_OVR
    ld b,64
.c:
    ld (hl),0
    inc l
    djnz .c
lo_ovflag:
    ld hl,LO_PFLAG+3
    ld a,(hl)
    or 0xC0
    ld (hl),a
    ld b,4
.f:
    inc l
    ld (hl),0xFF
    djnz .f
    ld a,1
    ld (lo_ppend),a
    ret

lo_marcador:
    xor a
    ld (lo_enh),a
    ld (lo_title),a
    push hl
    push bc
    call lo_ovclr
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

; The title screen: the logo (spec/nxgfx/logo.bin, the patch's) replaces
; Konami's (lo_logocell), its palette as Layer 2 entries 10h-1Fh.
LO_LOGO     equ (24*2+1)        ; 8K page: the logo at 0000, its palette at 1800
lo_logopal:
    ld a,i                      ; P/V: interrupts were on
    push af
    di                          ; (6000-7FFF is fixed memory meanwhile)
    db 0xED,0x91,0x53,LO_LOGO   ; at 6000
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
    ; stage 1's 16 colours, for good: the ship's (sprite palette 13, lo_mship;
    ; its entry 1 is Konami's colour 13's, lo_setpal, so the ship's colour 1
    ; is entry 2, which its line colours do not use) and the status line's
    ; (Layer 2 entries F0-FF, lo_cell)
    db 0xED,0x91,0x52,ENH_BANK*2+1      ; stage 1's VRAM 2000-3FFF at 4000
    db 0xED,0x91,0x40,0xD2
    ld hl,0x5802                ; its palette's colour 1 at D2,
    ld b,2
    call .bytes
    ld hl,0x5806                ; and 3-15 at D3-DF
    ld b,26
    call .bytes
    ld hl,0x5800
    db 0xED,0x91,0x43,0x10
    db 0xED,0x91,0x40,0xF0
    call lo_setpal.pal16
    db 0xED,0x91,0x52,0x0A
    db 0xED,0x91,0x43,0x00
    call lo_ovclr
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
.bytes:                         ; B bytes at HL to nextreg 44h
    ld a,(hl)
    db 0xED,0x92,0x44
    inc hl
    djnz .bytes
    ret
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
    ld a,d                      ; tile_pdirty: written since the stage load
    add a,a                     ; (lo_pcell)
    add a,a
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,e
    rrca
    rrca
    rrca
    and 31
    or b
    or 0x80
    ld l,a
    ld h,tile_cdirty>>8
    ld a,e
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
    call lo_fadestep
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
    call lo_tur                 ; stage 5's turrets and skeletons, smooth; the shots
    call lo_sprites
    jp unborrow_page            ; Konami's page back at C000

; Konami's screen dissolve (dz_on: after the stage 7 boss and the stage 8
; brain; it eats the colour and pattern copies in about 35 ticks): the pool
; goes on drawing the scenery (lo_cmap) while Layer 2's colours fade to black
; in 21 steps, as far as Konami's dissolve has gone (lo_fprog): the stage's
; 16 (entries 0-15, from LO_PAL16), palettes 2-12 (entries 22h-CFh, from
; LO_TAB) and the stage's scenery palette (D1h-DFh, from its table in
; LO_TAB), each channel scaled by (21 - step) / 21 and rounded (LO_FMAP), so
; a colour keeps its hue and all of them reach black together; the steps
; fall on different colours at different times, which reads as a fade.  On the dissolve's first screen the stage's 16
; go to entries E0-EF as they are and every cell is drawn again: lo_cell puts
; what Konami spares (the status line, the stars) there.  lo_apply puts it
; all back.
lo_fadestep:
    ld a,(dz_on)
    or a
    ret z
    ld hl,lo_fade
    ld a,(hl)
    cp 29
    ret nc
    or a
    jr z,.first
    call lo_fprog
    ret z
    call .map
    db 0xED,0x91,0x43,0x10      ; Layer 2's first palette
    db 0xED,0x91,0x40,0x00
    ld hl,LO_PAL16
    ld b,16
    call lo_fent
    db 0xED,0x91,0x52,LO_TAB
    ld hl,0x4000+TAB_PAL
    ld c,0x22
.pl:
    ld a,c
    db 0xED,0x92,0x40
    push bc
    ld b,14
    call lo_fent
    pop bc
    ld a,c
    add a,0x10
    ld c,a
    cp 0xD2
    jr c,.pl
    ld a,(lo_tabh)              ; and the stage's scenery palette, D1-DF
    ld h,a
    ld l,0x42
    db 0xED,0x91,0x40,0xD1
    ld b,15
    call lo_fent
    db 0xED,0x91,0x52,0x0A
    db 0xED,0x91,0x43,0x00
    ret
.map:                           ; LO_FMAP for the step: level * (21 - step) / 21, rounded
    ld a,(lo_flv)
    neg
    add a,21
    ld d,a
    ld e,10
    ld hl,LO_FMAP
    ld b,8
.ml:
    ld a,e
    ld c,0xFF
.dl:
    inc c
    sub 21
    jr nc,.dl
    ld (hl),c
    inc hl
    ld a,e
    add a,d
    ld e,a
    djnz .ml
    ret
.first:
    inc (hl)
    ld (lo_flv),a
    call .map
    db 0xED,0x91,0x43,0x10
    db 0xED,0x91,0x40,0xE0
    ld hl,LO_PAL16
    ld b,16
    call lo_fent
    db 0xED,0x91,0x43,0x00
    jp dirty_all

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
lo_cch:     db 0                ; the cell's character

; The stage's character pool (nx_pack.py, char_pool(): 8 x 8 blocks of Layer 2
; pixels, a byte each; the stage's map in bank 32, bit 7 of a block's number
; set for a block of our drawings): lo_pool set by lo_apply, 1 for a stage's
; whole load, 2 for the screen before a stage (the bottom third, the status
; line, only), cleared by lo_ovclr.  A character Konami has written to since
; (its bit in tile_cdirty or tile_pdirty, cleared by lo_apply; lo_rowmark
; sets tile_pdirty's for row updates), or one the map has no block for, is
; drawn from the copies.
lo_pool:    db 0
lo_cm1:     db 0                ; lo_cmap: stage 1's map (the status line)
lo_mpage:   db 0                ; 8K page of the stage's map
lo_mbh:     db 0                ; its high byte at 4000

; Character C of third B: Z, A = its block's page, C = its number (bit 7: ours)
; if the pool has one and Konami has not written to the character since the
; stage load (or the dissolve is under way: dz_on, after the stage 7 boss and
; the stage 8 brain, which eats the copies; the pool goes on showing the
; scenery as lo_fadestep fades it); NZ otherwise.  MMU2 = the map's page.
lo_cmap:
    ld a,(dz_on)
    or a
    jr nz,.map
    ld a,b
    add a,a
    add a,a
    add a,a
    add a,a
    add a,a
    ld e,a                      ; third * 32
    ld a,c
    rrca
    rrca
    rrca
    and 31
    or e
    ld l,a
    ld h,tile_cdirty>>8
    ld a,(hl)
    set 7,l
    or (hl)                     ; tile_pdirty's too
    ld e,a
    ld a,c
    and 7
    inc a
    ld d,a
    ld a,e
.sh:
    rrca
    dec d
    jr nz,.sh                   ; the character's bit to bit 7
    rla
    jr c,.no                    ; written since: the copies
.map:
    ld a,(lo_cm1)               ; the status line: stage 1's map, whatever
    or a                        ; the stage (lo_cell)
    jr nz,.m1
    ld a,(lo_mpage)
    db 0xED,0x92,0x52
    ld a,(lo_mbh)
    jr .m2
.m1:
    db 0xED,0x91,0x52,64        ; stage 1's: page 64, at 4000
    ld a,0x40
.m2:
    add a,b
    add a,b
    ld h,a
    ld a,c
    add a,a
    ld l,a
    jr nc,.h
    inc h
.h:
    ld a,(hl)                   ; the block's page (0: none)
    inc l
    ld c,(hl)
    or a
    jr z,.no
    cp a                        ; Z
    ret
.no:
    or 1                        ; NZ
    ret

; lo_cell's cell (character lo_cch, third lo_third, HL its first pixel) from
; the pool: Z if drawn.  MMU2 is page D's (13) on return.
lo_pcell:
    ld a,(lo_pool)
    dec a
    jr z,.all
    ld a,(lo_third)
    cp 2
    ret nz                      ; the screen before a stage: the bottom third only
.all:
    push hl
    ld a,(lo_third)
    ld b,a
    ld a,(lo_cch)
    ld c,a
    call lo_cmap
    jr nz,.none
    db 0xED,0x92,0x52
    ld a,c                      ; 4000 + number * 64 (bit 7 aside)
    rrca
    rrca
    ld l,a
    and 0x1F
    or 0x40
    ld h,a
    ld a,l
    and 0xC0
    ld l,a
    pop de                      ; the cell's first pixel
    ld a,d
    ld ixh,a                    ; each line's address set afresh (in column
    ld a,(lo_colx)              ; 31 the copies carry into D: the next line
    ld ixl,a                    ; would be skipped and, at the bottom of a
    ld bc,64                    ; third, past FFFF into this bank)
.r:
    ld a,ixh
    ld d,a
    inc a
    ld ixh,a
    ld a,ixl
    ld e,a
    ldi
    ldi
    ldi
    ldi
    ldi
    ldi
    ldi
    ldi
    jp pe,.r
    db 0xED,0x91,0x52,13
    xor a                       ; Z
    ret
.none:
    db 0xED,0x91,0x52,13
    pop hl
    or 1                        ; NZ
    ret

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
    ld a,(hl)                   ; the character
    ld (lo_cch),a
    ld l,a
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
    ld a,(lo_third)             ; the status line (rows 22-23), with the MSX2
    cp 2                        ; graphics in: as in stage 1 throughout the
    jr nz,.nost                 ; game (bonus stages included), stage 1's
    ld a,d                      ; blocks in Layer 2's entries F0-FF (stage
    cp 6                        ; 1's colours, set by lo_init, not faded)
    jr c,.nost
    ld a,(lo_enh)
    or a
    jr z,.nost
    push hl
    ld a,1
    ld (lo_cm1),a
    call lo_pcell.all
    push af
    xor a
    ld (lo_cm1),a
    pop af
    call nz,.two                ; no block: from the copies
    pop hl
    ld e,0xF0
    jr .kor
.nost:
    ld a,(dz_on)                ; the dissolve: what Konami spares (the stars)
    or a                        ; in Layer 2's entries E0-EF, which
    jr z,.draw                  ; lo_fadestep does not fade
    ld a,(lo_cch)
    cp 0xF6
    jr c,.draw
    push hl
    call .draw
    pop hl
    ld e,0xE0
.kor:
    ld c,8
.kl:
    push hl
    ld b,8
.kp:
    ld a,(hl)
    cp 0x10
    jr nc,.kn
    or e
    ld (hl),a
.kn:
    inc l
    djnz .kp
    pop hl
    inc h
    dec c
    jr nz,.kl
    ret
.draw:
    ld a,(lo_pool)              ; from the character pool if it can
    or a
    jr z,.two
    call lo_pcell
    ret z
.two:
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
    ld hl,lo_objs
    ld (lo_cr),hl
    xor a
    ld (lo_ci),a
.cp:
    push bc
    call lo_pconv               ; from the character pool,
    call nz,lo_conv             ; or from the copies
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
    ld (lo_rockp),a
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
    ld a,c                      ; palette offset (0: as drawn; lo_pconv), X bit 8
    sub 64
    add a,LO_OPAL&0xff
    ld l,a
    ld a,h
    ld h,LO_OPAL>>8
    or (hl)
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
    call lo_bossspr
    call lo_qspr
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
; ship's sprites, 2:99A1 and 2:99CF, and leaves its second sprite where the
; first is, 3:A19B) and draws the barrier as a sprite of
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
    ld a,1
    ld (lo_nogr),a
    call lo_attr
    xor a
    ld (lo_nogr),a
    ret
lo_shent:   ds 4
lo_nogr:    db 0

; The rocks the volcanoes throw in stages 1 and 4 (E300 objects of type 0F
; with pattern CC): drawn in fire colours (red edges, orange, yellow), all
; with one pattern (RPAT, from the stage's fire copies, made once a
; screen).  Z if it is one (lo_mpi, lo_mpo set).  From lo_ecol: entry C
; (10-21), preserves BC, DE, HL.
lo_rock:
    ld a,(0xE061-0x3100)
    cp 1
    jr z,.st
    cp 4
    ret nz
.st:
    ld a,(lo_ap)
    cp 0xCC/4
    ret nz
    push hl
    ld a,c                      ; E300 slot C - 10: its type
    sub 10
    rrca
    rrca
    rrca                        ; * 32 (slot < 12)
    ld l,a
    and 0x1F
    ld h,a
    ld a,l
    and 0xE0
    ld l,a
    ld a,h
    add a,(0xE300-0x3100)>>8
    ld h,a
    ld a,(hl)
    pop hl
    cp 0x0F
    ret nz
    ld a,(lo_rockp)
    or a
    jr nz,.have
    push bc
    push de
    push hl
    ld a,(lo_fpage)             ; the fire copy of pattern CC
    db 0xED,0x92,0x52
    ld hl,0x4000+(0xCC/4)*128
    ld de,LO_RPAT
    ld bc,128
    ldir
    db 0xED,0x91,0x52,0x0A
    pop hl
    pop de
    pop bc
    ld a,1
    ld (lo_rockp),a
.have:
    ld a,RPAT
    ld (lo_mpi),a
    ld a,0x10
    ld (lo_mpo),a
    xor a                       ; Z
    ret
lo_rockp:   db 0
lo_rpend:   db 0

; Konami's pattern lo_ap drawn as ours (LO_OVR; sent so by lo_sprflip): Z,
; lo_mpi = the pattern, lo_mpo its palette (the red twin for an E300 object,
; entries 10-21, that leaves a capsule: byte 14 set; Konami makes it red,
; colour 8).  From lo_ecol: entry C, preserves BC, DE, HL.
lo_arc:
    push hl
    ld a,(lo_ap)
    add a,LO_OVR&0xff
    ld l,a
    ld h,LO_OVR>>8
    ld a,(hl)
    or a
    jr z,.no
    add a,(LO_APAL-1)&0xff
    ld l,a
    ld h,LO_APAL>>8
    ld a,(hl)                   ; its palette byte
    bit 0,a
    jr z,.p
    push de
    ld d,a
    ld a,c                      ; E300 slot C - 10
    sub 10
    cp 12
    jr nc,.p0
    rrca
    rrca
    rrca
    ld e,a
    and 0x1F
    add a,(0xE300-0x3100)>>8
    ld h,a
    ld a,e
    and 0xE0
    or 0x0E
    ld l,a
    ld a,(hl)                   ; byte 14: leaves a capsule
    or a
    jr z,.p0
    ld a,d
    add a,0x10
    ld d,a
.p0:
    ld a,d
    pop de
.p:
    and 0xF0
    ld (lo_mpo),a
    ld a,(lo_ap)
    ld (lo_mpi),a
    pop hl
    xor a                       ; Z
    ret
.no:
    pop hl
    or 1                        ; NZ
    ret

; lo_sprites, for character enemy record lo_cr (moved on): its four
; characters as a 4-bit pattern at DE (moved on 128) from the stage's
; character pool, and Z, if the pool is on for the whole screen, the enemy is
; four characters (or four with only the top two taken, on row 21: the bottom
; two left transparent) and the pool has a block for each that Konami has
; not written to since (lo_cmap); NZ otherwise (lo_conv: from the copies).  Its
; frame (the object's byte 12, LO_OFRM: what Konami draws or is about to
; draw; its characters on the screen can lag a tick behind, part old, part
; new) gives the characters (TAB_FRAMES).  An enemy with a block of our
; drawings (bit 7 of the number) loses the stage's colours (pixels below 20h)
; and gets its palette (LO_OPAL + the record's number: palette * 16; 0
; otherwise); the rest keep their pixels.  Preserves IX, IY.
lo_pconv:
    push ix
    ld ix,(lo_cr)
    ld hl,8
    ld bc,(lo_cr)
    add hl,bc
    ld (lo_cr),hl
    ld hl,lo_ci
    ld c,(hl)
    inc (hl)
    ld b,0
    ld hl,LO_OPAL
    add hl,bc
    ld (hl),b
    ld (lo_popal),hl
    ld a,(lo_pool)
    dec a
    jp nz,.no
    ld a,(ix+7)                 ; four characters (1: 4 blocks), or their top
    ld b,4                      ; two (3: 2 blocks)?
    dec a
    jr z,.sz
    ld b,2
    sub 2
    jp nz,.no
.sz:
    ld a,b
    ld (lo_pq),a
    push de
    cp 4
    jr z,.full
    ld h,d                      ; the bottom two left transparent
    ld l,e
    ld b,128
    xor a
.zf:
    ld (hl),a
    inc hl
    djnz .zf
.full:
    ld a,c
    add a,LO_OFRM&0xff
    ld l,a
    ld h,LO_OFRM>>8
    ld l,(hl)                   ; its frame: 4000 + TAB_FRAMES + frame * 4
    ld h,0
    add hl,hl
    add hl,hl
    ld bc,0x4000+TAB_FRAMES
    add hl,bc
    db 0xED,0x91,0x52,LO_TAB
    ld de,lo_pch
    ld bc,4
    ldir
    xor a
    ld (lo_pours),a
    ld (lo_ppal),a
    ld hl,lo_pch
    ld de,lo_pblk
    ld b,a
.q:                             ; B = 0-3: top left, top right, bottom left, right
    push bc
    push hl
    push de
    ld a,b                      ; its third
    srl a
    add a,(ix+2)
    rrca
    rrca
    rrca
    and 3
    ld b,a
    ld c,(hl)
    call lo_cmap
    pop de
    pop hl
    jp nz,.nq
    ld (de),a
    inc de
    ld a,c
    ld (de),a
    inc de
    ld a,(lo_pours)
    or c
    ld (lo_pours),a
    inc hl
    pop bc
    inc b
    ld a,(lo_pq)
    cp b
    jr nz,.q
    ld a,(lo_pours)             ; below 20h: none (ours), or all
    and 0x80
    jr z,.t
    ld a,0x20
.t:
    ld ixh,a
    pop de
    push de
    ld hl,lo_pblk
    ld b,0
.cq:
    push bc
    push hl
    push de
    ld a,b                      ; DE + (B & 2) * 32 + (B & 1) * 4
    and 1
    add a,a
    add a,a
    bit 1,b
    jr z,.c1
    add a,64
.c1:
    add a,e
    ld e,a
    jr nc,.c2
    inc d
.c2:
    ld a,(hl)
    inc hl
    db 0xED,0x92,0x52
    ld a,(hl)                   ; 4000 + number * 64 (bit 7 aside)
    rrca
    rrca
    ld l,a
    and 0x1F
    or 0x40
    ld h,a
    ld a,l
    and 0xC0
    ld l,a
    ld c,8
.cr:
    push de
    ld b,4
.cb:
    call .px
    add a,a
    add a,a
    add a,a
    add a,a
    ld ixl,a
    call .px
    or ixl
    ld (de),a
    inc de
    djnz .cb
    pop de
    ld a,e
    add a,8
    ld e,a
    jr nc,.c3
    inc d
.c3:
    dec c
    jr nz,.cr
    pop de
    pop hl
    inc hl
    inc hl
    pop bc
    inc b
    ld a,(lo_pq)
    cp b
    jr nz,.cq
    ld a,(lo_pours)
    rla
    jr nc,.np
    ld hl,(lo_popal)
    ld a,(lo_ppal)
    ld (hl),a
.np:
    pop hl
    ld de,128
    add hl,de
    ex de,hl
    db 0xED,0x91,0x52,0x0A
    pop ix
    xor a                       ; Z
    ret
.nq:
    pop bc
    pop de
.no:
    db 0xED,0x91,0x52,0x0A
    pop ix
    or 1                        ; NZ
    ret
.px:                            ; the next pixel at HL as a sprite nibble
    ld a,(hl)
    inc hl
    cp ixh
    jr c,.p0
    cp 0x20
    jr c,.pk
    push af
    and 0xF0
    ld (lo_ppal),a
    pop af
.pk:
    and 15
    ret
.p0:
    xor a
    ret
lo_cr:      dw 0
lo_ci:      db 0

; The Big Core (stages 1-6) drawn with sprites so that it moves smoothly.
; Konami draws its 11 x 8 characters into the map at (E785, E783), whole
; characters, and moves it 8 pixels a step: in from the right one step
; every 8 ticks (E190 = 1), then up or down one every 3-5 ticks in runs
; (E190 = 2; E781 running, E787 the way, E78A the ticks to the next step,
; E78B the steps, a run ending after the eleventh).  lo_boss (from lo_tick)
; takes its characters out of name_shadow (as lo_chars does the enemies'),
; makes 24 16x16 patterns of them (only those whose characters changed) and
; works out how far towards its next step it has come; lo_bossspr shows
; them there.  Konami's collisions still use its own position.
lo_boss:
    xor a
    ld (lo_bon),a
    ld a,(0xE061-0x3100)
    dec a
    cp 6
    ret nc
    ld a,(0xE151-0x3100)
    or a
    ret z
    ld a,(0xE780-0x3100)
    cp 1
    ret nz
    ld a,(0xE785-0x3100)
    ld (lo_bx),a
    rrca
    rrca
    rrca
    and 31
    ld (lo_bc0),a
    ld a,(0xE783-0x3100)
    ld (lo_by),a
    rrca
    rrca
    rrca
    and 31
    ld (lo_br0),a
    ; coming in from the right, part of it past column 31, where Konami
    ; (which clips it there, 0:48F7) has drawn nothing: the whole boss from
    ; its own tables, for those cells
    ld a,(lo_bc0)
    cp 21
    call nc,lo_bfill
    ; take the characters: 8 rows of 12
    xor a
    ld (lo_btook),a
    ld ix,lo_bnew
    ld a,(lo_br0)
    ld d,a                      ; row
    ld b,8
.row:
    push bc
    ld a,(lo_bc0)
    ld e,a                      ; column
    ld b,12
.col:
    push bc
    push de
    xor a
    ld (ix+0),a
    ld a,d
    cp 22
    jr nc,.nx
    ld a,e
    cp 32
    jr nc,.off
    ld l,d                      ; index = row * 32 + column
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,l
    or e
    ld l,a
    push hl
    ld bc,MAPK
    add hl,bc
    ld e,(hl)                   ; the background
    pop hl
    push hl
    ld bc,name_shadow
    add hl,bc
    ld a,(hl)
    cp e
    jr z,.same
    ld (ix+0),a
    ld (hl),e
    pop bc                      ; the index: third B, low byte C
    call dirty_cell
    ld a,1
    ld (lo_btook),a
    jr .nx
.off:                           ; past the right edge: from lo_bfull
    ld a,(ix+96)
    ld (ix+0),a
    jr .nx
.same:
    pop hl
.nx:
    inc ix
    pop de
    pop bc
    inc e
    djnz .col
    pop bc
    inc d
    djnz .row
    ld a,(lo_btook)
    or a
    jr nz,.took
    ld a,(lo_blast)             ; not redrawn this tick: as before
    ld (lo_bon),a
    jr .glide
.took:
    call lo_bpats
    ld a,1
    ld (lo_bon),a
    ld (lo_blast),a
.glide:
    ; in from the right: one step every 8 ticks (E003 bit 0-2 at 0)
    xor a
    ld (lo_bdx),a
    ld (lo_bdy),a
    ld a,(0xE155-0x3100)        ; the core dead: no more steps
    or a
    ret nz
    ld a,(0xE190-0x3100)
    cp 1
    jr nz,.up
    ld a,(0xE785-0x3100)
    cp 0x99
    ret c
    ld a,(0xE003-0x3100)
    and 7
    ld (lo_bdx),a
    ret
.up:
    cp 2
    ret nz
    ld a,(0xE781-0x3100)        ; a run under way, a step to come
    or a
    ret z
    ld a,(0xE78B-0x3100)
    cp 0x0A
    ret nc
    ld a,(0xE111-0x3100)        ; the ticks a step, as 1:7E34
    ld c,5
    cp 4
    jr c,.c
    dec c
    cp 10
    jr c,.c
    dec c
.c:
    ld a,(0xE78A-0x3100)        ; ticks to the step: 1..c
    or a
    ret z
    cp c
    ret nc                      ; (c: the step just taken)
    neg
    add a,c                     ; done: 1..c-1
    ld b,a
    ld a,c                      ; 8 * done / c
    sub 3
    add a,a
    add a,a                     ; (c - 3) * 4
    add a,b
    ld hl,.frac
    add a,l
    ld l,a
    jr nc,.f
    inc h
.f:
    ld a,(hl)
    ld b,a
    ld a,(0xE787-0x3100)        ; 0: up
    or a
    ld a,b
    jr nz,.down
    neg
.down:
    ld (lo_bdy),a
    ret
.frac:
    db 0,3,5,0, 0,2,4,6, 0,2,3,5,6      ; 8 * n / c for c = 3, 4, 5 (n < c; c = 5
                                        ; needs index 12: up to 0.110N the 06 of
                                        ; the next routine's first instruction
                                        ; stood in for it, by luck)

; The whole boss into lo_bfull (8 rows of 12, as lo_bnew), as Konami's 1:7E70
; draws it: the body (11 x 8, 1:7EE6), then the eye (3 x 2, one place right
; and three down; 1:7F3E, picked by E789) and the mouth (3 x 2, four right and
; three down; 1:7F62, by the face in E786).
lo_bfill:
    ld hl,lo_bfull
    ld de,lo_bfull+1
    ld bc,95
    ld (hl),0
    ldir
    ld hl,m1_7EF1-11            ; the body (moved to fixed memory)
    ld de,lo_bfull
    ld a,8
.br:
    ld bc,11
    ldir
    inc de                      ; the twelfth column stays empty
    dec a
    jr nz,.br
    ld a,PAGE_A                 ; the eye and the mouth (page A)
    call borrow_page
    ld a,(0xE789-0x3100)        ; (E789 >> 1) & 0E, times 3
    srl a
    and 0x0E
    ld c,a
    add a,a
    add a,c
    ld hl,m1_7F3E
    call .add
    ld de,lo_bfull+3*12+1
    call .three
    ld a,(0xE786-0x3100)        ; the face, times 6
    ld c,a
    add a,a
    add a,c
    add a,a
    ld hl,m1_7F6A-8
    call .add
    ld de,lo_bfull+3*12+4
    call .three
    jp unborrow_page
.add:
    add a,l
    ld l,a
    ret nc
    inc h
    ret
.three:                         ; 3 x 2 from HL to DE
    ld bc,3
    ldir
    ex de,hl
    ld bc,9
    add hl,bc
    ex de,hl
    ld bc,3
    ldir
    ret

; The patterns of the 24 blocks (2 x 2 characters) whose characters (or
; their thirds) changed: the characters' pattern and colour bytes (pages D
; and C), 4-bit patterns by lo_conv, sent to the Next as BPAT on.
lo_bpats:
    ld b,24
    ld c,0                      ; block
.bl:
    push bc
    ; its four characters: rows 2*(c/6) and +1, columns 2*(c%6) and +1
    ld a,c
    ld b,0
.dv:
    cp 6
    jr c,.dd
    sub 6
    inc b
    jr .dv
.dd:
    add a,a
    ld e,a                      ; column in the block grid * 2
    ld a,b
    add a,a
    ld d,a                      ; row * 2
    ld (lo_bbr),a
    ld l,a                      ; lo_bnew + row * 12 + column
    ld h,0
    add hl,hl
    add hl,hl                   ; * 4
    ld a,l
    add a,a
    add a,l                     ; * 12
    add a,e
    ld hl,lo_bnew
    add a,l
    ld l,a
    jr nc,.n1
    inc h
.n1:
    ld a,(hl)
    ld (lo_bk+0),a
    inc hl
    ld a,(hl)
    ld (lo_bk+2),a              ; top right
    ld de,11
    add hl,de
    ld a,(hl)
    ld (lo_bk+1),a              ; bottom left
    inc hl
    ld a,(hl)
    ld (lo_bk+3),a
    ld a,(lo_br0)               ; thirds of the two rows
    ld hl,lo_bbr
    add a,(hl)
    ld (lo_bk+4),a              ; (the top row itself: its third and the next's follow)
    ; changed?
    ld a,c
    ld l,a
    add a,a
    add a,a
    add a,l                     ; * 5
    ld hl,lo_bkey
    add a,l
    ld l,a
    jr nc,.n2
    inc h
.n2:
    push hl
    ld de,lo_bk
    ld b,5
    ld a,0
.cmp:
    ld a,(de)
    cp (hl)
    jr nz,.diff
    inc de
    inc hl
    djnz .cmp
    pop hl
    jr .next
.diff:
    pop de                      ; the key: brought up to date
    ld hl,lo_bk
    push bc
    ld bc,5
    ldir
    pop bc
    ld a,c
    call lo_bconv
.next:
    pop bc
    inc c
    djnz .bl
    ret

; Block A: lo_bk's characters (top left, bottom left, top right, bottom
; right; the top row in lo_bk+4) -> 4-bit pattern BPAT + A, sent.
lo_bconv:
    jp lo_bart                  ; the arcade's drawing instead (nx_tur.asm tu_bc)
    push af
    ld a,PAGE_D
    call borrow_page
    ld hl,lo_bpp
    call .four
    ld a,PAGE_C
    call borrow_page
    ld hl,lo_bpc
    call .four
    call unborrow_page
    pop af
    add a,BPAT
    ld (lo_bsend),a
    ; Made and sent with interrupts on: one that comes while they are off can
    ; be lost on the Next, and the status lines' scroll split (line 176)
    ; depends on the interrupts alternating.  The frame interrupt makes and
    ; sends patterns of its own (lo_sprflip, through lo_conv, which keeps
    ; its row in its own code, and the selection at 303Bh): it sets lo_brst,
    ; and this pattern is made and sent again.  Made in lo_btmp, not lo_tmp
    ; (the interrupt's); the rest of an interrupted send goes to pattern
    ; 103, where lo_sprflip leaves the selection.
.again:
    xor a
    ld (lo_brst),a
    ld ix,lo_bpp
    ld iy,lo_bpc
    ld de,lo_btmp
    call lo_conv
    ld hl,lo_btmp
    ld a,(lo_bsend)
    call lo_sprflip.send
    ld a,(lo_brst)
    or a
    jr nz,.again
    ret
.four:                          ; the four characters' 8 bytes each to HL
    ex de,hl
    ld a,(lo_bk+4)
    ld c,a
    ld a,(lo_bk+0)
    call .ch
    inc c
    ld a,(lo_bk+1)
    call .ch
    dec c
    ld a,(lo_bk+2)
    call .ch
    inc c
    ld a,(lo_bk+3)
.ch:                            ; character A of row C (its third) -> DE
    push bc
    or a
    jr z,.zero
    ld l,a                      ; E800 + third * 0x800 + A * 8
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,c
    and 0x18                    ; third * 8 = third * 0x800 / 0x100
    add a,0xE8
    add a,h
    ld h,a
    ld bc,8
    ldir
    pop bc
    ret
.zero:
    xor a
    ld b,8
.z:
    ld (de),a
    inc de
    djnz .z
    pop bc
    ret

; The boss's sprites at DE (moved on), after the others: each block with
; something in it, at the boss's position less lo_bdx and plus lo_bdy.
lo_bossspr:
    ld a,(lo_bon)
    or a
    ret z
    ld a,(spr_on)
    or a
    ret z
    ld c,0
.b:
    push bc
    ld a,c                      ; empty?
    ld l,a
    add a,a
    add a,a
    add a,l
    ld hl,lo_bkey
    add a,l
    ld l,a
    jr nc,.k
    inc h
.k:
    ld a,(hl)
    inc hl
    or (hl)
    inc hl
    or (hl)
    inc hl
    or (hl)
    jr z,.skip
    ld a,c                      ; grid position
    ld b,0
.dv:
    cp 6
    jr c,.dd
    sub 6
    inc b
    jr .dv
.dd:
    ; X = lo_bx - lo_bdx + column * 16 + 32
    add a,a
    add a,a
    add a,a
    add a,a
    ld l,a
    ld h,0
    ld a,(lo_bx)
    add a,l
    ld l,a
    jr nc,.x1
    inc h
.x1:
    ld a,(lo_bdx)
    neg
    jr z,.x2
    add a,l
    ld l,a
    jr c,.x2
    dec h
.x2:
    ld a,l
    add a,32
    ld l,a
    jr nc,.x3
    inc h
.x3:
    ld a,l
    ld (de),a
    inc de
    ; Y = lo_by + lo_bdy + row * 16 + 32
    ld a,b
    add a,a
    add a,a
    add a,a
    add a,a
    ld l,a
    ld a,(lo_by)
    add a,l
    ld l,a
    ld a,(lo_bdy)
    add a,l
    add a,32
    ld (de),a
    inc de
    ld a,h                      ; palette 15 (the arcade's drawing), X bit 8
    and 1
    or 0xF0
    ld (de),a
    inc de
    pop bc
    push bc
    ld a,c
    add a,BPAT
    ld b,a
    srl a
    or 0xC0                     ; visible, a fifth attribute
    ld (de),a
    inc de
    ld a,b
    and 1
    rrca
    rrca                        ; N6
    or 0x80                     ; 4-bit
    ld (de),a
    inc de
.skip:
    pop bc
    inc c
    ld a,c
    cp 24
    jr c,.b
    ret

lo_bon:     db 0                ; the boss shown as sprites this screen
lo_bsend:   db 0                ; the boss pattern being sent (lo_bconv)
lo_brst:    db 0                ; lo_sprflip ran meanwhile: send it again
lo_blast:   db 0
lo_btook:   db 0
lo_bx:      db 0
lo_by:      db 0
lo_bc0:     db 0
lo_br0:     db 0
lo_bdx:     db 0
lo_bdy:     db 0
lo_bbr:     db 0
lo_bk:      ds 5
lo_bkey:    ds 24*5,0xFF        ; per block: its characters and top row as made
lo_bnew:    ds 96               ; this tick's characters, 8 rows of 12
lo_bfull:   ds 96               ; the whole boss, as lo_bnew (lo_bfill): at lo_bnew + 96
lo_bpp:     ds 32
lo_bpc:     ds 32
lo_btmp:    ds 128              ; the boss pattern being made (lo_bconv, lo_qmake)

; Stage 3's boss (Konami's boss 1; boss 6 on later rounds, one piece): up to
; eight round pieces in the slots at E780 (16 bytes each: byte 0 alive, Y in
; byte 3 and X in byte 5, whole pixels, byte 6 the drawing).  Konami moves
; them a pixel at a time but draws each as 4 x 4 characters into the map at
; cell (Y / 8, X / 8) (2:86D9; 1:6936 saves what was there, 1:6A37 puts it
; back after the map comparison), so they jump 8 pixels.  lo_pieces (from
; lo_tick) takes their characters out of name_shadow (as lo_chars does the
; enemies'), with the background (Konami's map now) put back, and notes
; where each is; lo_qspr shows them there as four 16 x 16 sprites each.  The
; six patterns (the two drawings, 2:86F1 and 2:8701, share their right
; halves) are made once a boss from the character pool (third 0's blocks;
; the stage has the same in all three) into the Big Core's patterns
; (BPAT on; it is never on screen with them).  Without the pool's blocks the
; pieces are left in the map as before.  Konami's collisions use its own
; position, which is the sprites'.
; Stage 4's mid-boss (Konami's boss 5) is the same machinery: up to eight
; flyers in the same slots, moved 2 pixels a tick along a fixed route (2:8D7C
; on) and drawn as 4 x 3 characters with blank corners (2:8E45 through 0:490C:
; the corners are written as character 00, which lifting them out leaves
; showing the background), two drawings alternating every 4 frames (2:8E5F,
; 2:8E6B; told apart by the middle row's first character, BC or C2).
lo_pieces:
    call lo_qgh                 ; the ghosts first (LO_QTAB still last tick's)
    xor a
    ld (LO_QN),a
    ld hl,0xE151-0x3100
    ld a,(hl)
    or a
    jr z,.off
    inc hl
    ld a,(hl)
    cp 1
    jr z,.on
    cp 2
    jp z,lo_brain               ; stage 6's brains: nx_tur.asm
    cp 5
    jr z,.on
    cp 6
    jr z,.on
.off:
    xor a
    ld (LO_QOK),a
    ret
.on:
    ld (LO_QK),a
    ld a,(LO_QOK)
    or a
    call z,lo_qmake
    ld a,(LO_QOK)
    dec a
    ret nz
    ld ix,0xE780-0x3100
    ld iy,LO_QTAB
    ld a,(LO_QK)                ; eight slots, or the first only (boss 6;
    ld b,8                      ; as Konami's 1:6936)
    cp 6
    jr nz,.pc
    ld b,1
.pc:
    push bc
    ld a,(ix+0)
    or a
    jr z,.nx
    ld hl,LO_QN
    inc (hl)
    ld a,(ix+3)                 ; HL = MAPK + (Y / 8) * 32 + X / 8 (rows
    and 0xF8                    ; up to 21: Y stays below 91h, 2:85E4; at
    ld l,a                      ; 88h at most for boss 5, 2:8DF0)
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(ix+5)
    rrca
    rrca
    rrca
    and 31
    ld e,a                      ; the column
    or l
    ld l,a
    ld a,h
    add a,MAPK>>8
    ld h,a
    ld a,(ix+5)                 ; X, Y, drawing for lo_qspr
    ld (iy+0),a
    ld a,(ix+3)
    ld (iy+1),a
    ld d,4                      ; rows taken out
    ld a,(LO_QK)
    cp 5
    ld a,(ix+6)
    jr nz,.dr
    dec d                       ; boss 5: three rows, and the drawing from
    push hl                     ; the middle row's first character as
    ld bc,name_shadow-MAPK+32   ; Konami wrote it (C2: the second)
    add hl,bc
    ld a,(hl)
    pop hl
    sub 0xC2
    cp 1
    ccf
    sbc a,a
    inc a                       ; C2 -> 1, else 0
.dr:
    ld (iy+2),a
    inc iy
    inc iy
    inc iy
.r:
    push hl
    ld b,4
    ld c,e
.c:
    ld a,c
    cp 32
    jr nc,.rd                   ; past column 31 (coming in): not drawn
    ld a,(hl)                   ; the background
    push hl
    push de
    ld de,name_shadow-MAPK
    add hl,de
    pop de
    cp (hl)
    jr z,.same
    ld (hl),a
    pop hl
    push bc
    ld c,l                      ; the index: third B, low byte C
    ld a,h
    sub MAPK>>8
    ld b,a
    call dirty_cell
    pop bc
    jr .cn
.same:
    pop hl
.cn:
    inc hl
    inc c
    djnz .c
.rd:
    pop hl
    ld a,l
    add a,32
    ld l,a
    jr nc,.rn
    inc h
.rn:
    dec d
    jr nz,.r
.nx:
    ld bc,16
    add ix,bc
    pop bc
    dec b
    jp nz,.pc
    ret

; lo_qmake, lo_qspr, lo_tur, lo_tcell, lo_isec, lo_lcod and lo_c0 are kept in
; free parts of the bank's RAM map (the code must end below LO_SPAT):
; 3360-343F, 3448-34FF and 3B40-3C6F.
lo_qret = $
    org 0x3360
; The six patterns, sent as lo_bconv sends the Big Core's: LO_QOK 1, or 2 if
; the pool has no block for one of the characters (character 00: none, the
; quarter left transparent).
lo_qmake:
    ld hl,lo_bkey               ; the Big Core's patterns: made again when
    ld de,lo_bkey+1             ; it is next shown
    ld bc,24*5-1
    ld (hl),0xFF
    ldir
    ld a,2
    ld (LO_QOK),a
    ld a,(lo_pool)
    dec a
    ret nz
    ld a,(LO_QK)
    cp 5
    ld hl,lo_qch
    jr nz,.k
    ld hl,lo_qch5
.k:
    ld a,BPAT
.p:
    ld (lo_bsend),a
    push hl
    ld hl,lo_btmp               ; transparent to begin with
    ld de,lo_btmp+1
    ld bc,127
    ld (hl),0
    ldir
    pop hl
    push hl
    ld b,0
.q:                             ; B = 0-3: top left, top right, bottom left, right
    push bc
    push hl
    ld c,(hl)
    ld a,c
    or a
    jr z,.qe                    ; character 00: nothing
    ld b,0
    call lo_cmap
    jr nz,.fail
    db 0xED,0x92,0x52
    ld a,c                      ; 4000 + number * 64
    rrca
    rrca
    ld l,a
    and 0x1F
    or 0x40
    ld h,a
    ld a,l
    and 0xC0
    ld l,a
    pop de
    pop bc
    push bc
    push de
    ld a,b                      ; lo_btmp + (B & 2) * 32 + (B & 1) * 4
    and 1
    add a,a
    add a,a
    bit 1,b
    jr z,.d1
    add a,64
.d1:
    add a,lo_btmp&0xff
    ld e,a
    ld a,0
    adc a,lo_btmp>>8
    ld d,a
    ld c,8
.row:
    ld b,4
.px:                            ; two pixels a byte (the stage's colours:
    ld a,(hl)                   ; pixels 0-15, palette offset 0)
    inc hl
    add a,a
    add a,a
    add a,a
    add a,a
    ld (de),a
    ld a,(hl)
    inc hl
    and 15
    ex de,hl
    or (hl)
    ld (hl),a
    ex de,hl
    inc de
    djnz .px
    ld a,e
    add a,4
    ld e,a
    jr nc,.rw
    inc d
.rw:
    dec c
    jr nz,.row
.qe:
    pop hl
    inc hl
    pop bc
    inc b
    ld a,b
    cp 4
    jr nz,.q
.send:
    xor a
    ld (lo_brst),a
    ld hl,lo_btmp
    ld a,(lo_bsend)
    call lo_sprflip.send
    ld a,(lo_brst)
    or a
    jr nz,.send
    pop hl
    ld bc,4
    add hl,bc
    ld a,(lo_bsend)
    inc a
    cp BPAT+6
    jp nz,.p
    ld a,1
    ld (LO_QOK),a
    jr .out
.fail:
    pop hl
    pop bc
    pop hl
.out:
    db 0xED,0x91,0x52,0x0A
    ret
; Stage 5's turrets and skeletons drawn smooth, and in every stage the shots
; and the laser drawn over the scenery (nx_tur.asm): its code and
; variables are in 8K page LO_TURP (nx_pack.py), at 6000 for the call; the
; page's 6000-7FFF is back as it was (MMU3 0Bh: lo_cells has put it back).
LO_TURP     equ 55
lo_tur:
    db 0xED,0x91,0x53,LO_TURP
    call 0x6000
    db 0xED,0x91,0x53,0x0B
    ret
    assert $ <= LO_PFLAG

    org 0x3448
; For nx_tur.asm: cell D (row in the third lo_third), column E, drawn as
; lo_cells draws it (the screen's third at MMU6/7 already), with nx_tur's
; page at 6000 again on return.  IX and IY not kept.
lo_tcell:
    db 0xED,0x91,0x52,13
    db 0xED,0x91,0x53,9
    call lo_cell
    db 0xED,0x91,0x53,LO_TURP
    db 0xED,0x91,0x52,0x0A
    ret

; Stage 6's brains (Konami's boss 2), in nx_tur.asm's page: lo_brain from
; lo_pieces (LO_QK 2; takes them out of the map and works out their
; sprites), lo_bspr from lo_qspr (the sprites at DE, moved on).
lo_brain:
    ld (LO_QK),a
    db 0xED,0x91,0x53,LO_TURP
    call 0x6003
    db 0xED,0x91,0x53,0x0B
    ret
lo_bspr:
    db 0xED,0x91,0x53,LO_TURP
    call 0x6006
    db 0xED,0x91,0x53,0x0B
    ret
; Pieces Konami takes off at the left edge (stages 3 and 4), and brains left
; when stage 6's boss ends, gliding off: lo_qgh from lo_pieces, their sprites
; through lo_bspr.
lo_qgh:
    db 0xED,0x91,0x53,LO_TURP
    call 0x6009
    db 0xED,0x91,0x53,0x0B
    ret
; The Big Core's block A in the arcade's drawing, sent (from lo_bpats, in
; place of lo_bconv's).
lo_bart:
    db 0xED,0x91,0x53,LO_TURP
    call 0x600C
    db 0xED,0x91,0x53,0x0B
    ret

; The MSX2 patch's colour 80 for Konami's objects (entries 10-21; its type
; 1C, the stars stage 5's skeletons release) is its line-colour table 80,
; not the early clock with colour 0: the patch shows it where it is.
; lo_isec: NZ if entry C's sprite has the early clock.  lo_lcod: A = entry
; C's colour (10-21), the early clock aside, 80 kept.  Both preserve BC, DE,
; HL.
lo_isec:
    ld a,(lo_ac)
    cp 0x80
    jr nz,.b
    ld a,c
    sub 10
    cp 12
    jr c,.no                    ; the patch's 80
    ld a,0x80
.b:
    bit 7,a
    ret
.no:
    xor a
    ret
lo_lcod:
    ld a,(lo_ac)
    cp 0x80
    ret z
    and 0x7f
    ret

; Konami's colour 0 for entry C (10-21: E300 slot C - 10), as the patch shows
; it: 8 on one screen (lo_par 0), 0A on the next; in stage 3 5 and 0A, and
; there the Moai's rings (type 0E) 5 and 0D (our choice).  A = the colour.
; Preserves BC, DE, HL.
lo_c0:
    ld a,(0xE061-0x3100)
    cp 3
    jr nz,.n
    push hl
    push de
    ld a,c
    sub 10
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,0xE300-0x3100
    add hl,de
    ld a,(hl)                   ; its type
    pop de
    pop hl
    cp 0x0E
    ld a,(lo_par)
    jr z,.ring
    or a
    ld a,5
    ret z
    ld a,0x0A
    ret
.ring:
    or a
    ld a,5
    ret z
    ld a,0x0D
    ret
.n:
    ld a,(lo_par)
    or a
    ld a,8
    ret z
    ld a,0x0A
    ret
    assert $ <= LO_MPAT

    org 0x3A60
; The dissolve's fade (lo_fadestep): the step from how far Konami's dissolve
; has gone (3:A6C0: E1A0 0 while it turns the backgrounds black, which it does
; in its first tick; 1 while it eats the patterns, a quarter of the table a
; tick, E1A1 the quarter (0, 40h, 80h, C0h), E1A2 the mask, FEh, FCh ... 80h,
; then 00h; 2 on when all is black), 0-32 quarters, as a step of 21: P * 21 /
; 32.
; Z: the same step as before; NZ: a new one, in lo_flv.
lo_fprog:
    ld a,(0xE1A0-0x3100)
    or a
    jr z,.p                     ; the backgrounds: 0
    dec a
    ld a,32
    jr nz,.p                    ; all black
    ld a,(0xE1A2-0x3100)        ; the patterns: the mask's pass (FE 1 ... 00 8)
    ld b,8
    or a
    jr z,.n
    ld b,0
.tz:
    rrca
    jr c,.n
    inc b
    jr .tz
.n:
    ld a,b
    dec a
    add a,a
    add a,a
    ld b,a
    ld a,(0xE1A1-0x3100)        ; and the quarters of this pass done
    rlca
    rlca
    and 3
    add a,b
.p:
    ld l,a                      ; * 21 / 32
    ld h,0
    ld d,h
    ld e,l
    add hl,hl
    add hl,hl
    add hl,de
    add hl,hl
    add hl,hl
    add hl,de
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,h
    ld hl,lo_flv
    cp (hl)
    ret z
    ld (hl),a
    or 1                        ; NZ
    ret

; B colours at HL (moved on, two bytes each: RRRGGGBB, then B's low bit),
; each channel through LO_FMAP, to the palette entries from the one selected.
lo_fent:
    push bc
    ld a,(hl)                   ; RRRGGGBB
    inc hl
    ld d,a
    rlca
    rlca
    rlca
    and 7
    call .dn
    rrca
    rrca
    rrca
    ld e,a                      ; R
    ld a,d
    rrca
    rrca
    and 7
    call .dn
    add a,a
    add a,a
    or e
    ld e,a                      ; R, G
    ld a,(hl)                   ; the second byte: B's low bit in bit 0
    rra
    ld a,d
    rla
    and 7
    call .dn
    ld b,a
    srl a
    or e
    db 0xED,0x92,0x44
    ld a,(hl)
    inc hl
    and 0xFE
    srl b
    adc a,0
    db 0xED,0x92,0x44
    pop bc
    djnz lo_fent
    ret
.dn:
    push hl
    ld hl,LO_FMAP
    add a,l
    ld l,a
    ld a,(hl)
    pop hl
    ret
    assert $ <= LO_OVR

    org 0x3B40

; The pieces' sprites at DE (moved on), after the others, as many as fit.
lo_qspr:
    ld a,(spr_on)
    or a
    ret z
    ld a,(LO_QN)
    or a
    jr nz,.any
    ld a,(LO_QG)                ; none: any ghosts
    or a
    ret z
    jp lo_bspr
.any:
    ld b,a
    ld a,(LO_QK)                ; the kind's patterns
    cp 2
    jp z,lo_bspr                ; stage 6's brains: nx_tur.asm
    cp 5
    ld hl,lo_qpat
    jr nz,.k
    ld hl,lo_qpat5
.k:
    ld (LO_QPP),hl
    ld ix,LO_QTAB
.p:
    push bc
    ld c,0
.q:
    ld a,e                      ; all 96 in use: no more
    cp (LO_ATTR+NSPR*5)&0xff
    jr nz,.ok
    ld a,d
    cp (LO_ATTR+NSPR*5)>>8
    jr z,.full
.ok:
    ld a,c                      ; X + 32 (+ 16 on the right)
    and 1
    add a,a
    add a,a
    add a,a
    add a,a
    add a,32
    ld h,0
    add a,(ix+0)
    jr nc,.x
    inc h
.x:
    ld (de),a
    inc de
    ld a,c                      ; Y + 32 (+ 16 below)
    and 2
    add a,a
    add a,a
    add a,a
    add a,32
    add a,(ix+1)
    ld (de),a
    inc de
    ld a,h                      ; palette offset 0, X bit 8
    ld (de),a
    inc de
    ld a,(ix+2)                 ; the pattern
    or a
    ld a,c
    jr z,.a
    add a,4
.a:
    ld hl,(LO_QPP)              ; the kind's patterns
    add a,l
    ld l,a
    jr nc,.h
    inc h
.h:
    ld a,(hl)
    ld b,a
    srl a
    or 0xC0                     ; visible, a fifth attribute
    ld (de),a
    inc de
    ld a,b
    and 1
    rrca
    rrca                        ; N6
    or 0x80                     ; 4-bit
    ld (de),a
    inc de
    inc c
    ld a,c
    cp 4
    jr nz,.q
    inc ix
    inc ix
    inc ix
    pop bc
    djnz .p
    jp lo_bspr                  ; and the ghosts (nx_tur)
.full:
    pop bc
    ret

; Each pattern's four quarters (top left, top right, bottom left, bottom
; right), and each drawing's patterns (top left, top right, bottom left,
; bottom right; the second drawing's four follow).
lo_qch:                         ; stage 3's pieces (2:86F1, 2:8701)
    db 0xA6,0xA7,0xAA,0xAB, 0xA8,0xA9,0xAC,0xAD
    db 0xB6,0xB7,0xB2,0xB3, 0xB8,0xB9,0xB4,0xB5
    db 0xAE,0xA7,0xAF,0xAB, 0xBB,0xB7,0xBA,0xB3
lo_qpat:                        ; byte 6 0, or not
    db BPAT,BPAT+1,BPAT+2,BPAT+3, BPAT+4,BPAT+1,BPAT+5,BPAT+3
lo_qch5:                        ; stage 4's flyers (2:8E5F, 2:8E6B: 4 x 3)
    db 0x00,0xBA,0xBC,0xBD, 0xBB,0x00,0xBE,0xBF     ; the first drawing's top
    db 0x00,0xC0,0x00,0x00, 0xC1,0x00,0x00,0x00     ; the bottom row, shared
    db 0x00,0xBA,0xC2,0xC3, 0xBB,0x00,0xC4,0xC5     ; the second drawing's top
lo_qpat5:                       ; middle row BC, or C2
    db BPAT,BPAT+1,BPAT+2,BPAT+3, BPAT+4,BPAT+5,BPAT+2,BPAT+3

; Sprite palettes 14 and 15 (entries E2-EF, F2-FF; entry 1 of each is a Konami
; colour's, lo_setpal) from TAB_PAL, after palettes 2-12: our drawings of
; stage 5's enemies.  Sprites only: Layer 2's E0-FF are the dissolve's copy
; and the status line's (lo_cell).  From lo_apply, LO_TAB at 4000.
lo_pal1415:
    db 0xED,0x91,0x43,0x20
    ld hl,0x4000+TAB_PAL+11*28
    ld c,0xE2
    call lo_apply.p28
    ld de,28
    add hl,de
    ld a,(0xE061-0x3100)        ; stages 6 and 7: their own palette 15
    cp 6
    jr nz,.p7
    ld hl,0x4000+TAB_PAL6
.p7:
    cp 7
    jr nz,.p15
    ld hl,0x4000+TAB_PAL7
.p15:
    ld c,0xF2
    jp lo_apply.p28

    assert $ <= LO_OPAL

    org lo_qret

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
    ld a,(lo_nogr)              ; (not the barrier: E300 slot 0's flag is not its)
    or a
    jr nz,.x
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
    call lo_isec
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
    call lo_arc                 ; our own drawings
    ret z
    ld a,c
    cp 10
    jr c,.fixed
    cp 22
    jr nc,.fixed
    call lo_rock                ; the volcano rocks: fire colours
    ret z
    call lo_lcod                ; the colour, the early clock aside
    cp 0x10
    jr nc,.tab
    or a
    ret nz                      ; Konami's own (carry clear)
    call lo_c0                  ; 8 and 0A (stage 3: lo_c0)
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
    jp lo_mship
.solo:
    pop hl
    ld hl,0
    ld (lo_mt2),hl
    jp lo_mship_hl
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
    jp lo_mship

; The ship's line-coloured pattern (lo_multi), in sprite palette 13: stage
; 1's colours throughout the game (lo_init), not the stage's.
lo_mship_hl:
lo_mship:
    ld a,1
    ld (lo_shipc),a
    call lo_multi
    push af
    xor a
    ld (lo_shipc),a
    pop af
    ret c
    ld a,0xD0
    ld (lo_mpo),a
    or a
    ret
lo_shipc:   db 0

; Konami pattern lo_ap's fire-coloured copy (Next bank 24 + stage, made
; by nx_pack.py) -> LO_MPAT slot lo_mn, palette offset 1.
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
    cp 1                        ; the ship's colour 1: entry 2 of its palette
    jr nz,.c1                   ; (lo_mship)
    ld a,(lo_shipc)
    inc a
.c1:
    rlca
    rlca
    rlca
    rlca
    ld (de),a
    ld c,a
    push de
    ld a,e
    add a,16
    ld e,a
    jr nc,.c2
    inc d
.c2:
    ld a,c                      ; the same colour for the right half
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
    ld a,(lo_rockp)
    ld (lo_rpend),a
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
    ld a,1                      ; a boss pattern being sent: send it again
    ld (lo_brst),a
    ld a,(lo_ppend)
    or a
    jp z,.cobj
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
    ld a,c                      ; one of ours? (lo_arc)
    add a,LO_OVR&0xff
    ld l,a
    ld h,LO_OVR>>8
    ld a,(hl)
    or a
    jr nz,.kw
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
    jr .kn
.kw:                            ; our drawing A (from 1)
    push bc
    ld e,a
    ld a,0x52                   ; MMU2 as it is (put back after)
    ld bc,0x243B
    out (c),a
    inc b
    in a,(c)
    push af
    ld a,e                      ; 1-64 in LO_ART, 65 on in LO_ART2
    cp 65
    ld a,LO_ART
    jr c,.k1
    ld a,e
    sub 64
    ld e,a
    ld a,LO_ART2
.k1:
    db 0xED,0x92,0x52
    pop af
    pop bc
    push af
    push bc
    ld a,e                      ; 4000 + (drawing - 1) * 128
    dec a
    rrca
    ld h,a
    and 0x80
    ld l,a
    xor h
    add a,0x40
    ld h,a
    ld a,c
    call .send
    pop bc
    pop af
    db 0xED,0x92,0x52
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
    ld a,(lo_rpend)             ; the rocks' pattern
    or a
    jr z,.att0
    ld a,RPAT
    ld hl,LO_RPAT
    call .send
.att0:
    xor a
    ld bc,0x303B
    out (c),a                   ; sprite 0
    ld hl,LO_ATTR
    ld c,0x57
    ld b,0
    otir                        ; 256 bytes...
    ld b,NSPR*5-256
    otir                        ; ...and the rest
    ld a,0xB3                   ; pattern 103 (unused) selected: what is left
    ld bc,0x303B                ; of a boss pattern being sent goes there
    out (c),a
    ret
.send:                          ; 4-bit pattern A from HL (moved on)
lo_psend:                       ; (for nx_tur.asm)
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
