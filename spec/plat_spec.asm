; MSX Nemesis on a standard ZX Spectrum 128K: platform layer.
;
; Konami's code (MSX banks 0-3 and 7, relocated by reloc/gen.py with
; NEM_TARGET=spec) runs unchanged except at the hardware boundary.  This file
; provides that boundary: the Konami4 mapper on Spectrum paging, the MSX BIOS
; entry points Konami calls, the VDP data port, the PSG (as the 128K's AY),
; the keyboard and joystick, the interrupt, and the main loop.
;
; Memory:
;   4000-5AFF  screen 0 (bank 5)
;   5B00-7B1F  MSX bank 0 (fixed), 7C00-7C5F moved data
;   8000-ACFF  this platform, the renderer, far-call stubs, buffers
;   AD00-AE00  IM2 vector table, AEAE jump to the ISR, stack below AEA0, AEB4-AEF3 dc_buf
;   AF00-BFFF  Konami's RAM (MSX E000-F0FF), including its stack (BFF0 down)
; Paged at C000:
;   page A (bank 0) MSX 1+2      page B (bank 3) MSX 4+5 (graphics source)
;   page C (bank 4) MSX 3, title logo data E020-E5BB, VRAM colour shadow E800-FFFF
;   page D (bank 6) MSX 7+8 (sound), VRAM pattern shadow E800-FFFF
;   page E (bank 1) MSX 11+12 (map pieces and scripts)
;   page 7 (bank 7) screen 1 C000-DAFF, converted tile set DB00-F5FF,
;                   sprite patterns F800-FFFF
;
; Timing: the IM2 interrupt (50Hz) runs Konami's sound driver, as the MSX's
; did.  The main loop runs one Konami game tick, converts any tiles Konami
; uploaded, draws the hidden screen and flips it every FRAMES_PER_TICK frames.

    device zxspectrum128

PAGE_A equ 0
PAGE_E equ 1
PAGE_B equ 3
PAGE_C equ 4
PAGE_D equ 6
PAGE_7 equ 7

    ifndef FRAMES_PER_TICK
FRAMES_PER_TICK equ 2
    endif
    ifndef LOGIC_EXTRA
LOGIC_EXTRA equ 4               ; a tick without drawing after every 4 drawn (0: none)
    endif
    ifndef PACE_PAL_MIX
PACE_PAL_MIX equ 0
    endif

KRAM equ 0xAF00 - 0xE000          ; add to an MSX RAM address
TILE_PAGES equ 0xDB                ; converted tiles: page TILE_PAGES+9*third+row, low byte = id
SPR_PAT equ 0xF800                 ; sprite pattern table (VRAM 1800-1FFF), page 7
COL_SHADOW equ 0xE800              ; VRAM 0000-17FF, page C
PAT_SHADOW equ 0xE800              ; VRAM 2000-37FF, page D

    ifndef HOLD_TICKS
HOLD_TICKS equ 12               ; fire held this many ticks: power-up as well (fire_hold)
    endif

    macro section_fixed
        org 0x5B00
    endm
    macro section_fixed2
        org 0x7C00
    endm
    macro section_A
        slot 3
        page PAGE_A
        org 0xC000
    endm
    macro section_C
        slot 3
        page PAGE_C
        org 0xC000
    endm
    macro section_D
        slot 3
        page PAGE_D
        org 0xC000
    endm
    macro section_E               ; code moved to page E (gen.py ITEM_MOVES), where the colour fit was
        slot 3
        page PAGE_E
        org 0xFB04
    endm
    macro section_data pg, base
        slot 3
        page pg
        org base
    endm

    include "konami_spec.asm"

; The dissolve's pattern chunks (0.107), here since 0.109 to make room in
; 8000-96FF: rarely run, so contended memory does not matter.
; The native build's loads and dissolve (native.asm), after Konami's bank 0
; (shorter by the loaders it leaves out).
    org section_fixed_end
    include "native.asm"
    ifndef NEXT
    include "native_tables.asm"
    else
    include "native_tables_next.asm"    ; (native_next.py)
    endif
native_end:
    assert native_end <= edge_pat
    org 0x7C58
    assert section_fixed2_end <= 0x7C58
; ===========================================================================
; Low fixed RAM after Konami's moved data (7C58-7FFF).
    org 0x7C60
; ===========================================================================
; MSX BIOS entry points.  Each preserves every register except its outputs,
; like the simulator the relocation was verified against.

bios_000C:                      ; RDSLT: no other cartridge
    ld a,0xff
    ret
bios_0024:                      ; ENASLT
    ret
bios_0138:                      ; RSLREG
    xor a
    ret

bios_0047:                      ; WRTVDP: register C = B
    push af
    push hl
    ld a,c
    and 7
    ld hl,vdp_regs
    add a,l
    ld l,a
    jr nc,.nc
    inc h
.nc:
    ld (hl),b
    ld a,c
    and 7
    cp 7
    jr nz,.out
    ld a,b                      ; backdrop colour -> border
    and 15
    ld hl,border_of
    add a,l
    ld l,a
    jr nc,.nc2
    inc h
.nc2:
    ld a,(hl)
    out (0xfe),a
.out:
    pop hl
    pop af
    ret

bios_004D:                      ; WRTVRM: (HL) = A
    push hl
    ld (vdp_addr),hl
    pop hl
    jp vram_write

bios_0053:                      ; SETWRT: address HL
    ld (vdp_addr),hl
    ret

bios_0056:                      ; FILVRM: BC bytes of A from HL
    push af                     ; Only the name table and the sprite attributes
    push bc                     ; are kept (3800-3BFF): the native build has
    push de                     ; no pattern or colour tables, and Konami fills
    push hl                     ; those only in the loads it no longer makes
    ld (.v+1),a                 ; (and the boot's clearing of the whole VRAM)
    ifdef NEXT
    push af                     ; the Next: the boot's clearing (from 0000)
    ld a,h                      ; clears its store of character rows and its
    or l                        ; sprite patterns too
    call z,nx_clear
    pop af
    endif
    ex de,hl
    ld h,b
    ld l,c
    add hl,de                   ; HL = the end, DE = the start
    push hl
    ld bc,0x3c00
    or a
    sbc hl,bc
    pop hl
    jr c,.e
    ld h,b
    ld l,c                      ; end = min(end, 3C00)
.e:
    ld a,d
    cp 0x38
    jr nc,.s
    ld de,0x3800                ; start = max(start, 3800)
.s:
    or a
    sbc hl,de                   ; HL = the count
    jr c,.done
    jr z,.done
    ld (vdp_addr),de
    ld b,h
    ld c,l
.f:
.v:
    ld a,0
    call vram_write
    dec bc
    ld a,b
    or c
    jr nz,.f
.done:
    pop hl
    pop de
    pop bc
    push hl
    add hl,bc
    ld a,h
    and 0x3f
    ld h,a
    ld (vdp_addr),hl            ; as the BIOS leaves it
    pop hl
    pop af
    ret

    ifdef NEXT
nx_clear:                       ; A: pages C and D E800-FFFF, bank 7 F800-FFFF
    push hl
    push bc
    ld c,a
    ld a,PAGE_C
    ld hl,0xE800
    call .fill
    ld a,PAGE_D
    ld hl,0xE800
    call .fill
    ld a,PAGE_7
    ld hl,0xF800
    call .fill
    ld a,1
    ld (spr_new),a
    call unborrow_page
    pop bc
    pop hl
    ret
.fill:
    call out_page
.f:
    ld (hl),c
    inc l
    jr nz,.f
    inc h
    jr nz,.f
    ret
    endif

bios_0059:                      ; LDIRMV: reached only from code the native
    ret                         ; build leaves unused (the loaders, the dissolve)

bios_013E:                      ; RDVDP: status (frame flag set)
    ld a,0x80
    ret

bios_0093:                      ; WRTPSG: PSG register A = E, on the AY
    push af
    push bc
    push hl
    and 15
    ld c,a
    ifdef NEXT
    ld a,(nx_ay)                ; Next: AY 2 or 3 selected (nx_sfx): written
    or a                        ; every time (psg_regs is AY 1's)
    ld a,c
    jr nz,.write
    endif
    ld hl,psg_regs
    add a,l
    ld l,a
    ld a,e
    cp (hl)
    ld (hl),a
    ld a,c
    jr nz,.write                ; a value the AY already holds is not written
    cp 13                       ; again (plat_boot clears both), except the
    jr nz,.noei                 ; envelope shape, whose write restarts it
.write:
    cp 14                       ; 14/15, the MSX joystick port: nothing on
    jr nc,.noei                 ; the AY (the joystick comes from the keys)
    di                          ; the sound driver's interrupt must not select
    ld bc,0xfffd                ; another register in between (Konami's start-up
    out (c),a                   ; code calls this too).  The ei is safe inside
    ld b,0xbf                   ; the interrupt as well: the next one is a
    out (c),e                   ; frame away
    ei
.noei:
    pop hl
    pop bc
    pop af
    ret

bios_0096:                      ; RDPSG: register A (14 = joystick port)
    and 15
    cp 14
    jr z,read_joystick
    push hl
    ld hl,psg_regs
    add a,l
    ld l,a
    ld a,(hl)
    pop hl
    ret

; Joystick port A as the MSX sees it: bits 0-5 up, down, left, right,
; trigger A, trigger B, active low.  Worked out once per tick by kb_compute.
read_joystick:
    ld a,(kb_cache+9)
    ret

; The keyboard, read once per tick (plat_main), one byte per half-row, then
; turned into the nine MSX matrix rows and the joystick byte (kb_compute,
; unrolled code generated by tables.py from its key maps).
kb_rows:    ds 8
kb_cache:   ds 10               ; MSX rows 0-8, joystick

read_keyboard:
    ld hl,kb_rows
    ld bc,0xfefe
.r:
    in a,(c)
    ld (hl),a
    inc hl
    rlc b
    jr c,.r
    call kb_compute
    call kempston
    jp fire_hold

bios_0141:                      ; SNSMAT: keyboard row A, bit = 0 if pressed
    cp 9
    jr c,.ok
    ld a,0xff
    ret
.ok:
    push hl
    ld hl,kb_cache
    add a,l
    ld l,a
    jr nc,.nc
    inc h
.nc:
    ld a,(hl)
    pop hl
    ret

; ---- rarely run: kept in the low (contended) area ----------------------------
plat_boot:
    di
    ld sp,0xAEA0
    ld e,0                      ; AY registers 13-0 cleared, as psg_regs is,
    ld a,13                     ; for WRTPSG's skipping of unchanged values
.ay:
    ld bc,0xfffd
    out (c),a
    ld b,0xbf
    out (c),e
    dec a
    jp p,.ay
    ld a,0x10
    ld (port_bits),a
    ifdef NEXT
    ld a,PAGE_D                 ; Next: 28 MHz, the copper (page D)
    call set_page
    call nx_init
    endif
    ld a,PAGE_A
    call set_page
    xor a
    out (0xfe),a
    ; IM2: table AD00-AE00 of 0xAE, so every vector is AEAE.
    ld hl,0xAD00
    ld de,0xAD01
    ld bc,256
    ld (hl),0xAE
    ldir
    ld hl,0xC9FB                ; first ei / ret at AEAE: two bare frames to
    ld (0xAEAE),hl              ; look for a Kempston interface
    ld a,0xAD
    ld i,a
    im 2
    call kempston_detect
    ld a,0xc3
    ld (0xAEAE),a
    ld hl,isr
    ld (0xAEAF),hl
    ; Silence the AY.
    ld e,0
    ld a,8
    call bios_0093
    ld a,9
    call bios_0093
    ld a,10
    call bios_0093
    call render_init
    jp m0_4071                  ; Konami's INIT; it ends in plat_main

render_init:
    ld a,PAGE_7
    call set_page
    ld hl,0x4000
    ld de,0x4001
    ld bc,6911
    ld (hl),0
    ldir
    ld hl,0xC000
    ld de,0xC001
    ld bc,6911
    ld (hl),0
    ldir
    ld a,PAGE_A
    call set_page
    ld a,0xff
    ifndef NEXT
    ld (erase0),a
    ld (erase1),a
    else
    ld (0x3D00),a               ; Next: nx_low.asm's erase lists
    ld (0x3E00),a
    endif
    jp dirty_all



; Map writers found by the 24 Oct censuses (here for want of room above 8000).
nm_751d:                        ; MSX 1:751D: call 571B, then a 2x2 at HL is cleared
    call m0_571B
    push af
    push de
    ld de,0x0202
    call nm_rec
    pop de
    pop af
    ret
nm_87cf:                        ; MSX 2:87CF: ld hl,EE5B, then it and the cell below
    ld hl,0xEE5B+KRAM
    push af
    push de
    ld de,0x0102
    call nm_rec
    pop de
    pop af
    ret

; The title (0:52D9 patched to come here): Konami's panel, then the controls.
spec_title:
    call m0_5B77                ; escribe_el_panel_del_titulo
    ld a,(cur_page)
    push af
    ld a,PAGE_C
    call set_page
    ld de,ctl_text
    call m0_4998                ; escribe_caracteres
    call title_start            ; the title's tune, at once
    pop af
    call set_page
    xor a
    jp m0_53A1

; Kempston joystick (port 0x1F, bits 0-4 = right, left, down, up, fire, 1 =
; pressed) into the MSX joystick byte (PSG register 14: up, down, left,
; right, trigger A, trigger B; 0 = pressed), with the keys.  A second fire
; button, on bit 5 (some interfaces) or bit 7 (the Retroleum SmartCard,
; pin 9), is trigger B: power-up, the MSX's second button.  Without an
; interface the port reads the floating bus, so the interface is looked for
; once at boot, just after an interrupt (top border: an idle bus reads 0xFF,
; which would be all four directions at once); and bits 5 and 7 are used
; only if they read 0 then, so an interface that leaves them floating cannot
; select power-ups by itself.
kempston_detect:
    ld b,2
.f:
    ei
    halt
    di
    in a,(0x1f)
    ld c,a
    and 0x1f
    cp 0x1f
    ret z
    djnz .f
    xor a
    ld (kempston),a             ; ret -> nop: the interface is read
    ld a,c
    and 0xa0
    ret z
    xor a
    ld (kemp_b2+1),a            ; bits 5 and 7 not 0 at rest: not used
    ret
kempston:
    ret                         ; nop once an interface is found
    in a,(0x1f)
    ld b,a
    ld hl,kb_cache+9
    bit 3,b
    jr z,$+4
    res 0,(hl)
    bit 2,b
    jr z,$+4
    res 1,(hl)
    bit 1,b
    jr z,$+4
    res 2,(hl)
    bit 0,b
    jr z,$+4
    res 3,(hl)
    bit 4,b
    jr z,$+4
    res 4,(hl)
    ld a,b
kemp_b2:
    and 0xa0                    ; the second button (bit 5 or 7)
    ret z
    res 5,(hl)
    ret

; Fire held for HOLD_TICKS ticks running presses power-up (trigger B) as
; well, until fire is let go: Konami takes only the moment a button goes
; down, so that is one power-up per hold, for joysticks with one button.
; Konami's own repeat (a shot every 15 ticks held) is unchanged.
hold_n:     db 0
fire_hold:
    ld hl,kb_cache+9
    bit 4,(hl)
    ld a,0
    jr nz,.st                   ; fire up: count again from 0
    ld a,(hold_n)
    cp HOLD_TICKS
    jr c,.inc
    res 5,(hl)
    ret
.inc:
    inc a
.st:
    ld (hold_n),a
    ret


; Sprite attributes (VRAM 3B00-): the renderer draws from Konami's EC80, but
; Konami hides every sprite by writing 0xD0 to VRAM 3B00 alone
; (quita_los_sprites_de_la_pantalla, 0:55AA, on the way back to the title),
; leaving EC80 as it was.  So a write to 3B00 sets spr_on (0 for 0xD0), and
; each attribute upload (0:47CE, patched to call spr_upload) sets it again.
spr_on:     db 1
vw_attr:
    ld a,d
    cp 0x3b
    jp nz,vram_write.done
    ld a,e
    or a
    jp nz,vram_write.done
    ld a,(vw_val)
    sub 0xd0
    ld (spr_on),a
    jp vram_write.done
spr_upload:
    ld hl,spr_on
    ld (hl),1
    ld hl,0x3B00
    ret

low_end:
    assert low_end <= 0x8000

; ---------------------------------------------------------------------------
; Sprites crossing the left or right edge of the screen, from draw_sprites
; (render.asm), in the gap after Konami's relocated bank 0 code.  The part
; of the sprite on screen is shifted into edge_pat, a 16 x 16 pattern laid
; out as the chip's, which draw_sprite16 then draws on a cell boundary: at
; x 0 (columns 0-1) for the left edge, x 240 (columns 30-31) for the right.
; With 8 or more pixels off screen only one column shows, and only that
; column is coloured and recorded (on the right, the pixels still go
; through column 30, whose bytes are empty).
; A = X (241-255) or, with the early clock (bit 7 of C), X - 32 (-32 to -1);
; HL = the sprite's entry in the list, page 7 in.  Back to draw_sprites.next
; with BC and HL as they were.
    org 0x7B40
    assert section_fixed_end <= edge_pat
edge_pat:   ds 32               ; 32-byte aligned: draw_sprite16 steps it by L
se_k:       db 0                ; pixels off screen, 1-15
spr_edge:
    push hl
    push bc
    ld e,a
    ld a,c
    rla                         ; carry: the early clock, so the left edge
    ld a,e
    jr nc,.right
    cp 0xf1
    jp c,.done                  ; 16 or more pixels off: nothing shows
    neg
    ld e,0
    jr .k
.right:
    sub 240
    ld e,240
.k:
    ld (se_k),a
    ld a,e
    ld (sp_x),a
    rrca
    rrca
    rrca
    ld (sp_cx),a                ; 0 or 30
    inc l
    inc l
    ld a,(hl)                   ; pattern
    and 0xfc
    call spr_patsel
    jp c,.done                  ; the ship's second colour: not drawn
    ld de,edge_pat
.line:
    ld b,(hl)                   ; BC = the line's 16 pixels
    set 4,l
    ld c,(hl)
    res 4,l
    inc l
    ld a,(sp_x)
    or a
    ld a,(se_k)
    jr nz,.rs
    cp 8                        ; left: shifted left by k
    jr c,.ls
    ld b,c
    ld c,0
    sub 8
    jr z,.st
.ls:
    sla c
    rl b
    dec a
    jr nz,.ls
    jr .st
.rs:
    cp 8                        ; right: shifted right by k
    jr c,.rsh
    ld c,b
    ld b,0
    sub 8
    jr z,.st
.rsh:
    srl b
    rr c
    dec a
    jr nz,.rsh
.st:
    ex de,hl
    ld (hl),b
    set 4,l
    ld (hl),c
    res 4,l
    inc l
    ex de,hl
    ld a,e
    and 15
    jr nz,.line
    ld a,(se_k)
    cp 8
    ld b,2                      ; columns shown
    ld a,(sp_cx)
    ld c,a                      ; the column drawn from
    jr c,.draw
    dec b
    or a
    jr z,.draw
    inc a                       ; right: column 31 alone is coloured
    ld (sp_cx),a
.draw:
    ld hl,edge_pat
    xor a                       ; no shift
    call draw_sprite16.cols
.done:
    pop bc
    pop hl
    jp draw_sprites.next
spr_edge_end:
    assert spr_edge_end <= 0x7C00
    assert m7_83C8 == 0xC3C8          ; sound data at MSX address + 0x4000
    assert section_D_end <= 0xE000
    assert section_C_end <= COL_SHADOW ; E015-E7FF free since the title logo moved to page E
    assert data_bank9_end <= 0xE769    ; banks 12, 9 and 10 in page E (gen.py DATA_PLACE)
    ; page E: the bonus stages' parts of bank 12 (gen.py DATA_PIECES) in bank 10's
    ; skipped records-screen part and the room the colour fit left
    assert data_bank10_part0_end <= data_bank12_piece0 && data_bank12_piece1_end <= 0xF20F
    assert data_bank10_end <= data_bank12_piece2 && data_bank12_piece3_end <= 0xFB04
    assert section_E_end <= data_bank12_piece4
    assert data_bank5_end <= 0xF900    ; the colour fit follows in page B

; ===========================================================================
    org 0x8000
platform_start:

; ---- paging state -----------------------------------------------------------
cur_page:   db PAGE_A           ; page at C000
win6:       db 1                ; Konami's view of its mapper windows
win8:       db 2
winA:       db 3
saved_page: db PAGE_A
in_special: db 0
port_bits:  db 0x10             ; 7FFD bits other than the page: ROM 1, bit 3 = screen 1 shown
port_now:   db 0x10             ; the value last written to 7FFD (the interrupt puts it back)

; ---- MSX system variables Konami reads --------------------------------------
bios_var_0006: db 0x98          ; VDP read port
bios_var_0007: db 0x98          ; VDP write port
bios_var_002B: db 0x81          ; international character set (NEMESIS logo), 50Hz
hook_FD9A:  db 0
hook_FD9B:  dw 0
hook_FCC1:  db 0,0,0,0,0,0,0,0  ; EXPTBL: no expanded slots


; ---- VDP state --------------------------------------------------------------
vdp_addr:   dw 0
vdp_regs:   ds 8
vw_val:     db 0
psg_regs:   ds 16

; Page the Spectrum bank A at C000 as Konami's page (cur_page).
set_page:                       ; A = page; preserves BC, DE, HL (not AF)
    ld (cur_page),a
; Every write to 7FFD goes through here (and the interrupt): the value is
; noted in port_now before it is written, so an interrupt, which pages in the
; sound driver, puts back exactly what was there, and code that borrows a
; page for a moment needs no di.  isr_flip does not flip while inside
; out_page..out_page_end, where port_bits has been read but not yet written.
out_page:                       ; A = page; preserves BC, DE, HL (not AF)
    push bc
    ld b,a
    ld a,(port_bits)
    or b
    ld (port_now),a
    ifndef NEXT
    ld bc,0x7ffd
    out (c),a
    else
    ld a,b                      ; Next: MMU6/MMU7 (NEXTREG 56h, 57h), not port
    add a,a                     ; 7FFD, whose writes put the ROM back at 0000
    db 0xED,0x92,0x56           ; nextreg 0x56,a
    inc a
    db 0xED,0x92,0x57           ; nextreg 0x57,a
    endif
out_page_end:
    pop bc
    ret

; Konami mapper writes (ld (6000/8000/A000),a).  Data banks get their page;
; when Konami returns to its normal 1,2,3 set, the page in use before is back.
; Every write to 6000 or 8000 in Konami's code is followed, in straight-line
; code with no read through a window, by a write to A000 (all 78 mapper
; writes checked, 0.108), so only that last write works out the page.
map_6000:
    ld (win6),a
    ret
map_8000:
    ld (win8),a
    ret
map_a000:
    ld (winA),a
map_update:
    push af
    push hl
    ld a,(win8)
    ld h,PAGE_D
    cp 7
    jr z,.special
    ld h,PAGE_E
    cp 11
    jr z,.special
    ld h,PAGE_B
    cp 5
    jr z,.special
    ld h,PAGE_E                 ; the title's part of bank 9, with bank 10
    cp 9
    jr z,.special
    ld h,PAGE_B
    ld a,(win6)
    cp 4
    jr z,.special
    ld h,PAGE_E                 ; bank 10 at A000, switched from fixed code (the
    ld a,(winA)                 ; end-of-loop explosion); from paged code (the
    cp 10                       ; stage 5 boss in page A, the boss pieces in page
    jr nz,.not10                ; E) the page stays as it is
    push hl
    ld hl,6                     ; the mapper write's caller, past HL, AF and HL
    add hl,sp
    inc hl
    ld a,(hl)
    pop hl
    cp 0xc0
    jr c,.special
.not10:
    ld a,(in_special)
    or a
    jr z,.done
    xor a
    ld (in_special),a
    ld a,(saved_page)
    jr .set_a
.special:
    ld a,(in_special)
    or a
    jr nz,.set
    ld a,(cur_page)
    ld (saved_page),a
    ld a,1
    ld (in_special),a
.set:
    ld a,h
.set_a:
    ld hl,cur_page              ; already there (the second write of a pair): no switch
    cp (hl)
    call nz,set_page
.done:
    pop hl
    pop af
    ret

; DCOMPR (RST 20h): compare HL with DE.
dcompr:
    ld a,h
    sub d
    ret nz
    ld a,l
    sub e
    ret

; Test builds (NEM_PIN_R=1): ld a,r replaced by this fixed sequence, the same
; as the simulators' (state = state * 73 + 41, A = state & 0x7F).  Carry kept.
r_state: db 0x5A
pinned_r:
    push bc
    push af
    ld a,(r_state)
    ld b,a
    add a,a
    add a,a
    add a,a
    ld c,a
    add a,a
    add a,a
    add a,a
    add a,c
    add a,b
    add a,41
    ld (r_state),a
    and 0x7f
    ld b,a
    pop af
    ld a,b
    inc a
    dec a
    pop bc
    ret

; Sound stream 0xFE (repeat): the high byte of the new stream address, moved
; from MSX 8000-BFFF to the copy at C000-FFFF.
snd_fe_hi:
    ld a,(hl)
    or 0x40
    ld (ix+4),a
    ret

; ===========================================================================
; VDP data port and VRAM.  Konami's VRAM is not kept as such: each region goes
; where the Spectrum needs it.
;   0000-37FF patterns, colours, sprite patterns: not kept (the native
;               build's graphics come converted, with its loads: nl_load)
;   3800-3AFF names     -> name_shadow (the renderer's source)
;   3B00-     sprite attributes: ignored (the renderer reads Konami's EC80)

; out (c),a to the VDP data port.  Preserves everything.
vdp_out_a:
vram_write:
    ld (vw_val),a
    push af
    push de
    push hl
    ld hl,(vdp_addr)
    ex de,hl
    ld hl,1
    add hl,de
    ld a,h
    and 0x3f
    ld h,a
    ld (vdp_addr),hl
    ld a,d
    cp 0x18
    jr c,.colour
    cp 0x20
    jr c,.sprite
    cp 0x38
    jr c,.pattern
    cp 0x3b
    jp nc,vw_attr
    ld hl,name_shadow-0x3800
    add hl,de
    ld a,(vw_val)
    cp (hl)
    jr z,.done
    ld (hl),a
    push bc
    ld a,d                      ; a cell of the map area: the next upload
    cp 0x3a                     ; must compare the buffer again (on the MSX
    jr c,.map                   ; it would overwrite this write)
    ld a,e
    cp 0xc0
    jr nc,.hud
.map:
    ld a,1
    ld (nm_full),a
.hud:
    ld a,h
    sub name_shadow>>8
    ld b,a
    ld c,l
    ld a,(vw_val)
    call star_cell
    call dirty_cell
    pop bc
.done:
    pop hl
    pop de
    pop af
    ret
.sprite:                        ; the pattern, colour and sprite pattern tables:
.colour:                        ; not kept (the native build's tiles and
.pattern:                       ; sprite patterns come with its loads, nl_load)
    jr .done

; Back to Konami's page after a borrow.  Preserves BC, DE, HL.
unborrow_page:
    ld a,(cur_page)
    jp out_page


; Compare the regions queued in nm_list and nm2_list with name_shadow and
; take their changes; empties both lists.  Preserves DE.
nm_flush:
    ld hl,(nm_ptr)
    ld a,l
    cp nm_list&0xff
    jr z,.listed
    push de
.next:
    dec l
    ld c,(hl)                   ; rows
    dec l
    ld b,(hl)                   ; width
    dec l
    ld d,(hl)
    dec l
    ld e,(hl)
    push hl
    ex de,hl
.row:
    ld a,h                      ; rows past the map (EFC0 on) are not shown
    cp (0xED00+KRAM+0x200)>>8
    jr c,.cells
    jr nz,.rdone
    ld a,0xc0
    sub l
    jr c,.rdone
    jr z,.rdone
    cp b                        ; the last row: no further than its end
    jr nc,.cells
    ld b,a
.cells:
    push bc
    push hl
    ld a,h
    add a,(name_shadow>>8)-((0xED00+KRAM)>>8)
    ld d,a
    ld e,l
.cell:
    ld a,(de)
    cp (hl)
    call nz,upl_chg
    inc hl
    inc de
    djnz .cell
    pop hl
    pop bc
    ld a,l
    add a,32
    ld l,a
    jr nc,.nc
    inc h
.nc:
    dec c
    jr nz,.row
.rdone:
    pop hl
    ld a,l
    cp nm_list&0xff
    jr nz,.next
    ld (nm_ptr),hl
    pop de
.listed:
    ld hl,(nm2_ptr)             ; and the 2x2 objects
    ld a,l
    or a
    jr z,.done2
    push de
.n2:
    dec l
    ld d,(hl)
    dec l
    ld e,(hl)
    push hl
    ex de,hl
    ld a,h
    sub (0xED00+KRAM)>>8
    cp 2
    jr c,.n2ok
    jr nz,.n2skip
    ld a,l
    cp 0xc0
    jr nc,.n2skip               ; below the map (row 22 on): not shown from here
    cp 0xa0
    jr nc,.n2last               ; starts in the last row: just that row
.n2ok:
    ld a,h
    add a,(name_shadow>>8)-((0xED00+KRAM)>>8)
    ld d,a
    ld e,l
    ld a,(de)
    cp (hl)
    call nz,upl_chg
    inc hl
    inc de
    ld a,(de)
    cp (hl)
    call nz,upl_chg
    ld bc,31
    add hl,bc
    ex de,hl
    add hl,bc
    ex de,hl
    ld a,(de)
    cp (hl)
    call nz,upl_chg
    inc hl
    inc de
    ld a,(de)
    cp (hl)
    call nz,upl_chg
.n2skip:
    pop hl
    ld a,l
    or a
    jr nz,.n2
    ld (nm2_ptr),hl
    pop de
.done2:
    ret
.n2last:
    ld a,h
    add a,(name_shadow>>8)-((0xED00+KRAM)>>8)
    ld d,a
    ld e,l
    ld a,(de)
    cp (hl)
    call nz,upl_chg
    ld a,l
    cp 0xbf
    jr z,.n2skip
    inc hl
    inc de
    ld a,(de)
    cp (hl)
    call nz,upl_chg
    jr .n2skip


; ===========================================================================
; sube_la_pantalla (MSX 47FE) replaced: the 704 bytes of Konami's map at ED00
; go to the name-table shadow, and every cell that changed (or whose tile
; changed this tick) is marked for redrawing on both screens.  Leaves
; registers as the original does: alternate set selected, HL = ED00+704,
; B = 0, C = VDP port, Z set; the main set's HL = 3800.
plat_upload_map:
    ld hl,0x3800+704
    ld (vdp_addr),hl
    ld hl,0x3800
    exx
    ld a,(nm_full)
    or a
    jp nz,.full
    ld a,(nm_count)
    dec a
    ld (nm_count),a
    jp z,.full
    call nm_flush               ; compare just the regions Konami wrote
    ld hl,0xED00+KRAM+704
    ld bc,0x0098
    inc b
    dec b
    ret
.full:
    xor a
    ld (nm_full),a
    ld hl,nm_list
    ld (nm_ptr),hl
    ld hl,nm2_list
    ld (nm2_ptr),hl
    ld a,64
    ld (nm_count),a
    push de
    push ix
    ld hl,0xED00+KRAM
    ld de,name_shadow
    call full_cmp_d
    pop ix
    pop de
    ld hl,0xED00+KRAM+704
    ld bc,0x0098
    inc b                       ; set Z the way the last outi left it
    dec b
    ret

nm_ptr:     dw nm_list          ; next free entry in nm_list
nm2_ptr:    dw nm2_list         ; next free entry in nm2_list
nm_full:    db 1                ; a big copy wrote the map buffer: compare it all
nm_count:   db 64               ; ticks to the next full comparison regardless

;  Konami's writes into its map buffer (NM_SITES in gen.py): note the region
; about to be written, then the original instruction.  Registers and flags
; are as the original instruction leaves them.
    macro NM_AT_HL size
        push af
        push de
        ld de,size
        call nm_rec
        pop de
        pop af
    endm
    macro NM_AT_DE size
        push af
        push de
        push hl
        ex de,hl
        ld de,size
        call nm_rec
        pop hl
        pop de
        pop af
    endm
    macro NM22_AT_HL            ; note a 2x2 region at HL in nm2_list
        push af
        push de
        ex de,hl
        ld hl,(nm2_ptr)
        ld (hl),e
        inc l
        ld (hl),d
        inc l
        ld a,l
        cp (nm2_list+NM2_LEN)&0xff
        jr nz,.ok
        ld a,1                  ; full: compare everything instead
        ld (nm_full),a
        ld hl,nm2_list
.ok:
        ld (nm2_ptr),hl
        ex de,hl
        pop de
        pop af
    endm
    macro NM22_AT_DE
        push hl
        ex de,hl
        NM22_AT_HL
        ex de,hl
        pop hl
    endm
nm_r22_de_ldi:
    NM22_AT_DE
    ldi
    ret
nm_r11_de_a:
    NM_AT_DE 0x0101
    ld (de),a
    ret
nm_r21_hl_c:
    NM_AT_HL 0x0201
    ld (hl),c
    ret
nm_r11_hl_a:                    ; the new column and its stars: on a scroll the
    ld (hl),a                   ; shift has already asked for a full comparison,
    push af                     ; so the cell need not be noted (0.109)
    ld a,(nm_full)
    or a
    jr nz,.full
    push de
    ld de,0x0101
    call nm_rec
    pop de
.full:
    pop af
    ret
nm_69e1:
    ld h,(ix+0x1f)
    NM22_AT_HL
    ret
nm_6a5b:
    call m0_571B
    NM_AT_HL 0x0404
    ret
nm_902e:
    NM22_AT_DE
    ld hl,m2_905C
    ret
nm_9051:
    NM_AT_DE 0x0101
    ld hl,m2_8FE4
    ret
nm_9fe0:
    NM_AT_DE 0x0101
    jp m0_49DE
; The laser's strip (MSX 3:A2AA, A2F4), missed by the census, which had no
; laser: B (or C) cells in a row at DE.
nm_laser_w:
    ld d,(ix+0x0f)
    push af
    push bc
    push hl
    push de
    ex de,hl
    ld d,b
    ld e,1
    call nm_rec
    pop de
    pop hl
    pop bc
    pop af
    ret
nm_laser_e:
    ld c,(ix+0x0c)
    push af
    push bc
    push hl
    push de
    ex de,hl
    ld d,c
    ld e,1
    call nm_rec
    pop de
    pop hl
    pop bc
    pop af
    ret
nm_rect_ld_e_b:                 ; B wide, C rows at HL
    push af
    push de
    ld d,b
    ld e,c
    call nm_rec
    pop de
    pop af
    ld e,b
    ret
nm_rect_sub_b:
    push af
    push de
    ld d,b
    ld e,c
    call nm_rec
    pop de
    pop af
    sub b
    ret
nm_ldir_full:
    ldir
nm_set_full:
    push af
    ld a,1
    ld (nm_full),a
    pop af
    ret
nm_ldi31_full:                  ; the scroll's 31-byte row moves: LDIR unrolled
    rept 31
    ldi
    endr
    jr nm_set_full

; The full comparison (fullcmp_gen.asm, from gen_fullcmp.py) runs in page D.
full_cmp_d:
    ld a,(cur_page)
    push af
    ld a,PAGE_7
    call set_page
    push hl
    push de
    call star_check
    pop de
    pop hl
    ld a,PAGE_D
    call set_page
    call full_cmp
    pop af
    jp set_page

; Note region HL (D wide, E rows) in nm_list, if it starts in or near the map
; buffer; a full list asks for a full comparison.  Preserves BC, HL.
nm_rec:
    ld a,h
    sub (0xED00+KRAM)>>8
    cp 3
    ret nc
    ld a,d
    or a
    ret z
    ld a,e
    or a
    ret z
    push hl
    push de
    ex de,hl
    ld hl,(nm_ptr)
    ld a,l
    cp 0xfc
    jr z,.over
    ld (hl),e
    inc l
    ld (hl),d
    inc l
    pop de
    ld (hl),d
    inc l
    ld (hl),e
    inc l
    ld (nm_ptr),hl
    pop hl
    ret
.over:
    pop de
    pop hl
    ld a,1
    ld (nm_full),a
    ret

; Group IXL of the full comparison changed (cells C, stars among them B):
; mark both screens, update star_cells.  Preserves BC, DE, HL.
; A cell of Konami's map changed: copy it, mark it on both screens, and keep
; star_cells (cells showing star tile F6 or F7) up to date.
upl_chg:
    ld a,(hl)
    ld (de),a
    push bc
    push hl
    ld c,a                      ; new tile
    ld a,e
    and 7
    ld l,a
    ld h,bitmask>>8
    ld b,(hl)                   ; this cell's bit
    ld a,d
    sub name_shadow>>8
    rrca
    rrca
    rrca
    ld l,a                      ; third * 32
    ld a,e
    rrca
    rrca
    rrca
    and 31
    or l
    ld l,a
    ld h,dirty0>>8
    ld a,(hl)
    or b
    ld (hl),a
    set 7,l
    ld a,(hl)
    or b
    ld (hl),a
    res 7,l
    ld a,l
    add a,star_cells&0xff
    ld l,a
    ld h,star_cells>>8
    ld a,c
    sub 0xf6
    cp 2
    ld a,(hl)
    jr c,.star
    ld c,a
    and b
    jr z,.nostar                ; was not a star either
    ld a,b
    cpl
    and c
    ld (hl),a
    call star_remove            ; a star cell went: out of its list
.nostar:
    pop hl
    pop bc
    ret
.star:
    push af
    or b
    ld (hl),a
    pop af
    and b
    call nz,star_remove         ; F6 <-> F7: out of the other list first
    ; into list third * 2 + (tile - F6)
    ld a,d
    sub name_shadow>>8
    add a,a
    ld b,a
    ld a,c
    sub 0xf6
    add a,b
    ld hl,star_n
    add a,l
    ld l,a
    ld a,(hl)
    cp STAR_CAP
    jr nc,.full
    inc (hl)
    ld b,a
    ld a,l
    add a,star_base-star_n
    ld l,a
    ld a,(hl)
    add a,b
    ld l,a
    ld (hl),e
    ; and into both screens' drawn lists, so that draw_stars erases it when
    ; the stars move (a full list: copy the star lists there instead)
    ld a,d
    sub name_shadow>>8
    ld b,a
    add a,drawn_n&0xff
    ld l,a
    ld h,drawn_n>>8
    ld c,0x01
    call .drawn
    ld a,l
    add a,4
    ld l,a
    ld c,0x02
    call .drawn
    pop hl
    pop bc
    ret
.drawn:                         ; HL = drawn_n[screen][third B]; C = the screen's bit
    ld a,(hl)
    cp 80
    jr nc,.dfull
    inc (hl)
    push hl
    ld h,a                      ; count
    ld a,l
    sub drawn_n&0xff
    and 4                       ; screen * 4
    rrca
    rrca                        ; screen
    add a,DRAWN>>8
    push af
    ld a,b
    add a,a
    add a,a
    add a,a
    add a,a                     ; third * 16
    ld l,a
    add a,a
    add a,a                     ; third * 64
    add a,l                     ; third * 80
    add a,h
    ld l,a
    pop af
    ld h,a
    ld (hl),e
    pop hl
    ret
.dfull:
    ld a,(stars_listed)
    or c
    ld (stars_listed),a
    ret
.full:
    ld a,1
    ld (star_dirty),a
    ld a,3
    ld (stars_listed),a
    pop hl
    pop bc
    ret

; Take cell E (third: D - name_shadow page) out of its third's two star
; lists.  Preserves C, DE.
star_remove:
    ld a,d
    sub name_shadow>>8
    add a,a
    push af
    call .one
    pop af
    inc a
.one:
    ld hl,star_n
    add a,l
    ld l,a
    ld b,(hl)
    ld a,b
    or a
    ret z
    push hl
    ld a,l
    add a,star_base-star_n
    ld l,a
    ld l,(hl)                   ; list start
.s:
    ld a,(hl)
    cp e
    jr z,.found
    inc l
    djnz .s
    pop hl
    ret
.found:
    push hl                     ; the last entry takes its place
    ld a,l
    add a,b
    dec a
    ld l,a
    ld a,(hl)
    pop hl
    ld (hl),a
    pop hl
    dec (hl)
    ret

; Cell (third B, low C) now shows tile A: set or clear its star_cells bit.
; Preserves BC, DE, HL.
star_cell:
    push hl
    push de
    sub 0xf6
    cp 2                        ; carry: a star tile
    push af
    ld a,c
    and 7
    ld l,a
    ld h,bitmask>>8
    ld e,(hl)
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
    add a,star_cells&0xff
    ld l,a
    ld a,1
    ld (star_dirty),a
    ld a,3
    ld (stars_listed),a
    pop af
    ld a,e
    jr c,.set
    cpl
    and (hl)
    ld (hl),a
    pop de
    pop hl
    ret
.set:
    or (hl)
    ld (hl),a
    pop de
    pop hl
    ret

; ===========================================================================
; Interrupt: Konami's sound driver, as MSX interrupcion did before the game
; tick (MSX 402C-4042), then the frame counter.
frames: db 0

isr:
    push af
    push bc
    ifdef NEXT
    ld a,(nx_tog)               ; Next: frame and line interrupts alternate
    xor 1                       ; (nx_frame keeps this in step)
    ld (nx_tog),a
    jr z,.line
    endif
    push de
    push hl
    ex af,af'
    push af
    exx
    push bc
    push de
    push hl
    push ix
    push iy
    ifndef NEXT
    ifndef TEST
    call run_sound
    endif
    endif
    ld hl,frames
    inc (hl)
    call isr_flip
    ifdef NEXT
    ifndef TEST
    call 0x010C                 ; Next: lo_snd, run_sound with the ordinary map
    endif
    endif
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    exx
    pop af
    ex af,af'
    pop hl
    pop de
    ifdef NEXT
.x:
    ld a,(nx_sel)               ; Next: the register the main program selected
    ld bc,0x243B                ; (nx_sel, noted before it selects), selected
    out (c),a                   ; again: its read of 253Bh then reads that one
    endif
    pop bc
    pop af
    ei
    reti
    ifdef NEXT
.line:                          ; Next: line 176, the status lines: ULA X
    db 0xED,0x92,0x16           ; Layer 2 X scroll 0 (nextreg 0x16,a; A is 0)
    jr .x
    endif

; Konami's sound driver (MSX bank 7), once: page D in, then the page that
; was in before (from port_now; the screen bit as it is now).  Through
; out_page, so that port_now is right throughout: test builds call this from
; the main loop, where an interrupt can come in the middle.
run_sound:
    ld a,(port_now)
    push af
    ld a,PAGE_D
    call out_page
    ifdef NEXT
    ld a,(snd_busy)             ; Next: Konami's sound request under way (0:4A02-
    or a                        ; 0:4A11, run without di): the driver, which reads
    jr nz,.nodrv                ; its queue, waits a frame
    call nx_hz                  ; at 60 Hz, one frame in six left out: Konami's
    jr nz,.nodrv                ; driver runs 50 times a second either way
    call m7_8063                ; the music (and the pause chime) on AY 1
    call nx_sfx                 ; the effects on AY 2
.nodrv:
    call nx_frame               ; Next: the shown screen's scroll, the clip window
    else
    call m7_8063
    endif
    pop af
    and 7
    jp out_page

; ===========================================================================
; Boot (entered from the loader or snapshot with interrupts off).
; Konami's INIT ends here (MSX 40DF, where it waited in jr $ for interrupts).
plat_main:
    ei
.loop:
    call read_keyboard
    ifdef TEST
    di                          ; test builds: sound once per tick, as an MSX
    call run_sound              ; whose ticks all fit in one frame
    ei
    endif
pm_tick:
    call m0_4045                ; one game tick (MSX interrupcion after the sound part)
pm_tiles:
    call tick_tiles
    ifdef ADAPT
    call far_pace               ; (0.110) behind the rhythm: no drawing this tick
    jr c,plat_main.loop
    endif
    if LOGIC_EXTRA
    ld hl,logic_ctr             ; after every LOGIC_EXTRA drawn ticks, one more
    dec (hl)                    ; tick without drawing: the game runs nearer the
    jr nz,pm_wait               ; MSX's speed, the screen catches up next time
    ld (hl),LOGIC_EXTRA+1
    jr plat_main.loop
    endif
    ifdef DRAW_EVERY
    ld hl,logic_ctr             ; only one tick in DRAW_EVERY is drawn; the
    dec (hl)                    ; flips are DRAW_EVERY * FRAMES_PER_TICK frames
    jr nz,plat_main.loop        ; apart at most, so quiet play keeps the MSX's rate
    ld (hl),DRAW_EVERY
    endif
pm_wait:
    call wait_shown
pm_render:
    ifndef NEXT
    call render_frame
    else
    call 0x010F                 ; Next: lo_render (Layer 2, sprites)
    endif
pm_flip:
    call request_flip
    jr plat_main.loop

    ifdef ADAPT
far_pace:                       ; far_go returns to this stub's caller
    call far_go
    db PAGE_C
    ifndef NEXT
    dw pace_adapt
    else
    dw nx_tick
    endif
    endif
; Pacing.  The screen just drawn is shown by the interrupt on the frame it
; is due, FRAMES_PER_TICK frames after the previous flip, while the next
; tick's game logic already runs; only drawing waits for the flip.  A late
; screen is shown at the next frame (no catching up: flips stay at least
; FRAMES_PER_TICK frames apart).
    if LOGIC_EXTRA
logic_ctr:  db LOGIC_EXTRA+1
    endif
    ifdef DRAW_EVERY
logic_ctr:  db DRAW_EVERY
    endif
flip_pending: db 0
    ifdef NEXT
nx_off:     db 0                ; Next: scroll offset (pixels right, 0-7), set per tick
nx_pend:    db 0                ; Next: offset of the screen waiting to be shown
nx_tog:     db 0                ; Next: 1 after a frame interrupt, 0 after a line one
snd_busy:   db 0                ; Next: pide_sonido is putting a request in its queue
nx_sel:     db 0x52             ; Next: the register the main program last selected
nx_ay:      db 0                ; Next: 0 with AY 1 selected, else AY 2 or 3
nx_hz60:    db 0                ; Next: 4 when the machine is at 60 Hz (NextReg 0x05 bit 2)
nx_hzc:     db 6                ; Next, 60 Hz: frames to the next one without the sound driver
; Next (1.1.3): the character enemies' 4-bit patterns kept between pictures.
; lo_pconv makes slot (lo_ci) - 1 from four (or two) blocks of the stage's
; character pool; the pattern depends only on those blocks, so a slot whose
; blocks are the ones it was last made from is left as it is.  Per slot: the
; blocks to make (lo_pq; 0: none noted), the four blocks (page, number), the
; palette the conversion found (lo_ppal).  Cleared at each graphics load
; (nl_done, before lo_apply copies the pool).
NX_PQ       equ 0x3FF2          ; nx_l2.asm's lo_pq, lo_pblk, lo_ppal (asserted there)
NX_PBLK     equ 0x3FE4
NX_PPAL     equ 0x3FEF
NX_CSLOTS   equ 22              ; OBJ_MAX
nx_ckey:    ds NX_CSLOTS*10
NX_STORE    equ 24              ; 8K page (bank 12's first half, otherwise unused):
NX_SN       equ 32              ; 32 patterns made (6000-6FFF at MMU3), their keys at 7000
nx_snext:   db 0                ; the store's entry to fill next
nx_snew:    db 1                ; empty the store before its next use (a graphics load)
lo_ci:      db 0                ; Next: lo_sprites' character enemy record (nx_l2.asm)
spr_new:    db 1                ; Next: Konami's sprite patterns (bank 7 F800) written since
                                ; lo_sprites last compared them all (nl_done, nx_clear)
; HL = slot (lo_ci) - 1's entry in nx_ckey.  Uses DE.
nx_cslot:
    ld a,(lo_ci)
    dec a
    ld l,a
    add a,a
    add a,a
    add a,l
    add a,a                     ; * 10
    ld l,a
    ld h,0
    ld de,nx_ckey
    add hl,de
    ret
; After lo_pconv has found the blocks: Z if the slot was made from the same
; ones (lo_ppal as it was then), or if the store holds their pattern (copied
; into the slot); NZ otherwise, the blocks noted for nx_cput.  Only four
; blocks: with two (row 21) lo_pconv has already cleared the slot's bottom
; half, so it is made every time.
nx_cchk:
    call nx_cslot
    ld a,(NX_PQ)
    cp 4
    jr nz,.two
    push hl
    cp (hl)
    jr nz,.new
    inc hl
    ld de,NX_PBLK
    ld b,8
.c:
    ld a,(de)
    cp (hl)
    jr nz,.new
    inc de
    inc hl
    djnz .c
    pop de
    ld a,(hl)
    ld (NX_PPAL),a
    xor a
    ret
.new:
    pop de
    ld a,4
    ld (de),a
    inc de
    ld hl,NX_PBLK
    ld bc,8
    ldir                        ; the slot's blocks noted
    ex de,hl                    ; HL = its palette byte
    push hl
    db 0xED,0x91,0x53,NX_STORE  ; the store at 6000
    call nx_sfind
    jr nz,.out
    ld a,(de)                   ; found: its palette
    ld (NX_PPAL),a
    pop hl
    ld (hl),a
    push hl
    call nx_sslot               ; and its pattern into the slot
    ex de,hl
    ld h,b
    ld l,c
    ld bc,128
    ldir
    xor a                       ; Z
.out:
    pop hl
    db 0xED,0x91,0x53,0x0B      ; MMU3 back (as lo_cells leaves it)
    ret
.two:
    ld (hl),0                   ; none noted
    or 1
    ret
nx_cput:                        ; after the conversion: its palette, and the
    call nx_cslot               ; pattern into the store (in turn)
    ld de,9
    add hl,de
    ld a,(NX_PPAL)
    ld (hl),a
    ld a,(NX_PQ)
    cp 4
    ret nz
    db 0xED,0x91,0x53,NX_STORE
    call nx_sclr
    ld a,(nx_snext)
    ld c,a
    inc a
    and NX_SN-1
    ld (nx_snext),a
    ld l,c                      ; DE = its key: 7000 + C * 10
    ld h,0
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,hl
    add hl,de
    ld de,0x7000
    add hl,de
    ex de,hl
    ld a,1                      ; valid, the blocks, the palette
    ld (de),a
    inc de
    ld hl,NX_PBLK
    push bc
    ld bc,8
    ldir
    pop bc
    ld a,(NX_PPAL)
    ld (de),a
    ld h,c                      ; its pattern: 6000 + C * 128
    ld l,0
    srl h
    rr l
    ld a,h
    add a,0x60
    ld d,a
    ld e,l
    call nx_sslot
    ld bc,128
    ldir
    db 0xED,0x91,0x53,0x0B
    ret
; HL = the slot's pattern (LO_CPAT + slot * 128).  Uses A.
nx_sslot:
    ld a,(lo_ci)
    dec a
    ld h,a
    ld l,0
    srl h
    rr l
    ld a,h
    add a,0x28                  ; LO_CPAT (asserted in nx_low.asm)
    ld h,a
    ret
; The store (MMU3 = NX_STORE): emptied first after a graphics load; then the
; entry whose key is NX_PBLK: Z, DE = its palette byte, BC = its pattern
; (6000 + entry * 128); NZ if none.
nx_sclr:
    ld a,(nx_snew)
    or a
    ret z
    xor a
    ld (nx_snew),a
    ld hl,0x7000
    ld b,NX_SN
.z:
    ld (hl),a
    ld de,10
    add hl,de
    djnz .z
    ret
nx_sfind:
    call nx_sclr
    ld hl,0x7000
    ld bc,0x6000
.e:
    ld a,(hl)
    or a
    jr z,.next
    push hl
    push bc
    inc hl
    ld de,NX_PBLK
    ld b,8
.k:
    ld a,(de)
    cp (hl)
    jr nz,.ne
    inc de
    inc hl
    djnz .k
    ex de,hl                    ; DE = the palette byte
    pop bc
    pop hl
    xor a
    ret
.ne:
    pop bc
    pop hl
.next:
    ld de,10
    add hl,de
    ld a,c
    add a,128
    ld c,a
    jr nc,.n2
    inc b
.n2:
    ld a,b
    cp 0x70
    jr c,.e
    or 1                        ; NZ (A = 70h)
    ret
nx_cinv:                        ; the slot made from the copies: no blocks.
    push hl                     ; Preserves BC, DE, HL.
    push de
    call nx_cslot
    ld (hl),0
    pop de
    pop hl
    ret
nx_cclr:                        ; a graphics load: none.  Preserves DE.
    ld a,1
    ld (nx_snew),a
    push bc
    ld hl,nx_ckey
    ld b,NX_CSLOTS
.z:
    ld (hl),0
    ld a,l
    add a,10
    ld l,a
    jr nc,.n
    inc h
.n:
    djnz .z
    pop bc
    ret
    ifdef ADAPT
pace_t:     db PACE_T           ; Next: pace_adapt's rhythm, eighths of a frame a tick (by 50/60 Hz)
    endif
snd_rec4:   ds 3*0x11           ; Next: the effects' three channels, records as
snd_mix2:   db 0x3F             ; Konami's three at 0xE010 (sounds below 16h:
                                ; encola_sonido, gen.py NEXT_PATCH, nx_pick), and
                                ; AY 2's mixer (0xE043's)
nx_pick:                        ; Next: A = an effect's number; HL = the record it
    push bc                     ; goes to (+2, as encola_sonido's 0:4A3F wants): one
    ld b,a                      ; already playing it, else a free one, else the
    ld de,0x11                  ; lowest-numbered (encola_sonido then compares, as
    ld hl,snd_rec4+2            ; Konami's channel C did)
    ld c,3
.same:
    ld a,(hl)
    and 0x7F
    cp b
    jr z,.got
    add hl,de
    dec c
    jr nz,.same
    ld hl,snd_rec4+2
    ld c,3
.free:
    ld a,(hl)
    or a
    jr z,.got
    add hl,de
    dec c
    jr nz,.free
    ld hl,snd_rec4+2
    ld a,(snd_rec4+2+0x11)
    and 0x7F
    ld c,a
    ld a,(hl)
    and 0x7F
    cp c
    jr c,.k1
    ld hl,snd_rec4+2+0x11
    ld a,c
.k1:
    ld c,a
    ld a,(snd_rec4+2+0x22)
    and 0x7F
    cp c
    jr nc,.got
    ld hl,snd_rec4+2+0x22
.got:
    pop bc
    ret
nx_aysel:                       ; Next: AY chip A (FFh: 1, FEh: 2, FDh: 3) selected
    push bc
    ld bc,0xfffd
    out (c),a
    pop bc
    cpl
    ld (nx_ay),a
    ret
nx_sfx:                         ; Next, from the interrupt: the effects' three
    ld a,0xFE                   ; channels, played on AY 2's A, B and C by Konami's
    call nx_aysel               ; channel interpreter, with AY 2's mixer in 0xE043;
    ld a,(0xE043-0x3100)        ; paused (0xE047), their volumes to 0, as Konami's
    push af                     ; chime does with AY 1
    ld a,(snd_mix2)
    ld (0xE043-0x3100),a
    ld a,(0xE047-0x3100)
    or a
    jr z,.play
    ld e,0
    ld a,8
.mute:
    call bios_0093
    inc a
    cp 11
    jr nz,.mute
    jr .done
.play:
    ld ix,snd_rec4
    ld c,1
.ch:
    ld a,(ix+2)
    or a
    jr z,.off
    call m7_8181                ; anda_un_canal
    jr .next
.off:
    call m7_8206                ; calla_este_canal
.next:
    ld de,0x11
    add ix,de
    inc c
    inc c
    ld a,c
    cp 7
    jr nz,.ch
.done:
    ld a,(0xE043-0x3100)
    ld (snd_mix2),a
    pop af
    ld (0xE043-0x3100),a
    ld a,0xFF
    jp nx_aysel
snd_hold:                       ; (gen.py NEXT_PATCH, in place of its di and ei:
    push af                     ; one of the two interrupts lost there left the
    ld a,1                      ; play area unscrolled for a frame)
    ld (snd_busy),a
    pop af
    ret
snd_free:
    push af
    xor a
    ld (snd_busy),a
    pop af
    ret
    endif
flip_due:   db 0
last_flip:  db 0
    ifdef DRAW_EVERY
    ifdef FLIP_FRAMES
pace_need:  db FLIP_FRAMES              ; screens at least this many frames apart
    else
pace_need:  db FRAMES_PER_TICK*DRAW_EVERY
    endif
    else
pace_need:  db FRAMES_PER_TICK
    endif
pace_idx:   db 0

wait_shown:                     ; the previous screen must be up before drawing again
    ei
.w:
    ld a,(flip_pending)
    or a
    ret z
    halt
    jr .w

request_flip:
    ld a,(pace_need)
    ld hl,last_flip
    add a,(hl)
    ld (flip_due),a
    ld a,1
    ld (flip_pending),a
    if PACE_PAL_MIX
    ld a,(pace_idx)             ; 2,2,2,2,1 frames
    inc a
    cp 5
    jr c,.idx
    xor a
.idx:
    ld (pace_idx),a
    cp 4
    ld a,2
    jr nz,.need
    dec a
.need:
    ld (pace_need),a
    endif
    ret

; From the interrupt: show the drawn screen if it is due.  Not while the
; main program is inside out_page (it would write the old screen bit back).
isr_flip:
    ld a,(flip_pending)
    or a
    ret z
    ld a,(flip_due)
    ld b,a
    ld a,(frames)
    sub b
    ret m
    ld hl,22                    ; the interrupted PC (10 pushes and this call)
    add hl,sp
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld hl,-out_page
    add hl,de
    ld a,h
    or a
    jr nz,.flip
    ld a,l
    cp out_page_end-out_page
    ret c
.flip:
    xor a
    ld (flip_pending),a
    ld a,(frames)
    ld (last_flip),a
    ld a,(port_bits)
    xor 8
    ld (port_bits),a
    ld a,(port_now)
    xor 8
    ld (port_now),a
    ifndef NEXT
    ld bc,0x7ffd
    out (c),a
    else
    and 8                       ; Next: the Layer 2 screen shown (NEXTREG 12h):
    rrca                        ; bank 9 for screen 0, 13 for screen 1
    add a,9
    db 0xED,0x92,0x12           ; nextreg 0x12,a
    endif
    ret

    include "convert.asm"
    include "render.asm"
    include "tables.asm"
    include "konami_spec_stubs.asm"
    include "ship.asm"          ; the ship's patterns (0.100), in the gap before the buffers
spr_vis:    ds 32               ; draw_sprites (0.109): the list's entries on screen
    assert (spr_vis & 0xff) <= 0xe0

; ---- buffers (page aligned) -------------------------------------------------
    align 256
    ifdef NEXT
    ds (0x200 - $) & 0x3FF      ; the Next: name_shadow on a 1K boundary (nx_tur.asm)
    endif
STAR_CAP equ 38
star_l:     ds 6*STAR_CAP       ; star cell lists (star_rebuild)
star_n:     ds 6                ; cells in each list
star_base:  db 0,STAR_CAP,2*STAR_CAP,3*STAR_CAP,4*STAR_CAP,5*STAR_CAP
star_wp:    ds 8                ; write pointers while making the lists...
star_lim:   db STAR_CAP,2*STAR_CAP,3*STAR_CAP,4*STAR_CAP,5*STAR_CAP,6*STAR_CAP   ; ...and their limits
    assert (star_wp & 0xff) == 0xf0 && star_lim == star_wp + 8 && (star_n >> 8) == (star_l >> 8)
    align 256
NM2_LEN equ 128
nm2_list:   ds NM2_LEN          ; 2x2 regions written since the last upload (top-left cells)
nm_list:    ds 128              ; other regions: cell, width, rows (31 used)
    assert (nm2_list & 0xff) == 0 && nm_list == nm2_list + 0x80
name_shadow: ds 768             ; VRAM 3800-3AFF
dirty0:     ds 128              ; cells screen 0 must redraw (96 bytes used)
dirty1:     ds 128              ; cells screen 1 must redraw (dirty0 + 0x80)
    align 256
bitmask:    db 1,2,4,8,16,32,64,128
    ds 8
star_cells: ds 96               ; cells showing a star tile (F6/F7), one bit per cell
    assert (star_cells & 0xff) + 96 <= 256
dz_on:      db 0                ; Konami's dissolve under way (its first chunk to the next stage
    assert dz_on >= 0x8000      ; load: native.asm); above 8000, which the Next's renderer reads
                                ; while 4000-7FFF hold the copies (nx_l2.asm lo_cmap, lo_cell)
    assert (dirty0 & 0xff) == 0 && dirty1 == dirty0 + 0x80 && (bitmask & 0xff) == 0
    ifdef NEXT
; The Next: characters Konami has written since the stage load (its native
; loads, native.asm nx_chars), one bit per character (third * 256 + char):
; the pool leaves them to the rows (nx_l2.asm lo_cmap).  lo_apply clears them.
    align 256
tile_cdirty: ds 128             ; colours (96 bytes used)
tile_pdirty: ds 96              ; patterns (tile_cdirty + 0x80)
    assert tile_pdirty == tile_cdirty + 0x80 && (tile_cdirty & 0xff) == 0
    endif
; (in the gap before the next page-aligned buffer)
; The title's tune (0.102).  On the MSX the title is silent and, after about
; 11 seconds, the attract cycle plays Konami's tune A6 over its illustration.
; Without the attract cycle, the title plays it instead: at once when the
; title appears, and again 3 seconds after each play ends.
; estado_1 (0:5308) comes here every title tick; the gap is counted in frames
; (the title's ticks run at different rates in the two editions).
TUNE_GAP equ 150                ; frames of silence before it starts again
title_tick:
    ld a,(0xE012+KRAM)          ; Konami's first music channel: 0 when silent
    or a
    jr nz,.playing
    ld a,(tune_wait)
    or a
    jr nz,.waiting
    ld a,(frames)               ; silence starts: note when
    ld (tune_from),a
    ld a,1
    ld (tune_wait),a
    jr .out
.waiting:
    ld a,(frames)
    ld hl,tune_from
    sub (hl)
    cp TUNE_GAP
    jr c,.out
    ld a,0xA6
    call m0_49E9                ; pide_sonido
.playing:
    xor a
    ld (tune_wait),a
.out:
    ld hl,0xE004+KRAM           ; estado_1 as Konami has it: E004 counts the
    dec (hl)                    ; blinking of the choice
    jp m0_5BD3                  ; parpadea_lo_elegido
tune_wait: db 0
tune_from: db 0
; The title drawn (spec_title): its tune starts at the first title tick, as
; though the gap had passed; after that, TUNE_GAP frames between plays.
title_start:
    ld a,(frames)
    sub TUNE_GAP
    ld (tune_from),a
    ld a,1
    ld (tune_wait),a
    ret
; estado_3 (0:537F), the game starting: the title's tune would play on into
; the stage, and hold the stage's music back (Konami starts it only on a
; silent channel), so it is stopped with Konami's silence request (CD).
title_end:
    ld a,(0xE012+KRAM)
    cp 0xA6
    ld a,0xCD
    call z,m0_49E9              ; pide_sonido
    ld hl,0xE004+KRAM           ; estado_3 as Konami has it
    jp m0_5382
erase0:     ds 129              ; per screen: up to 32 sprite rects [cx, cy, cols, rows], 0xFF end
erase1:     ds 129
; Small tables read with H fixed: kept in the alignment gap before DRAWN, so
; they never straddle a page as the code above them grows.
drawn_n:    ds 8                ; cells in each drawn list: [screen * 4 + third]
star_t80:   db 0,80,160         ; draw_stars: offset of each third's list
    assert (star_t80 >> 8) == ((star_t80 + 2) >> 8) && (drawn_n >> 8) == ((drawn_n + 7) >> 8)
    align 256
DRAWN:      ds 512              ; draw_stars: per screen 0x100, per third 80 cells
platform_end:
    assert platform_end <= 0xAD00

    ; Konami's RAM and our boot stack start zeroed.
; Page C, after MSX bank 3: the title's own lines, in Konami's text stream
; format (VRAM address, characters = ASCII - 0x20, 0xFE next address, 0xFF
; end) for escribe_caracteres (0:4998).  The controls go over PLAY SELECT and
; the blank row above it (rows 13-14), the credit on row 21.  Not row 22: it
; is the power-up bar's row, which play rewrites only in part.  Konami's
; font has letters and digits only.
    slot 3
    page PAGE_C
    org section_C_end
ctl_text:
    dw 0x39A3
    db 0x31,0x21,0x2F,0x30,0x00,0x00,0x33,0x30,0x21,0x23,0x25,0x00,0x26,0x29,0x32,0x25,0x00,0x00,0x2D,0x00,0x33,0x25,0x2C,0x25,0x23,0x34
    db 0xFE
    dw 0x39C0                   ; ON JOYSTICK HOLD FIRE TO SELECT
    db 0x2F,0x2E,0x00,0x2A,0x2F,0x39,0x33,0x34,0x29,0x23,0x2B,0x00,0x28,0x2F,0x2C,0x24,0x00,0x26,0x29,0x32,0x25,0x00,0x34,0x2F,0x00,0x33,0x25,0x2C,0x25,0x23,0x34
    db 0xFE
    dw 0x3AA3
    db 0x30,0x2F,0x32,0x34,0x25,0x24,0x00,0x22,0x39,0x00,0x30,0x21,0x35,0x2C,0x00,0x21,0x2E,0x24,0x00,0x23,0x2C,0x21,0x35,0x24,0x25
    db 0xFE
    include "version.inc"       ; the version, top right (row 0, ending at column 31)
    db 0xFF
ctl_text_end:
    ifdef ADAPT
; Adaptive pacing (0.110, experimental): called after each tick; carry: do
; not draw this tick.  pace_debt is how far the game is behind a rhythm of
; PACE_T eighths of a frame a tick (clamped to -32..64 eighths); a tick is
; left undrawn when that is more than PACE_SLACK, but never two in a row.
    ifdef NEXT
; Next smooth scroll: after each tick.  Konami's map moves a whole character
; on a scroll step (distance E063 up by one); the screen is then shown 7
; pixels right of it, and the gap closes by a pixel a tick, so the scenery
; moves a pixel a tick and settles when the scroll stops.  Steps in other
; modes (E1C0 = 2: one every tick) only let the gap close; a jump in the
; distance (a new stage, a restart) clears it.  Sprites are drawn the same
; distance left (render.asm), so they stay where Konami puts them.
nx_prev:    dw 0
nx_tick:
    ld hl,(0xE063-0x3100)
    ld de,(nx_prev)
    ld (nx_prev),hl
    or a
    sbc hl,de
    ld a,h
    or l
    jr z,.decay
    dec hl
    ld a,h
    or l
    jr nz,.zero
    ld a,(0xE1C0-0x3100)
    or a
    jr nz,.decay
    ld a,7
    jr .set
.zero:
    xor a
    jr .set
.decay:
    ld a,(nx_off)
    or a
    jr z,.set
    dec a
.set:
    ld (nx_off),a
    call 0x0100                 ; lo_tick (nx_low.asm): sprites, character enemies
    jp pace_adapt
    endif
pace_last:  db 0
pace_debt:  db 0
pace_prev:  db 0
    ifdef INPUT_DRAW
pace_dir:   db 0x0F             ; the directions at the last tick (kb_cache+9 bits 0-3)
pace_chg:   db 0                ; not 0: they changed this tick
    endif
pace_adapt:
    ifdef INPUT_DRAW
    ld a,(kb_cache+9)           ; a tick whose directions differ from the last
    and 0x0F                    ; tick's is drawn (the press shows sooner);
    ld hl,pace_dir              ; the debt it leaves skips a later one
    sub (hl)
    ld (pace_chg),a
    add a,(hl)
    ld (hl),a
    endif
    ld hl,pace_last
    ld a,(frames)
    ld b,(hl)
    ld (hl),a
    sub b                       ; frames since the last tick's decision
    cp 9
    jr c,.d
    ld a,8
.d:
    add a,a
    add a,a
    add a,a
    ifdef NEXT
    ld de,pace_t                ; (by 50/60 Hz, nx_hz)
    ex de,hl
    sub (hl)
    ex de,hl
    else
    sub PACE_T
    endif
    inc hl                      ; pace_debt
    add a,(hl)
    bit 7,a
    jr z,.pos
    cp 0xe0                     ; at least -32
    jr nc,.st
    ld a,0xe0
    jr .st
.pos:
    cp 65                       ; at most 64
    jr c,.st
    ld a,64
.st:
    ld (hl),a
    inc hl                      ; pace_prev: was the last tick undrawn?
    bit 7,a
    jr nz,.draw
    cp PACE_SLACK+1
    jr c,.draw
    ld a,(hl)
    or a
    jr nz,.draw                 ; never two in a row
    ifdef INPUT_DRAW
    ld a,(pace_chg)
    or a
    jr nz,.draw
    endif
    ld (hl),1
    scf
    ret
.draw:
    ld (hl),0
    or a
    ret
    endif
page_c_end:
    assert page_c_end <= 0xE800
; Page 7, F600-F7FF (between the converted tiles and the sprite patterns).
    slot 3
    page PAGE_7
    org 0xF600
page_7_code:
    include "star_check7.asm"
    include "spr_pmap.asm"

; After a tile's conversion (ensure_tile, D = third, E = id): dense tiles
; inverted (tile_invert), then the nuke capsule's tiles (77-7A; the standard
; capsule is 7B-7E) given cyan: on the MSX both are a white frame round a
; coloured core, which one ink per cell turns into the same white capsule.
; Tiles 77-7E appear only as capsules (checked over all eight stages).
; A sprite's ink (draw_sprites; A = its MSX colour 1-15, HL = its entry in
; Konami's list, page 7 in): spr_ink[colour], unless spr_pmap gives this
; pattern its own ink when it has that MSX colour (or any, for 0x10), or
; flags it (bit 7, 0x20 in spr_pmap) for attrs_keep.  Preserves BC, DE, HL.
spr_colour:
    push hl
    push de
    ld e,a
    inc l
    inc l
    ld a,(hl)                   ; pattern: 2 bytes per pattern / 4 in spr_pmap
    rrca
    and 0x7e
    or spr_pmap & 0xff
    ld l,a
    ld h,spr_pmap>>8
    ld d,0
    ld a,(hl)
    cp e
    jr z,.own
    cp 0x10                     ; 0x10: whatever its MSX colour
    jr z,.own
    cp 0x20                     ; 0x20: the usual ink, flagged for attrs_keep
    jr nz,.map
    ld d,0x80
    jr .map
.own:
    inc l
    ld a,(hl)
    jr .set
.map:
    ld hl,spr_ink
    ld a,l
    add a,e
    ld l,a
    jr nc,.nc
    inc h
.nc:
    ld a,(hl)
    or d                        ; bit 7: terrain keeps its colours
.set:
    ld (sp_ink),a
    pop de
    pop hl
    ret

; draw_sprite16's colouring for a sprite flagged in spr_pmap (bit 7 of
; sp_ink; A = sp_ink, DE = the attribute of the box's top-left cell): only
; the cells with nothing in them (tile 0) or a star (F6/F7) take its colour;
; terrain keeps its own, so the sprite shows in the terrain's colours there
; instead of recolouring the ground around it.  The player's missile.
attrs_keep:
    and 0x47                    ; ink and bright on black paper
    ld ixl,a
    ld a,(sp_rows)
    ld c,a
.row:
    ld a,(sp_cols)
    ld b,a
    push de
.col:
    ld a,d                      ; name_shadow + third * 256 + low byte
    and 3
    add a,name_shadow>>8
    ld h,a
    ld l,e
    ld a,(hl)
    or a
    jr z,.empty
    cp 0xf6
    jr c,.next
    cp 0xf8
    jr nc,.next
.empty:
    ld a,ixl
    ld (de),a
.next:
    inc e
    djnz .col
    pop de
    ld a,e
    add a,32
    ld e,a
    jr nc,.nc
    inc d
.nc:
    dec c
    jr nz,.row
    jp draw_sprite16.arec
    assert (name_shadow & 0xff) == 0
page_7_end:
    assert page_7_end <= SPR_PAT
; Page D, E400-E7FF (after MSX bank 8's sound data, E000-E3DC): the full
; map comparison.
    slot 3
    page PAGE_D
    org 0xE400
page_d_code:
    include "fullcmp_gen.asm"
    ifdef NEXT
; Spectrum Next (nextreg.txt): 28 MHz; the low area (nx_low.asm) at
; 0000-3FFF; Layer 2 shown, the ULA not; sprites on, sprite 0 on top as on
; the TMS9918; Layer 2's clip window hides the left 8 pixels (the column that
; wraps round when the screen is scrolled); a line interrupt at line 176 puts
; Layer 2's X scroll back to 0 for the status lines (isr), and nx_frame sets
; it for the play area.  Then lo_init (palettes, screens, sprites).
nx_init:
    ld bc,0x243B
    ld hl,nx_regs
    ld e,(nx_regs_end-nx_regs)/2
.r:
    ld a,(hl)
    out (c),a
    inc hl
    inc b
    ld a,(hl)
    out (c),a
    inc hl
    dec b
    dec e
    jr nz,.r
    ld a,0x08                   ; TurboSound on (nextreg 08h bit 1), the rest kept:
    out (c),a                   ; the effects play on AY 2 (nx_sfx)
    inc b
    in a,(c)
    or 2
    out (c),a
    ld a,0xFF                   ; and AY 1 selected
    call nx_aysel
    jp 0x0109                   ; lo_init
nx_regs:
    db 0x07,3                   ; CPU speed: 28 MHz
    db 0x62,0                   ; copper stopped
    db 0x50,16                  ; MMU0, MMU1: Next RAM (the .NEX's bank 8,
    db 0x51,17                  ; nx_low.asm) at 0000-3FFF in place of the ROM
    db 0x23,176                 ; line interrupt at line 176
    db 0x22,2                   ; line interrupt on (and the frame one)
    db 0x68,0x80                ; ULA off
    db 0x69,0x80                ; Layer 2 on
    db 0x70,0                   ; Layer 2 256x192, palette offset 0
    db 0x12,9                   ; Layer 2 shown: screen 0 (banks 9-11)
    db 0x16,0                   ; Layer 2 X scroll 0
    db 0x15,0x41                ; sprites on, sprite 0 on top, S over L2
    db 0x4B,0                   ; sprite colour index 0 transparent
    db 0x1C,0x0F                ; clip indices reset
    db 0x18,8                   ; Layer 2 clip X1 = 8 (X2, Y1, Y2 as reset)
    db 0x18,255
    db 0x18,0
    db 0x18,191
    db 0x19,0                   ; sprites clipped to the play area (lines 0-175):
    db 0x19,255                 ; none over the status lines (9 November)
    db 0x19,0
    db 0x19,175
nx_regs_end:
nx_shown:   db 0
nx_lastbit: db 0
; At each frame interrupt (run_sound, page D in): the machine's 50/60 Hz
; setting (NextReg 0x05 bit 2, which the F3 key toggles in play), noted for
; the pacing (lo_tick: screens 2 frames apart at 60 Hz, 30 ticks a second as
; at 50; pace_adapt's rhythm the same in ticks a second); NZ on one frame in
; six at 60 Hz, which run_sound leaves without Konami's sound driver, so the
; music keeps its 50 Hz tempo.
nx_hz:
    ld bc,0x243B
    ld a,0x05
    out (c),a
    inc b
    in a,(c)
    and 4
    ld (nx_hz60),a
    ifdef ADAPT
    ld a,PACE_T
    jr z,.t
    ld a,(PACE_T * 6 + 2) / 5   ; the same rhythm in 60 Hz frames
.t:
    ld (pace_t),a
    ld a,(nx_hz60)
    endif
    or a
    ret z                       ; 50 Hz: Z, the driver runs
    ld hl,nx_hzc
    dec (hl)
    jr z,.skip
    xor a                       ; Z: the driver runs
    ret
.skip:
    ld (hl),6
    or a                        ; (A = 4) NZ: left out this frame
    ret
nx_frame:                       ; from the frame interrupt, page D in
    ld bc,0x243B
    ld a,0x1E                   ; the line now: if it is the line interrupt's,
    out (c),a                   ; the frame/line toggle was out of step
    inc b
    in a,(c)
    dec b
    or a
    jr nz,.ok
    ld a,0x1F
    out (c),a
    inc b
    in a,(c)
    dec b
    sub 176
    cp 8
    jr nc,.ok
    xor a
    ld (nx_tog),a               ; the next one is a frame interrupt
.ok:
    ld a,(port_bits)            ; a flip since the last frame: the new
    and 8                       ; screen's offset
    ld hl,nx_lastbit
    cp (hl)
    jr z,.same
    ld (hl),a
    ld a,(nx_pend)
    ld (nx_shown),a
    push bc
    call 0x0115                 ; lo_sprflip: this screen's sprites
    pop bc
.same:
    ld a,0x16                   ; Layer 2 X scroll: lo_render's value
    out (c),a
    inc b
    ld a,(nx_shown)
    out (c),a
    ret
    endif
page_d_end:
    assert page_d_end <= PAT_SHADOW
    ifdef NEXT

; Next: Konami's own instructions that call into nx_low.asm (0:46A1, 2:9251,
; 0:4100, 0:414B, 0:5851, 0:544F, 2:99A1, 2:99C3, 3:A19B) and the sound
; request's di and ei (0:4A02, 0:4A11: snd_hold, snd_free) are
; reloc/gen.py's NEXT_PATCH entries, under ifdef NEXT in konami_spec.asm.  (Page A at C000 when the snapshot is
; saved, as the .NEX's entry bank, as before.)
    slot 3
    page PAGE_A
    endif

; The native build's graphics, packed (native_pack.py): in the room the MSX
; graphics, their copies and the colour fit left in pages A, B, C, D and E.
    ifndef NEXT
    include "native_data.asm"
    endif

    ifdef TEST
    savesna "nemesis_test.sna", plat_boot
    else
    ifdef NEXT
    savesna "nemesis_next.sna", plat_boot
    else
    savesna "nemesis.sna", plat_boot
    endif
    endif
