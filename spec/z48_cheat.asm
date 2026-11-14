; The test build (Z48_CHEAT): each life starts powered up, with speed 2, the
; laser and two options (Konami's own mejora_opcion, 3:A0C1, makes them);
; build48.py also makes the ship invulnerable (la_nave_ha_muerto, 1:75F0, a
; bare ret).  From render_frame in play.  In
; page 7 (with the stage's block), so that the core is the same as the
; plain build's.
z48_cheat7:
    ld a,(0xE000+KRAM)
    cp 5
    ret nz
    ld a,(0xE20E+KRAM)          ; the laser: once each life
    or a
    ret nz
    push ix
    push iy
    xor a
    ld (0xE20C+KRAM),a          ; no double
    ld (0xE20D+KRAM),a
    inc a
    ld (0xE20E+KRAM),a          ; the laser
    ld a,2
    ld (0xE202+KRAM),a          ; speed
    call m3_A0C1
    call m3_A0C1
    pop iy
    pop ix
    ret
