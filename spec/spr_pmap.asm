; Per-pattern sprite inks (draw_sprites): for pattern p, the bytes at
; spr_pmap + p/2 are [MSX colour, ZX ink]; when the sprite has that colour
; (any colour for 0x10) it gets that ink instead of spr_ink's.  Patterns as
; seen in play: 120-132 an explosion's frames, whatever the enemy (white,
; light red, dark red, magenta for most on the MSX: here bright yellow,
; bright yellow, bright red, red: fire), 136 the enemy bullet (light red:
; kept white).  0x20 instead of a colour: the usual ink, and the cells it
; covers that hold terrain keep their colours (attrs_keep): 28 and 32, the
; player's missile rolling along the ground and falling (MSX colours 10/11,
; blinking).
    align 128
spr_pmap:
    ds 128
    org spr_pmap + 28 / 2
    db 0x20, 0
    db 0x20, 0
    org spr_pmap + 120 / 2
    db 0x10, 0x46
    db 0x10, 0x46
    db 0x10, 0x42
    db 0x10, 0x02
    db 9, 0x07
    org spr_pmap + 128
    assert (spr_pmap & 0x7f) == 0
