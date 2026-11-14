; The 48K demo's graphics loads: stage 1 only.  The tile set and the sprite
; patterns are in place from the start (tiles48.bin, spr48.bin, with
; Konami's font in thirds 0 and 1, where stage 1 has nothing), so the loads
; before each life and at game over have nothing to do.  The Big Core puts
; its characters over stage 1's; a stage load (a new game, a life lost, the
; stage begun again) puts stage 1's back.  Each set of those characters
; (z48_data.asm) is unpacked into the screen's bitmap, its attributes black
; meanwhile, and copied into the tile set; every cell is then drawn again.

nl_count:   db 0                ; loads so far (for the checks)
nl_w:       dw 0                ; the next byte of the patch
nl_mb:      db 0                ; the mask byte, turning
z48_bc:     db 0                ; the Big Core's (or the font's) characters are in
z48_pn:     dw 0                ; z48_patch: the characters in the set
z48_bonus:  db 3,4,5,8          ; bonus stages 9-12 replaced by the stages after them
    assert (z48_bonus >> 8) == ((z48_bonus + 3) >> 8)

; 0:422A, carga_los_graficos_de_la_fase.  Another stage's: loaded from tape
; (z48_load.asm).
nl_stage:
    ld a,(0xE061+KRAM)
    cp 9
    jr c,.main
    sub 9                       ; a bonus stage (9-12): none in the 48K; the
    add a,z48_bonus&0xff        ; stage it would return to instead
    ld l,a                      ; (fases_por_ronda, 0:418F)
    ld h,z48_bonus>>8
    ld a,(hl)
    ld (0xE061+KRAM),a
.main:
    ifdef Z48SH
    ld hl,OV48                  ; (the stage's header: its number first)
    cp (hl)
    else
    cp STAGE48
    endif
    call nz,z48_other           ; (returns only for the demo: this stage)
    call nl_save
    ld a,(z48_bc)
    or a
    jr z,.tiles
    ifndef Z48_NOBC
    xor a
    ld (z48_bc),a
    ifdef Z48SH
    ld hl,(OV48+7)              ; the stage's own characters back
    ld bc,(OV48+11)
    ld de,(OV48+9)
    else
    ld hl,z48_rmask_z           ; the stage's own characters back
    ld bc,z48_rnum
    ld de,z48_s1_data
    endif
    call z48_patch
    endif
.tiles:
    ifdef Z48SH
    ld hl,(OV48+19)
    else
    ld hl,z48_star_attr
    endif
    ld de,star_attr
    ld bc,6
    ldir
    call bl_reset
    call nl_done
    pop ix
    pop af
    pop bc
    pop de
    pop hl
    ld a,1
    ld (0xE100+KRAM),a
    jp m0_4299                  ; devuelve_el_reparto_de_siempre

nl_bigcore:                     ; 0:4A8A (the Big Core's characters)
    ifdef Z48_NOBC              ; (the preview: drawn with stage 1's)
    ret
    else
    call nl_save
    ifdef Z48SH
    ld hl,(OV48+1)
    ld bc,(OV48+5)
    ld de,(OV48+3)
    else
    ld hl,z48_mask_z
    ld bc,z48_n
    ld de,z48_bc_data
    endif
    call z48_patch
    ld a,1
    ld (z48_bc),a
    jp nl_restore
    endif

    ifdef Z48SH
nl_prestage:                    ; 0:53D4: the font's characters that clash
nl_gameover:                    ; 0:54DD  with the stage's (none: nothing)
    call nl_save
    ld hl,(OV48+17)
    ld a,h
    or l
    jp z,nl_restore
    ld hl,(OV48+13)
    ld bc,(OV48+17)
    ld de,(OV48+15)
    call z48_patch
    ld a,1
    ld (z48_bc),a
    jp nl_restore
    elseif z48_fn
nl_prestage:                    ; 0:53D4: the font's characters that clash
nl_gameover:                    ; 0:54DD  with the stage's
    call nl_save
    ld hl,z48_fmask_z
    ld bc,z48_fn
    ld de,z48_ft_data
    call z48_patch
    ld a,1
    ld (z48_bc),a
    jp nl_restore
    else
nl_prestage:                    ; 0:53D4 (the font is in place)
nl_gameover:                    ; 0:54DD (the same)
    endif
nl_title:                       ; 0:5300 (the demo's own title)
nl_marcador:                    ; 0:4C2E (the ending: not in the demo)
nl_ending:                      ; 0:4B04
    ret

; 3:A765, a chunk of the dissolve (stages 7 and 8): not yet done in the 48K
; (13 November).  Konami's passes still run and count, but nothing changes
; on the screen: the scenery stays as it was until the next stage's graphics
dz_chunk:
    ret

nl_save:                        ; every register kept for Konami
    ex (sp),hl
    push de
    push bc
    push af
    push ix
    push hl
    xor a
    ld (dz_on),a
    ret
nl_restore:                     ; (jumped to, with nl_save's pushes on the stack)
    pop ix
    pop af
    pop bc
    pop de
    pop hl
    ret

nl_done:                        ; every cell redrawn at the end of the tick
    ifdef TRIM
    ld a,1
    ld (spx_stale),a
    endif
nl_done_t:
    ld a,0xff
    ld (chg_n),a
    ld a,1
    ld (star_stale),a
    ld hl,nl_count
    inc (hl)
    ret

    ifndef Z48_NOBC
; DE = a packed set: the index entries of the BC characters the packed mask
; at HL marks (their tiles' numbers, then their groups' attribute pages).
z48_patch:
    ld (z48_pn),bc
    push de
    push hl
    ld hl,0x5800                ; the screen black: its bitmap is the work area
    ld de,0x5801
    ld bc,767
    ld (hl),0
    ldir
    pop hl
    ld de,0x4000
    call dzx0_standard
    pop hl
    ld de,0x4060
    push de
    call dzx0_standard
    pop hl
    ld (nl_w),hl                ; the numbers; the pages BC on
    ld c,0                      ; the mask byte's index
.mb:
    ld l,c
    ld h,0x40
    ld a,(hl)
    ld (nl_mb),a
    ld b,0                      ; bit
.bit:
    ld a,(nl_mb)
    rrca
    ld (nl_mb),a
    call c,.one
    inc b
    ld a,b
    cp 8
    jr nz,.bit
    inc c
    ld a,c
    cp 96
    jr nz,.mb
    jp nl_done
.one:                           ; character c * 8 + b of third c / 32
    push bc
    ld a,c
    and 31
    add a,a
    add a,a
    add a,a
    add a,b
    ld e,a                      ; char
    ld a,c
    rlca
    rlca
    rlca
    and 3
    add a,a
    add a,IDX48
    ld d,a                      ; the third's index
    ld hl,(nl_w)
    ld a,(hl)
    ld (de),a                   ; the tile's number
    inc hl
    ld (nl_w),hl
    dec hl
    ld bc,(z48_pn)
    add hl,bc
    inc d
    ld a,(hl)
    ld (de),a                   ; its group
    pop bc
    ret

    include "tape/dzx0_standard.asm"
    endif
