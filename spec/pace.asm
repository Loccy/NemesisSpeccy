; Adaptive pacing (0.110): called after each tick; carry: do not draw this
; tick.  pace_debt is how far the game is behind a rhythm of PACE_T eighths
; of a frame a tick (clamped to -32..64 eighths); a tick is left undrawn
; when that is more than PACE_SLACK, but never two in a row.
; Included by plat_spec.asm: in fixed memory on the 128K, after the buffers
; (the main loop calls it every tick, and in page C that was a page switch
; there and back); in page C after nx_tick on the Next.
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
