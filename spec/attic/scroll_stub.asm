; The map scroll: entry from Konami (MSX 4695).  The work is in scroll.asm
; (page D).
scroll_native:
    ld a,(nm_full)
    or a
    jr z,.native
    ld hl,0xED01+KRAM           ; a full comparison is due anyway: plain shift
    ld de,0xED00+KRAM
    ld b,22
.plain:
    push bc
    ld bc,31
    ldir
    pop bc
    inc hl
    inc de
    djnz .plain
    jp m0_46A8
.native:
    ld a,(cur_page)             ; the shift runs from page D (E400); cur_page
    push af                     ; says so, so the interrupt maps it back
    ld a,PAGE_D
    call set_page
    call scroll_d
    pop af
    call set_page
    jp m0_46A8
