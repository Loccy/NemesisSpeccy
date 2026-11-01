; Stage colour rules (page C).  A tile of stage 2, 3, 6, 7 or 8 is drawn by
; hand-set rules instead of the colour fit: each rule recognises its tiles by
; the MSX colours in them (and for the stage 2 bricks and the stage 8 ladder,
; the tile number too) and either paints the tile afresh from its MSX colours
; or changes the colours the fit chose.  Reached from tile_post through
; stage_rules (fixed), with page C mapped; D = third, E = tile, cv_pat and
; cv_col the MSX rows, cv_out the fit's result (8 rows and the attribute).
; Returns by mapping page 7 again (tile_post's page).  Preserves DE.
;
; A rule that paints works per pixel line with masks: for a table that gives
; each MSX colour 0x00 or 0xFF, rowmask makes the 8 lines' masks of the
; pixels whose colour has 0xFF.  Stippled pixels are those with (x + y) odd,
; x counted from the left: 0x55 on even lines, 0xAA on odd ones.
;
; Spectrum attributes: 0x05 cyan on black, 0x47 bright white on black,
; 0x07 white on black, 0x0F white on blue, 0x41 bright blue on black,
; 0x4C bright green on bright blue, 0x4F bright white on bright blue.

rules_c:
    push de
    ld a,d
    cp 2
    jr nz,.tile
    ld a,e
    cp 0x44                     ; the power-up bar and the score: never
    jp c,rules_out
.tile:
    ld a,(dz_on)                ; a tile of Konami's dissolve (every row's
    or a                        ; background black, as dz_tile takes them):
    jr z,.rules                 ; no rules (0.107)
    ld hl,cv_col
    ld b,8
.dzbg:
    ld a,(hl)
    and 0x0e
    jr nz,.rules
    inc hl
    djnz .dzbg
    jp rules_out
.rules:
    ld a,(0xE061+KRAM)          ; Konami's stage
    cp 2
    jp z,rules_2
    cp 10
    jp z,rules_10
    cp 9                        ; the bonus stages (9-12) use stage 2's bricks
    jr c,.not_bonus
    cp 13
    jp c,rules_2
.not_bonus:
    cp 3
    jp z,rules_3
    cp 6
    jp z,rules_6
    cp 7
    jp z,rules_7
    cp 8
    jp z,rules_8
rules_out:
    pop de
    call tile_invert            ; mostly ink: stored the other way round
    ld a,PAGE_7
    jp set_page

; MSX 3:A6C0 (apaga_la_pantalla), the screen dissolve, runs once a tick until
; it is done: its first instruction, ld hl,E1A0, comes here (0.107).  The
; flag stays up until the next graphics load or stage change.
dz_mark:
    ld a,1
    ld (dz_on),a
    ld hl,0xE1A0+KRAM
    ret

; come_un_trozo (MSX 3:A765), one chunk of the dissolve, done natively
; (0.107).  Konami copies a chunk of the colour or pattern table (A = its
; first tile row, DE = the table) to EA00, ANDs it with the mask (E1A2: the
; same for every byte in step 0, turned three bits a byte after), and writes
; it back; here the shadow is masked in place, EA00 is left as Konami leaves
; it, and each tile that changed is marked as the bulk write would mark it.
dz_chunk:
    push ix
    ld bc,0x200                 ; Konami's chunk sizes: 64 tiles...
    cp 0x44
    jr nz,.c1
    ld bc,0x1e0                 ; ...60 from row 44 (the score and bar spared)
.c1:
    cp 0xc0
    jr nz,.c2
    ld bc,0x1b0                 ; ...54 from row C0 (F6-FF spared)
.c2:
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,de                   ; HL = the VRAM address
    ld a,h
    cp 0x20
    jr nc,.pat
    call dz_col
    pop ix
    ret
.pat:
    call far_dz_pat             ; the pattern shadow is in page D
    pop ix
    ret
dz_col:
    DZ_CHUNK COL_SHADOW, 0, tile_cdirty

; ---- helpers ---------------------------------------------------------------

; A = colour 0-15 -> A = byte of the table at (r_tab).  Preserves the rest.
r_get:
    push hl
    ld hl,(r_tab)
    or l
    ld l,a
    ld a,(hl)
    pop hl
    ret

; HL = table (16 aligned), DE = 8-byte buffer: the lines' masks of the pixels
; whose colour the table marks.  Returns A = OR of the masks (Z: none).
rowmask:
    ld (r_tab),hl
    ld hl,cv_pat
    xor a
    ld (r_or),a
    ld b,8
