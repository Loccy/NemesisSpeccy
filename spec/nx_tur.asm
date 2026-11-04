; Spectrum Next only: stage 5's turrets and skeletons, drawn smooth, and in
; every stage the shots and the laser over the scenery (tu_shots).  Its own
; 8K page (LO_TURP, nx_l2.asm; packed by nx_pack.py), called at 6000 by
; lo_tur (bank 8) after lo_cells, with the page at 6000-7FFF (MMU3), the
; screen being drawn's Layer 2 banks in lo_l2bank, and MMU2 free.  Assembled
; after nx_low.asm, with its symbols (nx_lsyms.inc, from nx_low.sym).
;
; Two kinds of Konami's stage 5 scenery move a character row a step; they
; are drawn again here a pixel step at a time.  Each is a rectangle of
; Konami's characters that slides out of the floor, a ceiling or a ledge,
; Konami drawing only the rows that are out.  It is shown as Konami has it
; in its map (name_shadow, the blocks from the character pool) moved back by
; what is left of the step, inside its rectangle (and, a turret sliding on,
; the row it has just left, if Konami has left it blank): the rectangle is
; cleared first and its cells marked to be drawn again from the names
; (dirty_cell, both screens), so it never shows where Konami has not put
; it.  With the pool for the whole stage only (lo_pool 1).
;
; The turrets (Konami's four of E880, 8 bytes: type, 1 rising, 2 coming
; down; step, 0 coming out, 1 sliding on, 2 and 3 out; row and column, in
; pixels; ticks to the next step; rows out less one): 4 x 4 characters out of
; a pool, a step every 5 ticks (3:B145; 3:B431 draws them: coming out, a
; type 1 its drawing's top rows at its row, which rises, a type 2 its bottom
; ones at its row, which stays), so back by 8, 6, 5, 3, 2 pixels with 5-1
; ticks to go.
;
; The skeletons (the small pieces of E700, 8 bytes: type 1-4, 5 on the big
; pieces; step, 0 coming out; row and column; ticks to the next step): 5 x 5
; characters, a type 1 rising out of the floor, 3 and 4 coming down (2 is
; not in the stage); Konami's next drawing every 8 ticks is the same
; skeleton a row further out (3:B2DA, 3:B3EA, the drawings at 3:B537), so
; back by 8-1 pixels; the last step, which Konami makes as it is out and no
; longer counts, is counted here.  Its open mouth, out, is Konami's.

    device zxspectrumnext
    include "nx_lsyms.inc"
K           equ 0x3100          ; Konami's RAM, E000 on, at AF00
MAPK_K      equ 0xED00-K        ; Konami's map (rows of 32)

    org 0x6000
tu_main:
    ld a,(lo_pool)
    dec a
    ret nz
    call tu_shchars
    ld a,0xFF                   ; no shot's look kept
    ld (tu_lkey),a
    ld hl,tu_pm                 ; no cells drawn here yet
    ld b,88
.c:
    ld (hl),0
    inc hl
    djnz .c
    ld a,(0xE061-K)             ; stage 5: its turrets and skeletons
    cp 5
    call z,tu_stage5
    call tu_shots               ; every stage: the shots and the laser
    db 0xED,0x91,0x52,0x0A      ; the ordinary map back at 4000
    ret
tu_stage5:
    ld ix,0xE880-K
    ld b,4
.t:
    push bc
    ld a,(ix+0)
    or a
    call nz,tu_turret
    pop bc
    ld de,8
    add ix,de
    djnz .t
    ld ix,0xE700-K
    ld hl,tu_sk
    ld b,8
.s:
    push bc
    push hl
    call tu_skel
    pop hl
    pop bc
    inc hl
    ld de,8
    add ix,de
    djnz .s
    ret

; IX a background piece, HL its tu_sk: a skeleton coming out?  Konami's
; last step comes as it is out (step 1, which does not count ticks): that
; one is counted here, a screen a tick, 8 to 1 (tu_sk, set while it comes
; out).
tu_skel:
    ld a,(ix+0)
    cp 5
    ret nc                      ; a big piece
    cp 3
    jr nc,.k                    ; 3, 4: coming down
    cp 1
    ret nz                      ; none, or 2
