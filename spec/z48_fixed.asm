; The multiload's fixed places, the same in every stage's image
; (z48_load.asm).

; The interrupt table, loaded with each image: AD00-AE00 all AE, and at AEAE
; ei / ret until z48_enter (or plat_boot) puts its jump there.  An interface
; that loads a block at once and returns with interrupts on finds these.
    org 0xAD00
    ds 257,0xAE
    org 0xAEAE
    db 0xFB,0xC9
    org ENTRY48
    jp z48_enter
    assert $ == 0xAF00

; The loader, in Konami's RAM where it never writes (MSX F001-F07F), so the
; one the first load put there serves every load after.  A = the stage, C =
; the way in (z48_enter).  Interrupts off; its stack in F081-F0B5, also
; never written.
    org LDR48
z48_ldr:
    ld sp,0xBFB6
    ld (z48_lst),a
    ld a,c
    ld (z48_lhow),a
z48_lda:
    ifdef Z48SH                 ; the shared layout: the stage's block alone,
    ld a,(z48_lst)              ; packed (ZX0), every stage's the same length
    add a,0x10                  ; (make_tap48.py pads them at the front and
z48_lx equ $+2                  ; writes the length and the address here):
    ld ix,0                     ; the block's last 3 bytes, the packed data's
z48_ll equ $+1                  ; start, padding, then the packed data, which
    ld de,0                     ; ends at FFFF, unpacked in place to OV48 up
    call z48_lb
    jr nc,z48_lda                ; (a wrong block, or a bad load: the next)
z48_lx2 equ $+1
    ld hl,0
    ld de,z48_tail
    ld bc,3
    ldir
    ld a,(hl)
    inc hl
    ld h,(hl)
    ld l,a
    ld de,OV48
    call dzx0_standard
    ld hl,z48_tail
    ld de,0xFFFD
    ld bc,3
    ldir
    ld a,(z48_lhow)
    jp ENTRY48
    else
    ld a,(z48_lst)
    add a,0x10
    ld ix,0x5B00
    ld de,0xAF00-0x5B00
    call z48_lb
    jr nc,z48_lda                ; (a wrong block, or a bad load: the next)
.b:
    ld a,(z48_lst)
    add a,0x20
    ld ix,0xC000
    ld de,0x4000
    call z48_lb
    jr nc,.b
    ld a,(z48_lhow)
    jp ENTRY48
    endif
z48_lb:                         ; the ROM's LD-BYTES joined at 0562, as the
    scf                         ; first loader does (make_tap48.py)
    inc d
    ex af,af'
    dec d
    di
    ld a,0x0f
    out (0xfe),a
    call 0x0562
    di
    ret
z48_lst:    db 0
z48_lhow:   db 0
z48_tail:   ds 3                ; (the block's last 3 bytes, aside while it unpacks)
    assert $ <= 0xBF80
