; The 48K demo's own pieces: the trap for Konami's code it leaves out, the
; stand-in for the sound driver, and the title.

SHAPES48 equ 0xD9EE           ; bank 5's object shapes (gen.py SHAPES48)
TUNE48 equ 200                ; frames a tune is taken to last

; Every item of Konami's that the demo leaves out (gen.py, z48_keep.txt) is
; this: the address on the top of the stack (the return from the call that
; led here) shown at the foot of the screen, the border red, and the machine
; stopped.
z48_trap:
    di
    pop hl
    ld de,z48_trap_hex
    ld a,h
    call .hex2
    ld a,l
    call .hex2
    ld hl,z48_trap_text
    call z48_title.s
    ld a,2
    out (0xfe),a
    halt
.hex2:
    push af
    rrca
    rrca
    rrca
    rrca
    call .hex1
    pop af
.hex1:
    and 15
    add a,'0'
    cp '9'+1
    jr c,.dig
    add a,7
.dig:
    ld (de),a
    inc de
    ret
z48_trap_text:
    db 23,0,0x57,"TRAP "
z48_trap_hex:
    db "0000",0,0xff

; No sound driver.  Konami's requests come to encola_sonido (0:4A22, jumped
; here), A = the sound.  Konami waits in places until its first music
; channel (E012) is silent again (game over, a change of music): a tune
; marks it busy for TUNE48 frames, and effects are dropped.
z48_tune:   db 0
z48_snd:
    and 0x7f
    push af
    call z48_sfx                ; a beeper effect, if the code has one
    pop af
    cp 0x16
    ret c
    ld (0xE012+KRAM),a
    ld a,TUNE48
    ld (z48_tune),a
    ret


z48_tune_tick:                  ; from the interrupt
    ld a,(z48_tune)
    or a
    ret z
    dec a
    ld (z48_tune),a
    ret nz
    ld (0xE012+KRAM),a
    ret

z48_cls:                        ; the screen black: from the top of the colours down, so it
    ld hl,0x5AFF                ; is black at once (the clear takes nearly 3 frames)
    ld de,0x5AFE
    ld bc,6911
    ld (hl),0
    lddr
    ret

; The title, in the ROM's font (3D00).
z48_title:
    call z48_cls
    call OV48+52                ; the stage's logo (stage 1's: jp z48_logo; the others: ret)
    ld hl,z48_title_text
.s:
    ld a,(hl)                   ; row (0xFF: the end), column, attribute, text, 0
    cp 0xff
    ret z
    ld b,a
    inc hl
    ld c,(hl)
    inc hl
    ld a,(hl)
    inc hl
    ld (.attr+1),a
.c:
    ld a,(hl)
    inc hl
    or a
    jr z,.s
    push hl
    ld l,a                      ; the glyph: 3C00 + 8 * code
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,0x3C00
    add hl,de
    ld a,b                      ; the screen: 4000 | (row & 0x18) << 8 | (row & 7) << 5 | column
    and 0x18
    or 0x40
    ld d,a
    ld a,b
    and 7
    rrca
    rrca
    rrca
    or c
    ld e,a
    push de
    ld a,8
.row:
    ex af,af'
    ld a,(hl)
    ld (de),a
    inc hl
    inc d
    ex af,af'
    dec a
    jr nz,.row
    pop de                      ; the attribute: 5800 + row * 32 + column
    ld a,d
    rrca
    rrca
    rrca
    and 3
    or 0x58
    ld d,a
.attr:
    ld a,0
    ld (de),a
    pop hl
    inc c
    jr .c

z48_title_text:
    db 9,0,0x46
    db "NEMESIS 48 - BY PAUL AND CLAUDE",0
    db 14,6,0x47
    db "PRESS FIRE TO START",0
    db 0xff

z48_cheat:                      ; (the test build calls z48_cheat7 instead: z48_cheat.asm)
    ret