.k:
    ld a,(ix+1)
    or a
    jr nz,.out
    ld (hl),8
    ld a,(ix+4)                 ; coming out: 8-1 ticks to the next step
    jr .go
.out:
    ld a,(hl)                   ; out: its last step, counted here
    or a
    ret z
    dec (hl)
.go:
    ld c,a                      ; that many pixels back: rising, lower;
    ld a,(ix+0)                 ; coming down, higher
    dec a
    ld a,c
    jr z,.d
    neg
.d:
    ld (tu_d),a
    ld a,5
    call tu_cols
    ld e,40                     ; Konami's 5 x 5, all drawn over
    call tu_rows
    jp tu_paint

; A columns from IX's column on.
tu_cols:
    ld e,a
    ld a,(ix+3)
    rrca
    rrca
    rrca
    and 31
    ld (tu_c0),a
    add a,e
    ld (tu_ce),a
    ret

; Konami's lines and the lines drawn: from IX's row, E of them.
tu_rows:
    ld a,(ix+2)
    ld (tu_s0),a
    ld (tu_a0),a
    add a,e
    ld (tu_s1),a
    ld (tu_a1),a
    ret

; IX a turret.
tu_turret:
    ld a,(ix+1)                 ; C: coming out (0) or sliding on (1)
    cp 2
    ret nc
    ld c,a
    ld a,(ix+4)                 ; T, 1-5 ticks to the next step: back by
    ld e,a                      ; T + (T + 1) / 2 = 2, 3, 5, 6, 8 pixels,
    inc a                       ; lower rising, higher coming down
    srl a
    add a,e
    bit 0,(ix+0)
    jr nz,.l
    neg
.l:
    ld (tu_d),a
    ld a,4
    call tu_cols
    ld e,32                     ; E: 8 * the rows Konami draws
    dec c
    jr z,.n
    ld a,(ix+5)
    cp 3
    ret nc
    inc a
    add a,a
    add a,a
    add a,a
    ld e,a
.n:
    call tu_rows
    inc c
    jr z,tu_paint               ; coming out: Konami's lines only
    bit 0,(ix+0)                ; sliding on: and the row it has left, if
    jr z,.dn                    ; blank (not yet, at first: the floor, the
    ld a,(tu_a1)                ; ceiling)
    call tu_blank4
    jr nz,tu_paint
    ld hl,tu_a1
    ld a,(hl)
    add a,8
    ld (hl),a
    jr tu_paint
.dn:
    ld a,(ix+2)
    sub 8
    jr c,tu_paint
    ld b,a
    call tu_blank4
    jr nz,tu_paint
    ld a,b
    ld (tu_a0),a
    ; on into tu_paint

; Lines A0 to A1 - 1, columns C0 to CE - 1: line Y as Konami's line Y - shift
; if that is one of S0 to S1 - 1, blank if not; then their cells marked.
tu_paint:
    ld a,0xFF
    ld (tu_key),a
    ld a,(tu_a0)
.line:
    ld (tu_y),a
    rlca
    rlca
    and 3
    ld b,a                      ; its third: MMU6/7
    ld a,(lo_l2bank)
    add a,b
    add a,a
    db 0xED,0x92,0x56
    inc a
    db 0xED,0x92,0x57
    ld a,(tu_y)
    ld hl,tu_d
    sub (hl)                    ; Konami's line
    ld hl,tu_s0
    cp (hl)
    jr c,.bk                    ; above S0
    inc hl
    cp (hl)                     ; below S1: Konami's
    jr c,.in
.bk:
    ld hl,tu_zero               ; not one of them: blank
    jr .bl
.in:
    ld c,a
    and 7
    add a,a
    add a,a
    add a,a
    ld (tu_ln),a
    ld a,c
    and 0xF8
    ld hl,tu_key
    cp (hl)
    call nz,tu_fetch
    ld hl,tu_blk