.line:
    ld c,(hl)                   ; this line's pattern
    ld a,l
    add a,8
    ld l,a
    ld a,(hl)                   ; its colours
    push af
    rrca
    rrca
    rrca
    rrca
    and 15
    call r_get
    and c                       ; foreground pixels marked
    ld (r_t),a
    pop af
    and 15
    call r_get
    ld (r_t+1),a
    ld a,c
    cpl
    push hl
    ld hl,r_t+1
    and (hl)                    ; background pixels marked
    dec hl
    or (hl)
    pop hl
    ld (de),a
    inc de
    push hl
    ld hl,r_or
    or (hl)
    ld (hl),a
    pop hl
    ld a,l
    sub 7
    ld l,a
    djnz .line
    ld a,(r_or)
    or a
    ret

; r_cnt[16] = how many of the 64 pixels have each colour.
count:
    ld hl,r_cnt
    ld b,16
.clr:
    ld (hl),0
    inc hl
    djnz .clr
    ld hl,cv_pat
    ld b,8
.line:
    ld a,(hl)
    ld c,0                      ; set pixels
    ld e,8
.bit:
    add a,a
    jr nc,.nb
    inc c
.nb:
    dec e
    jr nz,.bit
    ld a,l
    add a,8
    ld l,a
    ld a,(hl)                   ; colours
    push hl
    push af
    rrca
    rrca
    rrca
    rrca
    and 15
    ld hl,r_cnt
    add a,l
    ld l,a
    ld a,(hl)
    add a,c
    ld (hl),a
    pop af
    and 15
    ld hl,r_cnt
    add a,l
    ld l,a
    ld a,8
    sub c
    add a,(hl)
    ld (hl),a
    pop hl
    ld a,l
    sub 7
    ld l,a
    djnz .line
    ret
    assert (r_cnt & 0xff) <= 0xf0

; HL = table marking the colours a rule allows: Z if every pixel's colour is
; one of them.  (Built from a table marking the others.)
only:
    ld de,r_m3
    call rowmask
    ret

; Write the 8 masks at HL to cv_out and the attribute A.
put:
    ld (cv_out+8),a
    ld de,cv_out
    ld bc,8
    ldir
    jp rules_out

; r_m1 |= r_m2 & stipple, into r_m1.
stip_in:
    ld hl,r_m1
    ld de,r_m2
    ld b,8
    ld c,0x55
.l:
    ld a,(de)
    and c
    or (hl)
    ld (hl),a
    inc hl
    inc de
    ld a,c
    cpl
    ld c,a
    djnz .l
    ret

; The attribute in cv_out: ink or paper of colour B becomes colour C.
swap_colour:
    ld hl,cv_out+8
    ld a,(hl)
    and 7
    cp b
    jr nz,.paper
    ld a,(hl)
    and 0xf8
    or c
    ld (hl),a
.paper:
    ld a,(hl)
    rrca
    rrca
    rrca
    and 7
    cp b
    ret nz
    ld a,(hl)
    and 0xc7
    ld (hl),a
    ld a,c
    rlca
    rlca
    rlca
    or (hl)
    ld (hl),a
    ret

