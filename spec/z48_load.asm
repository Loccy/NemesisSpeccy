; The 48K multiload: each stage is a whole image (its own selection of
; Konami's code, its tiles, sprites, map and Big Core), on tape as two
; headerless blocks, 5B00-AEFF (flag 0x10 + stage) and C000-FFFF (flag 0x20 +
; stage).  Konami's RAM (AF00-BFFF) is never loaded over, so the score,
; lives and weapons carry across; the loader lives in a part of it Konami
; never writes (BF01-BF7F, z48_fixed.asm), the same in every image.
;
; The switch: Konami asks for a stage's graphics (carga_los_graficos_de_la_
; fase, 0:422A, nl_stage) from 0:4100 (a stage begun: the next one, or the
; same one again) or 0:414B (a life, from 0:53BE).
; If the stage is not this image's, the old image notes the way in and calls
; the loader; the new one (z48_enter) starts from the platform's main loop as
; though that tick were being run again from 0:4100 or 0:4129.

    ifndef LAST48
LAST48 equ 8
    endif
LDR48 equ 0xBF01              ; the loader (z48_fixed.asm)
ENTRY48 equ 0xAEFD            ; every image's way in: jp z48_enter

; From nl_stage, E061 not this image's stage.  (SP+2): the return from the
; call of 0:422A, (SP+4) the one before.  (The demo, 0:5CB5, is not in the
; 48K version.)
z48_other:
    ld hl,2
    add hl,sp
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld c,1                      ; 1: 0:4100, a stage begun
    ld hl,m0_4103
    or a
    sbc hl,de
    jr z,.go
    ld c,2                      ; 2: 0:4129 (0:53BE), a life
    ld hl,m0_414E
    or a
    sbc hl,de
    jp nz,z48_trap
    ld hl,4
    add hl,sp
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld hl,m0_53C1
    or a
    sbc hl,de
    jp nz,z48_trap
.go:
    di
    push bc
    call z48_cls
    ld a,(0xE061+KRAM)
    if LAST48 < 8               ; (a shorter test tape: past its last stage)
    cp LAST48+1
    jr c,.stage
    ld a,1                      ; past the last stage: the end, and stage 1
    ld (0xE061+KRAM),a          ; again as Konami's own wrap after the
    ld hl,0xE111+KRAM           ; eighth does it (0:6FE6): difficulty four
    ld a,(hl)                   ; steps down, E06C-E06D cleared, the loop
    sub 4                       ; counted
    jr nc,.d
    xor a
.d:
    ld (hl),a
    ld hl,0
    ld (0xE06C+KRAM),hl
    ld hl,0xE06A+KRAM
    inc (hl)
    jr nz,.e
    dec (hl)
.e:
    ld hl,z48_end_text
    jr .show
    endif
.stage:
    ifdef Z48SH                 ; stage 1 from the last stage's block: the game
    cp 1                        ; is over (Konami has wrapped, 1:6FE6)
    jr nz,.st
    ld hl,OV48
    ld a,LAST48
    cp (hl)
    ld hl,z48_end_text
    jr z,.show
    ld a,1
.st:
    endif
    add a,'0'
    ld (z48_ld_n),a
    ld hl,z48_ld_text
    call z48_title.s
    ld a,(0xE061+KRAM)
    ifdef Z48SH
    ld hl,OV48                  ; (the stage in memory: its header's first byte)
    cp (hl)
    else
    cp STAGE48
    endif
    ld hl,z48_rw_text
    jr c,.show                  ; an earlier stage: the tape rewound
    ld hl,z48_none
.show:
    call z48_title.s
    pop bc
    ld a,(0xE061+KRAM)
    jp LDR48

; From a jump slot to the front end (the title, a new game), which only
; stage 1's block holds (gen.py Z48_FEONLY): in stages 2-8 after game over.
; Stage 1 is loaded (an earlier stage: the tape rewound) and its tick run
; again from the start (z48_enter, way 3).
z48_fe:
    di
    call z48_cls
    ld a,'1'
    ld (z48_ld_n),a
    ld hl,z48_ld_text
    call z48_title.s
    ld hl,z48_rw_text
    call z48_title.s
    ld a,1
    ld c,3
    jp LDR48

; Game over (13 November, the user's choice): Konami's screen waits for a
; key, with no tune to beat on a tape machine.  C continues (Konami's own
; check, 0:54F3, sets E06F); R goes to the title: in stage 1 a restart, in
; the others the rewind (z48_fe).  0:549F's wait for the tune is this: Z to
; go on.
z48_go:
    ld a,(0xE06F+KRAM)
    dec a
    ret z                       ; C
    ld a,0xFB                   ; Q W E R T
    in a,(0xFE)
    and 8                       ; R
    ret
; The third line, "RE....  R": the stage's word (its header, OV48+47: "WIND "
; or, in stage 1, "START") put in before Konami writes the screen (0:54E3).
z48_go_text:
    push de
    ld hl,OV48+47
    ld de,z48_go_word
    ld bc,5
    ldir
    pop de
    jp m0_4998

z48_end_text:
    db 9,12,0x47,"THE END",0
z48_rw_text:
    db 13,5,0x47,"PLEASE REWIND THE TAPE",0,0xff
z48_ld_text:
    db 11,8,0x47,"LOADING STAGE "
z48_ld_n:
    db "0",0
z48_none:
    db 0xff

; Every image's way in from the loader (ENTRY48), A = the way: 0 the first
; load (the game from power-on), 1 a stage begun (0:4100), 2 a life (0:4129,
; returning to 0:53C1), 3 the front end (z48_fe: the tick from the start).
z48_enter:
    or a
    jp z,plat_boot
    ld sp,0xBFF0                ; Konami's stack, as INIT leaves it (0:40A0)
    push af
    xor a
    out (0xfe),a
    ld (0xE012+KRAM),a          ; no tune playing (z48_tune is new)
    ld (0xE005+KRAM),a          ; the tick's lock (0:4045) let go: that tick is over
    ld (z48_t),a                ; the title not on the screen (the load's text is)
    ld (z48_bc),a               ; the block's tiles are as loaded: nothing to put back
    ld a,0x10
    ld (port_bits),a
    ld a,0xAD                   ; the table and AEAE's ei / ret came loaded
    ld i,a
    im 2
    call kempston_detect
    ld a,0xc3
    ld (0xAEAE),a
    ld hl,isr
    ld (0xAEAF),hl
    call render_init
    pop af
    ei
    cp 3
    jp z,plat_main              ; 3: the front end, its tick run again
    ld hl,pm_tiles              ; the rest of the main loop's tick
    push hl
    dec a
    jr nz,.life
    call m0_4100                ; a stage begun.  The rest of that tick (the
    xor a                       ; scroll's step, 0:4565) is not run, so what
    ld (0xE100+KRAM),a          ; it would have cleared is cleared here: E107
    ld (0xE107+KRAM),a          ; still says the old stage's scroll had
    ret                         ; stopped, and its end would start at once
.life:
    ld hl,m0_53C1
    push hl
    jp m0_4129

    assert m0_4100 != z48_trap && m0_4103 != z48_trap && m0_4129 != z48_trap && m0_414E != z48_trap
    assert m0_53C1 != z48_trap