.bl:
    ld a,(tu_c0)
    ld c,a                      ; C: the column, HL its block (page, number)
.k:
    ld a,c
    cp 32
    jr nc,.kn                   ; past the right edge
    push hl
    ld a,(lo_org)
    add a,c
    and 31
    add a,a
    add a,a
    add a,a
    ld e,a                      ; DE: its 8 pixels (D afresh: LDIR in Layer
    ld a,(tu_y)                 ; 2's column 31 carries into it)
    and 63
    add a,0xC0
    ld d,a
    ld a,(hl)
    or a
    jr z,.kz
    db 0xED,0x92,0x52           ; the block's page at 4000
    inc l
    ld a,(hl)                   ; 4000 + (number & 7F) * 64 + line * 8
    rrca
    rrca
    ld h,a
    and 0xC0
    ld l,a
    ld a,(tu_ln)
    or l
    ld l,a
    ld a,h
    and 0x1F
    or 0x40
    ld h,a
    push bc
    ld bc,8
    ldir
    pop bc
    jr .kp
.kz:
    xor a
    ld b,8
.kzl:
    ld (de),a
    inc e
    djnz .kzl
.kp:
    pop hl
.kn:
    inc l
    inc l
    inc c
    ld a,(tu_ce)
    cp c
    jr nz,.k
    ld a,(tu_y)
    inc a
    ld hl,tu_a1
    cp (hl)
    jp c,.line
    ld a,(tu_a0)                ; every cell of rows A0-A1, columns C0-CE
    and 0xF8
.mr:
    ld (tu_y),a
    ld l,a                      ; HL: the cell's place in name_shadow
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(tu_c0)
    ld e,a
    add a,l
    ld l,a
.mk:
    ld a,e
    cp 32
    jr nc,.mn                   ; past the right edge
    ld b,h
    ld c,l
    call dirty_cell
    call tu_pset
.mn:
    inc e
    inc l
    ld a,(tu_ce)
    cp e
    jr nz,.mk
    ld a,(tu_y)
    add a,8
    ld hl,tu_a1
    cp (hl)
    jr c,.mr
    ret

; Konami's source row at line A (a multiple of 8): its five blocks from the
; pool at tu_blk (page, or 0: none, then number).
tu_fetch:
    ld (tu_key),a
    ld l,a                      ; HL: name_shadow + row * 32 + C0
    ld h,(name_shadow>>8)/4
    add hl,hl
    add hl,hl
    ld a,(tu_c0)
    add a,l
    ld l,a
    ld a,h
    sub name_shadow>>8
    ld b,a                      ; B: its third
    ld de,tu_blk
.f:
    ld a,(hl)
    call tu_under
    push hl
    ld c,a
    push de
    call lo_cmap                ; Z: A its block's page, C its number
    pop de
    jr z,.fy
    xor a                       ; none (character 00 among them): blank
.fy:
    ld (de),a
    inc e
    ld a,c
    ld (de),a
    inc e
    pop hl
    inc hl
    ld a,e
    cp (tu_blk+10)&0xff
    jr nz,.f
    ret

; Z if the four names of the row at line A (a multiple of 8), C0 on, are 00.
tu_blank4:
    ld l,a
    ld h,(name_shadow>>8)/4
    add hl,hl
    add hl,hl
    ld a,(tu_c0)
    add a,l
    ld l,a
    ld a,(hl)
    inc l
    or (hl)
    inc l
    or (hl)
    inc l
    or (hl)
    ret

; Konami's shots (E260, six of 16 bytes: type, 1 a shot, 3 the laser; byte 6
; its character; a shot's X and Y at bytes 3 and 5 and the character it
; covers at byte 8; the laser's cells, byte 12 of them from its map address
; at bytes 14-15, and the characters it covers from byte 17 on).  Konami
; writes them into its map and the screen over what it keeps: their own
; cells, as the MSX has them, are a black 8 x 8 with the shot through it.
; What was under one is what Konami kept (its map, by the time the Next draws
; a screen, no longer has stage 5's turrets and skeletons), but an enemy
; Konami draws with characters, which the Next shows as a sprite with the
; scenery under it, gives way to that scenery (Konami's map).

; The characters of the shots there are now, at tu_shc (0: none).
tu_shchars:
    ld ix,0xE260-K
    ld hl,tu_shc
    ld b,6
.s:
    ld a,(ix+0)
    cp 1
    jr z,.y
    cp 3
    ld a,0
    jr nz,.n
.y:
    ld a,(ix+6)
.n:
    ld (hl),a
    inc hl
    ld de,16
    add ix,de
    djnz .s
    ret

; A, the character at HL in name_shadow: if it is a shot's (at that cell),
; what was under it (tu_find).  Preserves BC, DE, HL.
tu_under:
    or a
    ret z
    push bc
    push hl
    ld hl,tu_shc
    ld b,6
.c:
    cp (hl)
    jr z,.m
    inc hl
    djnz .c
    pop hl
    pop bc
    ret
.m:
    pop hl
    push hl
    push af
    ld bc,-name_shadow
    add hl,bc
    call tu_find
    jr c,.f
    pop af                      ; no shot there: the character as it is
    pop hl
    pop bc
    ret
.f:
    pop bc                      ; (the old A)
    pop hl
    pop bc
    ret

; HL: a cell (row * 32 + column).  Carry and A: what Konami saved under a
; shot there; no carry: no shot there.
; Preserves BC, DE, HL, IX.
tu_find:
    push bc
    push de
    push ix
    ld ix,0xE260-K
    ld b,6
.s:
    ld a,(ix+0)
    cp 3
    jr z,.las
    cp 1
    jr nz,.nx
    push hl                     ; a shot: its cell, Y / 8 * 32 + X / 8
    ld a,(ix+5)
    and 0xF8
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(ix+3)
    rrca
    rrca
    rrca
    and 31
    add a,l
    ld l,a
    ex de,hl
    pop hl
    ld a,l
    cp e
    jr nz,.nx
    ld a,h
    cp d
    jr nz,.nx
    ld a,(ix+8)                 ; what it saved
    jr .got
.las:
    ld a,(ix+12)                ; the laser: cells from its map address
    or a
    jr z,.nx
    ld c,a
    push hl
    ld e,(ix+14)
    ld d,(ix+15)
    or a
    sbc hl,de
    ld de,MAPK_K
    add hl,de                   ; its cell's place in the strip
    ld a,h
    or a
    jr nz,.ln
    ld a,l
    cp c
    jr nc,.ln
    push ix
    pop de
    add a,17                    ; the strip it saved, from byte 17
    add a,e
    ld e,a
    jr nc,.lc
    inc d
.lc:
    ld a,(de)
    pop hl
    jr .got
.ln:
    pop hl
.nx:
    ld de,16
    add ix,de
    djnz .s
    pop ix
    pop de
    pop bc
    or a                        ; no carry: none
    ret
.got:
    pop ix
    pop de
    pop bc
    scf
    ret

; Every cell of every shot: drawn again over what is under it (Konami's map),
; the shot's character's lit lines as they are, a black line above and below
; them, and the rest as what is under it.  Cells with nothing under them are
; as Konami has them already.
tu_shots:
    ld ix,0xE260-K
    ld b,6
.s:
    push bc
    ld a,(ix+0)
    cp 1
    jr z,.shot
    cp 3
    jr nz,.nx
    ld b,(ix+12)                ; the laser: B cells from its map address
    ld a,b
    or a
    jr z,.nx
    ld l,(ix+14)
    ld h,(ix+15)
    ld de,-MAPK_K
    add hl,de
.lc:
    push bc
    push hl
    call tu_ovl
    pop hl
    pop bc
    inc hl
    djnz .lc
    jr .nx
.shot:
    ld a,(ix+5)                 ; its cell: Y / 8 * 32 + X / 8
    and 0xF8
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(ix+3)
    rrca
    rrca
    rrca
    and 31
    add a,l
    ld l,a
    call tu_ovl
.nx:
    pop bc
    ld de,16
    add ix,de
    djnz .s
    ret

; The shot's cell at offset HL (row * 32 + column), character (IX+6): what
; is under it drawn as lo_cells draws a cell (lo_tcell: the pool, or the
; copies), or, a cell tu_paint drew this screen, as it is; then the shot's
; lit lines over it as lo_cells draws the shot's character, with a black
; line above and below them.
tu_ovl:
    ld a,h
    cp 2
    jr c,.in
    ret nz
    ld a,l
    cp 0xC0
    ret nc                      ; rows 0-21 only
.in:
    ld (tu_off),hl
    ld de,name_shadow
    add hl,de
    ld (tu_nsp),hl
    ld a,(hl)
    cp (ix+6)
    ret nz                      ; not showing the shot
    ld hl,(tu_off)
    ld a,h                      ; its row
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,l
    rlca
    rlca
    rlca
    and 7
    or b
    ld (tu_row),a
    call tu_pget
    jr nz,.pt                   ; drawn here: the shot over it, whatever
    call tu_find                ; what is under it
    ret nc
    or a
    ret z                       ; nothing: as it is
    ld (tu_und),a
    jr .notp
.pt:
    ld de,tu_cell               ; drawn here: as it is
    call tu_rdcell
    call tu_shotlook
    jr .mix
.notp:
    call tu_shotlook            ; (draws the shot's character in the cell)
    ld hl,(tu_nsp)              ; what is under it, drawn as any cell
    ld a,(tu_und)
    ld (hl),a
    call tu_drawcell
    ld hl,(tu_nsp)
    ld a,(ix+6)
    ld (hl),a                   ; the shot back in name_shadow
    ld de,tu_cell
    call tu_rdcell
.mix:
    ld hl,tu_las                ; its lit lines over tu_cell, black above
    ld de,tu_cell               ; and below them
    ld b,8
    ld c,0                      ; the line above was lit
.ln:
    push bc
    push hl
    ld b,8                      ; this line lit (other than black, 0 or 1)?
    ld c,0
.lt:
    ld a,(hl)
    and 0xFE
    or c
    ld c,a
    inc hl
    djnz .lt
    ld a,c
    pop hl
    pop bc
    or a
    jr z,.dk
    push bc                     ; lit: as it is
    ld bc,8
    push de
    ldir
    pop de
    pop bc
    ld a,e                      ; and the line above black, if it was not
    cp tu_cell&0xff             ; (and there is one)
    jr z,.lf
    bit 0,c
    jr nz,.lf
    sub 8
    push bc
    push de
    ld e,a
    call tu_zero8
    pop de
    pop bc
.lf:
    ld c,1
    jr .nl
.dk:
    bit 0,c                     ; dark: black below a lit line
    jr z,.d0
    push bc
    push de
    call tu_zero8
    pop de
    pop bc
.d0:
    ld c,0
    ld a,l
    add a,8
    ld l,a
.nl:
    ld a,e
    add a,8
    ld e,a
    djnz .ln
    call tu_l2adr               ; tu_cell into Layer 2
    ld hl,tu_cell
    ld b,8
.w:
    push bc
    push de
    ld bc,8
    ldir
    pop de
    pop bc
    inc d
    djnz .w
    ret

; The shot's character (IX+6) as lo_cells draws it in this cell, at tu_las:
; drawn there (name_shadow has it) and read back, once a row and character.
tu_shotlook:
    ld a,(tu_row)
    ld c,(ix+6)
    ld hl,tu_lkey
    cp (hl)
    jr nz,.mk
    inc hl
    ld a,c
    cp (hl)
    ret z
.mk:
    ld a,(tu_row)
    ld (tu_lkey),a
    ld a,c
    ld (tu_lkey+1),a
    call tu_drawcell
    ld de,tu_las
    jp tu_rdcell

; Cell tu_off (row tu_row) drawn as lo_cells draws it, from name_shadow.
tu_drawcell:
    call tu_l2adr               ; its third at MMU6/7
    ld a,(tu_row)
    ld d,a
    rrca
    rrca
    rrca
    and 3
    ld (lo_third),a
    ld a,d
    and 7
    ld d,a
    ld a,(tu_off)
    and 31
    ld e,a
    push ix
    push iy
    call lo_tcell
    pop iy
    pop ix
    ret

; Cell tu_off (row tu_row) from Layer 2 to DE (64 bytes).
tu_rdcell:
    push de
    call tu_l2adr
    ex de,hl
    pop de
    ld b,8
.r:
    push bc
    push hl
    ld bc,8
    ldir
    pop hl
    pop bc
    inc h
    djnz .r
    ret

; DE: the cell tu_off (row tu_row) in Layer 2, its third at MMU6/7.
tu_l2adr:
    ld a,(tu_row)
    rrca
    rrca
    rrca
    and 3
    ld b,a
    ld a,(lo_l2bank)
    add a,b
    add a,a
    db 0xED,0x92,0x56
    inc a
    db 0xED,0x92,0x57
    ld a,(tu_off)
    and 31
    ld b,a
    ld a,(lo_org)
    add a,b
    and 31
    add a,a
    add a,a
    add a,a
    ld e,a
    ld a,(tu_row)
    and 7
    add a,a
    add a,a
    add a,a
    add a,0xC0
    ld d,a
    ret

; The cells drawn this screen by tu_paint (tu_pm: a bit a cell, row * 4 +
; column / 8).  HL: the cell (row * 32 + column).  tu_pset sets its bit;
; tu_pget: NZ if set.  Both preserve BC, DE, HL.
tu_pset:
    push hl
    push bc
    call tu_pbit
    or (hl)
    ld (hl),a
    pop bc
    pop hl
    ret
tu_pget:
    push hl
    push bc
    call tu_pbit
    and (hl)
    pop bc
    pop hl
    ret
tu_pbit:                        ; HL: its byte, A: its bit
    ld a,l
    and 7
    ld b,a
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ld a,1
    inc b
.s:
    dec b
    jr z,.d
    add a,a
    jr .s
.d:
    push de
    ld de,tu_pm
    add hl,de
    pop de
    ret

; 8 zero bytes at DE (E only moves).
tu_zero8:
    xor a
    ld b,8
.z:
    ld (de),a
    inc e
    djnz .z
    ret

tu_d:       db 0                ; the shift (Konami's line = line - shift)
tu_s0:      db 0                ; Konami's lines, S0 to S1 - 1
tu_s1:      db 0
tu_a0:      db 0                ; the lines drawn, A0 to A1 - 1
tu_a1:      db 0
tu_c0:      db 0                ; the columns, C0 to CE - 1
tu_ce:      db 0
tu_y:       db 0                ; the line
tu_key:     db 0                ; the source row tu_blk has (its line)
tu_ln:      db 0                ; the line in the block * 8
tu_sk:      ds 8                ; per skeleton: screens of its last step to go
tu_shc:     ds 6                ; the shots' characters (0: none)
tu_pm:      ds 88               ; the cells tu_paint drew this screen
tu_off:     dw 0                ; tu_ovl: the cell (row * 32 + column),
tu_row:     db 0                ; its row,
tu_nsp:     dw 0                ; its place in name_shadow,
tu_und:     db 0                ; what is under the shot,
tu_lkey:    db 0xFF,0           ; the row and character tu_las has
    align 64
tu_las:     ds 64               ; the shot's character as drawn
    align 64
tu_cell:    ds 64               ; the cell being made
    align 16
tu_blk:     ds 10               ; five blocks: page (0: none), number
tu_zero:    ds 10               ; five blocks of none
    assert (tu_blk >> 8) == ((tu_zero + 9) >> 8)
    assert (name_shadow & 0x3FF) == 0
tu_end:
    assert tu_end <= 0x8000
    savebin "nx_tur.bin", 0x6000, tu_end - 0x6000