; ---- stage 2: the bricks ----------------------------------------------------
; By tile, if the tile has only black, the blues, grey and white: grey and
; white pixels solid, blue ones stippled; the left half of a 2x1 brick, the
; first and last thirds of a 3x1 one and the left of a flat bar cyan, the
; rest bright white.  The 3x1 brick's last third keeps only its stipple.
rules_2:
    ld a,e
    sub 0x45
    cp 7
    jp nc,rules_out
    ld (r_idx),a
    ld hl,t2_bad
    call only
    jp nz,rules_out
    ld hl,t_e_f                 ; grey and white: solid
    ld a,(r_idx)
    cp 0x49-0x45
    jr nz,.solid
    ld hl,t_none                ; (the 3x1 brick's last third: none)
.solid:
    ld de,r_m1
    call rowmask
    ld hl,t_4_5                 ; the blues: stippled
    ld de,r_m2
    call rowmask
    call stip_in
    ld a,(r_idx)
    ld hl,t2_attr
    add a,l
    ld l,a
    ld a,(hl)
    ld hl,r_m1
    jp put

; ---- bonus stage 10: its bricks as stage 2's, its balls dark yellow ----------
; A character of only the yellows (MSX 10 and 11) with 8 or more such pixels
; (not a one-pixel star): yellow (not bright) on black, as on the MSX.
rules_10:
    ld hl,t10_bad
    call only
    jr nz,.bricks
    call count
    ld a,(r_cnt)
    cp 64-7
    jp nc,rules_out
    ld hl,t_nonzero
    ld de,r_m1
    call rowmask
    ld a,0x06
    ld hl,r_m1
    jp put
.bricks:
    pop de                      ; (only clobbered E, the tile)
    push de
    jp rules_2

; ---- stage 3: faces cyan, rocks magenta ------------------------------------
; In the Moai section only (Konami's distance below 0x195):
; The fit's white or grey becomes cyan in a tile whose main colour (the most
; pixels, black and transparent aside; a tie goes to the colour met first,
; line by line, foreground before background) is dark or light blue, and
; magenta in one whose main colour is light red.
rules_3:
    ld a,(0xE064+KRAM)          ; only in the Moai section (to distance 0x195):
    or a                        ; the turrets and the boss after it keep the fit
    jr z,.moai
    dec a
    jp nz,rules_out
    ld a,(0xE063+KRAM)
    cp 0x95
    jp nc,rules_out
.moai:
    call count
    ld hl,r_cnt+2
    ld b,14
    xor a
.max:
    cp (hl)
    jr nc,.nm
    ld a,(hl)
.nm:
    inc hl
    djnz .max
    or a
    jp z,rules_out
    ld c,a                      ; the most
    ld hl,cv_col
    ld b,8
.first:
    ld a,(hl)
    rrca
    rrca
    rrca
    rrca
    and 15
    ld e,a
    call .is_max
    jr z,.kind
    ld a,(hl)
    and 15
    ld e,a
    call .is_max
    jr z,.kind
    inc hl
    djnz .first
    jp rules_out                ; (not reached)
.is_max:                        ; A = colour: Z if it is >= 2 and has C pixels
    cp 2
    jr c,.no
    push hl
    ld hl,r_cnt
    add a,l
    ld l,a
    ld a,(hl)
    pop hl
    cp c
    ret
.no:
    or 1
    ret
.kind:
    ld a,e
    ld c,5                      ; cyan
    cp 4
    jr z,.swap
    cp 5
    jr z,.swap
    ld c,3                      ; magenta
    cp 9
    jp nz,rules_out
.swap:
    ld b,7
    call swap_colour
    jp rules_out

; ---- stage 6: the brain ----------------------------------------------------
; A tile of only the reds (dark red, red, light red) and black: the fit's
; white or grey becomes magenta, and the tile is bright.
rules_6:
    ld hl,t6_bad
    call only
    jp nz,rules_out
    call count
    ld a,(r_cnt)
    cp 64
    jp z,rules_out
    ld bc,0x0703
    call swap_colour
    ld hl,cv_out+8
    set 6,(hl)
    jp rules_out

; ---- stage 7: the formations and the band ------------------------------------
rules_7:
    call count
    ld hl,t7f_bad               ; formations: black, blues, cyan, greens
    call only
    jr nz,.band
    ld a,(r_cnt+2)
    ld hl,r_cnt+3
    add a,(hl)
    ld hl,r_cnt+12
    add a,(hl)
    jr nz,.form                 ; with green: a formation
    pop de
    push de
    ld a,d
    cp 2
    jp nc,rules_out             ; only blues: a formation's edge, in thirds 0-1
    ld a,(r_cnt+7)
    or a
    jp nz,rules_out             ; (cyan without green: the lattice)
    ld a,(r_cnt+4)
    ld hl,r_cnt+5
    add a,(hl)
    jp z,rules_out
.form:
    ld a,(r_cnt)
    cp 25
    jr c,.body
    ld hl,t_nonzero             ; mostly black: bright blue on black
    ld de,r_m1
    call rowmask
    ld a,0x41
    ld hl,r_m1
    jp put
.body:
    ld hl,t7_dots               ; greens and cyan: bright green dots on bright blue
    ld de,r_m1
    call rowmask
    ld a,0x4C
    ld hl,r_m1
    jp put
.band:
    ld hl,t_pipe_bad            ; the band: black, blues, cyan, grey, white
    call only
    jp nz,rules_out
    ld a,(r_cnt+4)
    cp 4
    jp c,rules_out
    ld a,(r_cnt+14)
    ld hl,r_cnt+15
    add a,(hl)
    jp z,rules_out
    ld hl,t_light               ; cyan, grey, white: white
    ld de,r_m1
    call rowmask
    ld a,(r_cnt)
    cp 25
    jr c,.rim
    ld a,0x07                   ; mostly black: white on black
    ld hl,r_m1
    jp put
.rim:
    ld hl,t_nonzero             ; and a black pixel above or below a coloured one
    ld de,r_m2
    call rowmask
    ld hl,r_m2
    ld de,r_m1
    ld b,8
    ld c,0                      ; the line above (none for the first)
.r:
    ld a,b
    cp 1
    ld a,0
    jr z,.last
    inc hl
    ld a,(hl)                   ; the line below
    dec hl
.last:
    or c
    ld c,a
    ld a,(hl)
    cpl                         ; black pixels of this line
    and c
    ex de,hl
    or (hl)
    ld (hl),a
    ex de,hl
    ld c,(hl)                   ; this line: the next one's line above
    inc hl
    inc de
    djnz .r
    ld a,0x0F                   ; white on blue
    ld hl,r_m1
    jp put

; ---- stage 8: the pipes, the ladders and the brain --------------------------
rules_8:
    call count
    ld hl,t_pipe_bad
    call only
    jr nz,.brain
    ld a,(r_cnt)
    cp 64
    jp z,rules_out
    ld a,(r_cnt+4)
    or a
    jp z,rules_out
    pop de
    push de
    ld a,e
    cp 0x58
    jr nz,.pipe
    ld hl,t_nonzero             ; the ladder: bright white on black
    ld de,r_m1
    call rowmask
    ld a,0x47
    ld hl,r_m1
    jp put
.pipe:
    ld hl,t_light               ; a line with 4 or more cyan, grey or white
    ld de,r_m1                  ; pixels: the body of a pipe
    call rowmask
    ld hl,r_m1
    ld b,8
.body:
    ld a,(hl)
    ld c,0
.bit:
    add a,a
    jr nc,.nb
    inc c
.nb:
    or a
    jr nz,.bit
    ld a,c
    cp 4
    jr nc,.is_body
    inc hl
    djnz .body
    ld hl,t_nonzero             ; not a body: bright blue on black
    ld de,r_m1
    call rowmask
    ld a,0x41
    ld hl,r_m1
    jp put
.is_body:
    ld hl,t_5                   ; light blue stippled, white on bright blue
    ld de,r_m2
    call rowmask
    call stip_in
    ld a,0x4F
    ld hl,r_m1
    jp put
.brain:
    ld hl,t8b_bad               ; the brain: black, dark red, light red, yellows
    call only
    jp nz,rules_out
    ld a,(r_cnt+6)
    or a
    jp z,rules_out
    ld a,(cv_out+8)             ; only where the fit chose red or yellow
    ld b,a
    and 7
    cp 2
    jr z,.recol
    cp 6
    jr z,.recol
    ld a,b
    rrca
    rrca
    rrca
    and 7
    cp 2
    jr z,.recol
    cp 6
    jp nz,rules_out
.recol:
    ld bc,0x0703                ; white: magenta (inside)
    call swap_colour
    ld bc,0x0602                ; yellow: red
    call swap_colour
    ld hl,cv_out+8
    set 6,(hl)
    jp rules_out

; ---- tables and work space ---------------------------------------------------
    align 16
t_none:     db 0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0
t_nonzero:  db 0,0xFF,0xFF,0xFF, 0xFF,0xFF,0xFF,0xFF, 0xFF,0xFF,0xFF,0xFF, 0xFF,0xFF,0xFF,0xFF
t_e_f:      db 0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0xFF,0xFF
t_4_5:      db 0,0,0,0, 0xFF,0xFF,0,0, 0,0,0,0, 0,0,0,0
t_5:        db 0,0,0,0, 0,0xFF,0,0, 0,0,0,0, 0,0,0,0
t_light:    db 0,0,0,0, 0,0,0,0xFF, 0,0,0,0, 0,0,0xFF,0xFF
t7_dots:    db 0,0,0xFF,0xFF, 0,0,0,0xFF, 0,0,0,0, 0xFF,0,0,0
t2_bad:     db 0,0xFF,0xFF,0xFF, 0,0,0xFF,0xFF, 0xFF,0xFF,0xFF,0xFF, 0xFF,0xFF,0,0
t6_bad:     db 0,0xFF,0xFF,0xFF, 0xFF,0xFF,0,0xFF, 0,0,0xFF,0xFF, 0xFF,0xFF,0xFF,0xFF
t7f_bad:    db 0,0xFF,0,0, 0,0,0xFF,0, 0xFF,0xFF,0xFF,0xFF, 0,0xFF,0xFF,0xFF
t_pipe_bad: db 0,0xFF,0xFF,0xFF, 0,0,0xFF,0, 0xFF,0xFF,0xFF,0xFF, 0xFF,0xFF,0,0
t10_bad:    db 0,0xFF,0xFF,0xFF, 0xFF,0xFF,0xFF,0xFF, 0xFF,0xFF,0,0, 0xFF,0xFF,0xFF,0xFF
t8b_bad:    db 0,0xFF,0xFF,0xFF, 0xFF,0xFF,0,0xFF, 0xFF,0,0,0, 0xFF,0xFF,0xFF,0xFF
r_cnt:      ds 16
t2_attr:    db 0x05,0x47,0x05,0x47,0x05,0x05,0x47     ; 45-4B
    assert (t2_attr >> 8) == ((t2_attr + 6) >> 8)
r_tab:      dw 0
r_idx:      db 0
r_t:        ds 2
r_or:       db 0
r_m1:       ds 8
r_m2:       ds 8
r_m3:       ds 8
