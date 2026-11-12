; Spectrum Next only: stage 5's turrets and skeletons, drawn smooth, and in
; every stage the shots and the laser over the scenery (tu_shots); stage 6's
; brains (tu_btick), the ghosts of pieces leaving at the left (tu_qtick),
; stage 8's electricity (tu_s8), the ending's zoom (tu_zoom) and the Big
; Core in the arcade's drawing (tu_bc, tu_bcq).  Its own
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

TB          equ 0x7600          ; stage 6's tables (nx_pack.py stage6_tables, TB6)
TB_PAT      equ TB              ; our 13 patterns (nx_art.STAGE6)
TB_BRW      equ TB+0x680        ; the five brain drawings' sizes (W, H)
TB_BRS      equ TB+0x690        ; and sprites: n, then (X, Y, pattern) x 4
TB_CHW      equ TB+0x6E0        ; the 40 chain drawings' sizes
TB_CHB      equ TB+0x730        ; and balls: (X, Y) x 7, from the brain's end
NB6         equ 13
NSL         equ 6               ; ticks a chain's balls take to new places
NB6S        equ 72              ; sprites at most: two brains, 4 + 14 each,
                                ; and their ghosts
QRS         equ 10              ; a piece's record (tu_qtick)

    org 0x6000
    jp tu_main                  ; lo_tur
    jp tu_btick                 ; lo_brain
    jp tu_bspr                  ; lo_bspr
    jp tu_qtick                 ; lo_qgh
    jp tu_bc                    ; lo_bart
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
; its character; a shot's Y and X at bytes 3 and 5 (0:571B makes its map
; address from them: 3:A299; until 8 November taken the other way round, so
; no ordinary shot was found and each kept its black box) and the character it
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
    ld a,(ix+3)                 ; (Y at byte 3, X at byte 5: Konami's 0:571B)
    and 0xF8
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(ix+5)
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
    ld a,(ix+3)                 ; its cell: Y / 8 * 32 + X / 8 (Y at byte 3,
    and 0xF8                    ; X at byte 5)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(ix+5)
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


; Stage 6's brains (Konami's boss 2; its step 1:7F74, its drawing 2:8290):
; two brains, at E790 and E7C0 (type 3), each with up to two chains of seven
; balls, above it at +10h and below at +20h (type 4; 2:8308 places them
; from the brain).  Konami draws them with characters (bank 10, tables AAA6
; and AAB0, by byte 6) at the cell of their position (Y byte 3, X byte 5).
; A brain moves only in steps: every 10 ticks (byte 8 counts them) 8 to the
; left and 8 up or down towards the ship (2:8144); a chain aims at the ship,
; Konami picking the next drawing every 5 to 8 ticks (2:8113, 2:81D5).  Here
; (from lo_tick, lo_brain) their characters are taken out of name_shadow,
; the background (Konami's map, which no longer has them) put back, and they
; are shown as sprites (lo_qspr, lo_bspr): a brain as far towards its next
; step left as its count has come, and its rise or fall gliding over the
; ten ticks after the step that made it; each ball as far from its place in
; the old drawing to its place in the new as NSL ticks have come, relative
; to the brain shown.  Our patterns (BPAT on, the Big Core's, which is never
; on screen with them) are sent once a boss (LO_QOK).  With the pool only.
tu_btick:
    xor a
    ld (tu_bn),a
    ld a,(lo_pool)
    dec a
    ret nz
    ld a,(LO_QOK)
    or a
    call z,tu_bmake
    ld hl,tu_bs
    ld (tu_bsp),hl
    ld ix,0xE790-K
    ld iy,tu_bst0
    call tu_brain
    ld ix,0xE7C0-K
    ld iy,tu_bst1
    call tu_brain
    ld iy,tu_gh0
    call tu_ghost
    ld iy,tu_gh1
    call tu_ghost
    ld a,(tu_bn)
    ld (LO_QN),a
    ret

; A new boss: its states cleared, our patterns sent as lo_qmake sends its
; (the Big Core's made again when it is next shown).
tu_bmake:
    ld hl,tu_bst0
    ld de,tu_bst0+1
    ld bc,4*BST-1
    ld (hl),0
    ldir
    ld hl,lo_bkey
    ld de,lo_bkey+1
    ld bc,24*5-1
    ld (hl),0xFF
    ldir
    ld hl,TB_PAT
    ld a,BPAT
.p:
    ld (lo_bsend),a
.s:
    push hl
    xor a
    ld (lo_brst),a
    ld a,(lo_bsend)
    call lo_psend
    ld a,(lo_brst)
    or a
    jr z,.ok
    pop hl                      ; sent over by the interrupt: again
    jr .s
.ok:
    pop af
    ld a,(lo_bsend)
    inc a
    cp BPAT+NB6
    jr nz,.p
    ld a,1
    ld (LO_QOK),a
    ret

; IX a brain's slot, IY its state (BST bytes: on (2: gliding off), Konami's X
; last tick, the Y it glides from and to, the X and Y shown, the ticks to the
; next step gliding off, its drawing; then its two chains', CST each).
tu_brain:
    ld a,(ix+0)
    cp 3
    jr z,.on
    ld a,(iy+0)                 ; gone: at the left edge (Konami takes it off
    dec a                       ; as its step would take X below 10h, 2:8169),
    jr nz,.off                  ; it glides on off the screen as a ghost (a
    or (ix+0)                   ; copy, BST bytes on: tu_ghost), not if shot
    jr nz,.off                  ; (the slot an explosion)
    ld a,(iy+1)
    cp 0x18
    jr nc,.off
    push iy
    pop hl
    ld de,2*BST
    add hl,de
    ex de,hl
    push iy
    pop hl
    ld bc,BST
    push de
    ldir
    pop hl
    ld (hl),2                   ; gliding: from X 8, the step's start
    inc hl
    ld (hl),8
    ld de,5
    add hl,de
    ld (hl),11
.off:
    xor a
    ld (iy+0),a
    ld (iy+8),a
    ld (iy+8+CST),a
    ret
.on:
    ld a,(ix+5)
    ld (tu_kx),a
    ld a,(ix+3)
    ld (tu_ky),a
    ld a,(iy+0)
    or a
    jr nz,.was
    inc (iy+0)
    ld a,(ix+5)
    ld (iy+1),a
    ld a,(ix+3)
    ld (iy+2),a
    ld (iy+3),a
.was:
    ld a,(ix+5)
    cp (iy+1)
    jr z,.same
    ld (iy+1),a                 ; a step: the rise or fall from where it was
    ld a,(iy+3)                 ; going
    ld (iy+2),a
    ld a,(ix+3)
    ld (iy+3),a
    jr .fr
.same:
    ld a,(ix+3)                 ; moved without a step: there at once
    cp (iy+3)
    jr z,.fr
    ld (iy+2),a
    ld (iy+3),a
.fr:
    ld a,10                     ; through the step: 10 - byte 8 (0-9)
    sub (ix+8)
    jr nc,.f1
    xor a
.f1:
    cp 10
    jr c,.f2
    ld a,9
.f2:
    ld (tu_fr),a
    ld c,a                      ; X shown: towards X - 8, frac / 10 of the way
    ld e,10
    ld a,(ix+5)
    ld b,a
    sub 8
    ld d,a
    ld a,b
    call tu_lerp
    ld (iy+4),a
    ld (tu_dx),a
    ld a,(tu_fr)                ; Y shown: (frac + 1) / 10 of the way
    inc a
    ld c,a
    ld e,10
    ld d,(iy+3)
    ld a,(iy+2)
    call tu_lerp
    ld (iy+5),a
    ld (tu_dy),a
    ld a,(ix+6)                 ; its drawing (0-4)
    cp 5
    jr c,.d
    ld a,4
.d:
    ld (tu_bd),a
    add a,a
    ld l,a
    ld h,0
    ld de,TB_BRW
    add hl,de
    ld b,(hl)
    inc hl
    ld c,(hl)
    ld a,(ix+3)
    ld e,(ix+5)
    call tu_lift
    ld a,(tu_bd)
    ld (iy+7),a
    call tu_bsprs
    push ix                     ; the chains
    push iy
    ld bc,16
    add ix,bc
    ld bc,8
    add iy,bc
    call tu_chain
    pop iy
    pop ix
    push ix
    push iy
    ld bc,32
    add ix,bc
    ld bc,8+CST
    add iy,bc
    call tu_chain
    pop iy
    pop ix
    ret

; Brain drawing A's sprites, from the brain shown (tu_dx, tu_dy).
tu_bsprs:
    ld hl,TB_BRS                ; TB_BRS + drawing * 13
    ld de,13
    or a
    jr z,.t
.tl:
    add hl,de
    dec a
    jr nz,.tl
.t:
    ld b,(hl)
    inc hl
.sp:
    push bc
    ld c,(hl)                   ; X, Y from the brain shown, pattern
    inc hl
    ld e,(hl)
    inc hl
    ld a,(hl)
    inc hl
    push hl
    ld b,0xF0                   ; palette 15
    ld d,a
    ld a,(tu_dx)
    ld l,a
    ld a,(tu_dy)
    ld h,a
    call tu_put
    pop hl
    pop bc
    djnz .sp
    ret

; A brain Konami has taken off at the left edge (IY its ghost, a copy of its
; state, on 2; if not, nothing): its steps go on, 8 to the left every 10 ticks, glided as before; it and its
; chains (their balls where they were) shown so until they are off the
; screen.  Not Konami's any more: nothing collides with it.
tu_ghost:
    ld a,(iy+0)
    cp 2
    ret nz
    dec (iy+6)
    jr nz,.g1
    ld (iy+6),10
    ld a,(iy+1)
    sub 8
    ld (iy+1),a
.g1:
    ld a,(iy+1)                 ; past -80: gone
    cp 0x80
    jr c,.g2
    cp 0xB0
    jr nc,.g2
    xor a
    ld (iy+0),a
    ld (iy+8),a
    ld (iy+8+CST),a
    ret
.g2:
    ld a,10
    sub (iy+6)
    ld c,a
    ld e,10
    ld a,(iy+1)
    ld b,a
    sub 8
    ld d,a
    ld a,b
    call tu_lerp
    ld (tu_gadd),a              ; X shown, through tu_put (signed)
    xor a
    ld (tu_dx),a
    ld a,(iy+5)
    ld (tu_dy),a
    ld a,(iy+7)
    call tu_bsprs
    ld a,(iy+8)
    or a
    jr z,.c2
    push iy
    pop hl
    ld de,8+5+28
    add hl,de
    call tu_balls
.c2:
    ld a,(iy+8+CST)
    or a
    jr z,.c3
    push iy
    pop hl
    ld de,8+CST+5+28
    add hl,de
    call tu_balls
.c3:
    xor a
    ld (tu_gadd),a
    ret

; Stages 3 and 4: a piece Konami takes off at the left edge (bosses 1 and 6:
; 2:85C3, 2:8630 and 2:8520, its X gone below 0; boss 5: 2:8E1D, past F0h)
; clears only its slot's byte 0, X left as it went, wrapped (E0h on).  It
; goes on off the screen as a ghost, the same steps at the same rate, drawn
; as lo_qspr draws the pieces, until it is past -32.  A piece shot keeps its
; X on the screen: not ghosted.  Brain ghosts (tu_ghost) left when stage 6's
; boss ends go on here too.  From lo_pieces each tick, before it (LO_QTAB
; still last tick's); while stage 6's brains are on, tu_btick has it all.
tu_qtick:
    xor a
    ld (LO_QG),a
    ld a,(0xE151-K)
    or a
    jr z,.q
    ld a,(0xE152-K)
    cp 2
    ret z
.q:
    xor a
    ld (tu_bn),a
    ld hl,tu_bs
    ld (tu_bsp),hl
    ld iy,tu_gh0
    call tu_ghost
    ld iy,tu_gh1
    call tu_ghost
    call tu_qwatch
    ld iy,tu_qr
    ld b,8
.g:
    push bc
    ld a,(iy+3)
    or a
    call nz,tu_qg1
    ld bc,QRS
    add iy,bc
    pop bc
    djnz .g
    xor a
    ld (tu_gadd),a
    call tu_s8
    call tu_bcq
    ld a,(tu_bcon)              ; (the Big Core's core: lo_bspr too)
    ld hl,tu_bn
    or (hl)
    ld (LO_QG),a
    ret

; Stage 8's electricity (nx_pack.py S8_PAGE, mapped at 4000 here: made by
; tools/pool/art/st8_brain_make.py).  Six bolts from the brain to
; Konami's six sockets (its type 11h objects, 2:88D3), from when the brain's
; screen comes in (40 columns before the scroll stops at distance 19Fh,
; Konami's boss 4 on) and moving with it (as the scenery's sprites move,
; lo_off), each until its socket is shot (its object no longer of type 11h
; where it should be): it flickers off then.  Each flickers throughout (shown
; 5 ticks in 8, at random) and swaps its cyan and green now and then
; (palettes 14 and 15) as it arcs.  Only drawn: Konami's game is as it was.
S8_PAGE     equ 59
S8_SPR      equ 0x5000          ; the sprites: number, then bolt, X, Y, pattern
S8_SOCK     equ 0x5100          ; the sockets' objects: X, Y a bolt
S8_PAL      equ 0x5200          ; palettes 14 and 15, entries 2-15
S8_NP       equ 0x5300          ; the drawings (at 4000, 128 bytes each)
S8_FL       equ 16              ; ticks of flicker
tu_s8:
    ld a,(0xE061-K)
    cp 8
    ret nz
    ld a,0x52                   ; MMU2 as it is, put back after
    call tu_rreg
    push af
    db 0xED,0x91,0x52,S8_PAGE
    call .b
    pop af
    db 0xED,0x92,0x52
    ret
.b:
    ld a,(0xE1D0-K)             ; the ending: the Vic Viper's zoom
    dec a
    jp z,tu_zoom
    ld a,(0xE151-K)
    or a
    jp z,.off
    ld a,(0xE152-K)
    cp 4
    jp nz,.off
    ld hl,0x19F                 ; the brain's screen this many columns
    ld de,(0xE063-K)            ; to come (0-40: on its way in)
    or a
    sbc hl,de
    jp c,.off
    ld a,h
    or a
    jp nz,.off
    ld a,l
    cp 41
    jp nc,.off
    add hl,hl                   ; * 8: pixels to the right of where the
    add hl,hl                   ; scroll stops
    add hl,hl
    ld (tu_s8sh),hl
    ld a,(tu_s8ok)
    or a
    call z,tu_s8make
    ld a,(dz_on)                ; Konami's dissolve: they fade with the room
    or a
    jr z,.f0
    ld a,(lo_flv)
.f0:
    ld hl,tu_s8fv
    cp (hl)
    jr z,.f1
    ld (hl),a
    call tu_s8pal
.f1:
    ld a,(dz_on)                ; and go with the brain when the dissolve
    or a                        ; clears Konami's map (its middle character)
    jr z,.f2
    ld a,(MAPK_K+10*32+15)
    or a
    ret z
.f2:
    ld ix,tu_s8st               ; each bolt: its socket shot?
    ld hl,S8_SOCK
    ld b,6
.u:
    push bc
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    push hl
    ld hl,(tu_s8sh)             ; where its socket is now (Konami sets it
    ld a,e                      ; up at X F8h, 2:88EC: further right, still
    add a,l                     ; to come)
    ld e,a
    ld a,0
    adc a,h
    jr nz,.ok
    ld a,e
    cp 0xF8
    jr nc,.ok
    call tu_s8sock
    jr z,.ok
    ld a,(ix+0)
    or a
    jr z,.ok
    ld (ix+0),0                 ; shot: flickers off
    ld (ix+6),S8_FL
.ok:
    pop hl
    call tu_rnd                 ; now and then cyan and green swap
    and 3
    jr nz,.np
    ld a,(ix+12)
    xor 0x10
    ld (ix+12),a
.np:
    ld a,(ix+0)
    or a
    jr z,.gone
    call tu_rnd                 ; on: shown 5 ticks in 8, at random
    and 7
    cp 5
    jr nc,.hide
    jr .show
.gone:
    ld a,(ix+6)
    or a
    jr z,.hide
    dec (ix+6)                  ; going: 1 in 4
    call tu_rnd
    and 3
    jr nz,.hide
.show:
    ld a,(ix+12)
    jr .set
.hide:
    xor a
.set:
    ld (ix+18),a
    inc ix
    pop bc
    djnz .u
    ld a,(lo_off)               ; drawn with the scenery: where the scroll
    ld e,a                      ; stops, the columns still to come and the
    ld d,0                      ; smooth scroll's offset to the right
    ld hl,(tu_s8sh)
    add hl,de
    ld (tu_xw),hl
    ld iy,S8_SPR+1              ; the sprites of the bolts shown
    ld a,(S8_SPR)
    ld b,a
.s:
    push bc
    ld a,(iy+0)
    add a,tu_s8v&0xff
    ld l,a
    ld a,0
    adc a,tu_s8v>>8
    ld h,a
    ld a,(hl)
    or a
    jr z,.sk
    ld b,a
    ld l,(iy+1)
    ld h,(iy+2)
    ld d,(iy+3)
    ld c,0
    ld e,0
    call tu_put
.sk:
    ld de,4
    add iy,de
    pop bc
    djnz .s
    ld hl,0
    ld (tu_xw),hl
    ret
.off:                           ; not there: all on, to start again
    xor a
    ld (tu_s8ok),a
    ld hl,tu_s8st
    ld b,6
.z1:
    ld (hl),1
    inc hl
    djnz .z1
    ld b,6
.z2:
    ld (hl),0
    inc hl
    djnz .z2
    ld b,6
    ld a,0xE0
.z3:
    ld (hl),a
    xor 0x10
    inc hl
    djnz .z3
    ret

; Z if one of Konami's objects of type 11h (a socket) is at X E (to 4 either
; way), Y D.  Preserves BC, DE, HL, IX.
tu_s8sock:
    push ix
    push bc
    ld ix,0xE300-K
    ld b,12
.l:
    ld a,(ix+0)
    cp 0x11
    jr nz,.n
    ld a,(ix+4)
    cp d
    jr nz,.n
    ld a,(ix+6)
    sub e
    add a,4
    cp 9
    jr c,.y
.n:
    push de
    ld de,32
    add ix,de
    pop de
    djnz .l
    pop bc
    pop ix
    or 1
    ret
.y:
    pop bc
    pop ix
    xor a
    ret

; The bolts' drawings sent (patterns 104-127, then 86 on, as the Big Core's
; are, again if the interrupt sends one meanwhile) and palettes 14 and 15.
tu_s8make:
    ld hl,0x4000
    ld a,(S8_NP)
    ld b,a
    ld c,0
.p:
    push bc
    ld a,c
    cp 24
    jr c,.lo
    sub 24+104-86
.lo:
    add a,104
    ld (lo_bsend),a
.r:
    push hl
    xor a
    ld (lo_brst),a
    ld a,(lo_bsend)
    call lo_psend
    ld a,(lo_brst)
    or a
    jr z,.ok
    pop hl
    jr .r
.ok:
    pop af
    pop bc
    inc c
    djnz .p
    ld a,1
    ld (tu_s8ok),a
    xor a
    ld (tu_s8fv),a

; Palettes 14 and 15 for the dissolve's step A (0: as they are), each
; channel through LO_FMAP, as Konami's dissolve fades the room (lo_fadestep).
tu_s8pal:
    ld (tu_s8f),a
    ld a,i
    push af
    ld a,0x43                   ; the palette control as it is, put back after
    call tu_rreg
    ld e,a
    db 0xED,0x91,0x43,0x20      ; sprites' first palette
    db 0xED,0x91,0x40,0xE2
    ld hl,S8_PAL
    call .w
    db 0xED,0x91,0x40,0xF2
    call .w
    ld a,e
    db 0xED,0x92,0x43
    pop af
    ret po
    ei
    ret
.w:
    ld b,14
.e:
    push bc
    push de
    ld a,(hl)                   ; RRRGGGBB, then B's low bit
    inc hl
    ld c,a
    rlca
    rlca
    rlca
    and 7
    call .dim
    rrca
    rrca
    rrca
    ld d,a                      ; R
    ld a,c
    rrca
    rrca
    and 7
    call .dim
    add a,a
    add a,a
    or d
    ld d,a                      ; G
    ld a,c
    and 3
    add a,a
    or (hl)
    inc hl
    and 7
    call .dim                   ; B
    ld e,a
    srl a
    or d
    db 0xED,0x92,0x44
    ld a,e
    and 1
    db 0xED,0x92,0x44
    pop de
    pop bc
    djnz .e
    ret
.dim:                           ; the level A at the dissolve's step (LO_FMAP), if
    push hl                     ; it is fading (tu_s8f not 0)
    push bc
    ld b,a
    ld a,(tu_s8f)
    or a
    ld a,b
    jr z,.dz
    ld hl,LO_FMAP
    add a,l
    ld l,a
    ld a,(hl)
.dz:
    pop bc
    pop hl
    ret

; The Big Core in the arcade's drawing (nx_pack.py BC_PAGE, mapped at 4000
; here: made by tools/arcade/bigcore_make.py).  Its 24 blocks are made
; here in place of lo_bconv's (lo_bpats, through lo_bart, when a block's
; characters change): the arcade's, the wall blocks (6, 7, 12, 13) as many
; walls as Konami's life / 4 (E789: its own walls change with it, 1:7E91);
; palette 15.  The core is a sprite of its own (tu_bspr; pattern BC_PAT,
; palette 14): grey when it comes, bluer every two hits, none once the core
; has gone (E155, or face 2 in E786).  Palettes 14 and 15 are the arcade's
; while the Big Core is there, and the stage's again after (lo_pal1415).
BC_PAGE     equ 82
BC_CORES    equ 0x4000+44*128   ; the five cores
BC_PAL      equ 0x5900          ; palettes 14 and 15, entries 2-15
BC_PAT      equ 86              ; the core's pattern
BC_CX       equ 36              ; the core's place in the boss
BC_CY       equ 24
tu_bc:
    ld (tu_bcb),a
    ld c,a
    add a,BPAT
    ld (lo_bsend),a
    ld b,0
    ld hl,.idx
    add hl,bc
    ld a,(hl)                   ; its drawing, or (80h on) a wall block's
    bit 7,a
    jr z,.t
    and 0x7F
    ld e,a
    ld a,(0xE789-K)             ; walls 0-5: Konami's life / 4
    rrca
    rrca
    and 0x3F
    cp 6
    jr c,.w
    ld a,5
.w:
    add a,a
    add a,a
    add a,e
.t:
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,0x4000
    add hl,de
    call tu_bsend
    ld a,(tu_bcb)               ; blocks 0 and 18 (Konami's empty, ours not):
    or a                        ; marked in the key, for lo_bossspr
    jr z,.m
    cp 18
    ret nz
.m:
    ld l,a
    add a,a
    add a,a
    add a,l
    ld l,a
    ld h,0
    ld de,lo_bkey
    add hl,de
    ld (hl),0xFE
    ret
.idx:       db 0,1,2,3,4,5, 0x80+20,0x80+21, 6,7,8,9, 0x80+22,0x80+23
            db 10,11,12,13,14,15,16,17,18,19

; Next register A read (A = its value; BC = 253Bh), with interrupts left on.
; Registers are read by selecting one (port 243Bh) and reading it (253Bh); the
; interrupt selects registers too (lo_snd, nx_frame), so one coming between
; the two made the read return another register, and MMU2 put back as that
; left a wrong page at 4000-5FFF over Konami's bank 0 code (1.0N's crash in
; the second loop's stage 5 boss, 8 November 2026).  The register is noted
; in nx_sel first, and the interrupt selects it again before it returns
; (plat_spec isr), as out_page's port_now for the paging.  (6N held
; interrupts off round the pair instead; an interrupt that came then was
; lost, and the status lines took the play area's scroll: the Big Core's
; flick, 9 November.)
tu_rreg:
    ld (nx_sel),a
    ld bc,0x243B
    out (c),a
    inc b
    in a,(c)
    ret

; The drawing at HL (page BC_PAGE at 4000) to pattern lo_bsend, again if the
; interrupt sends one meanwhile.  MMU2 as it was after.
tu_bsend:
    push hl
    ld a,0x52
    call tu_rreg
    ld (tu_bcm),a
    db 0xED,0x91,0x52,BC_PAGE
    pop hl
.r:
    push hl
    xor a
    ld (lo_brst),a
    ld a,(lo_bsend)
    call lo_psend
    ld a,(lo_brst)
    or a
    jr z,.ok
    pop hl
    jr .r
.ok:
    pop hl
    ld a,(tu_bcm)
    db 0xED,0x92,0x52
    ret

; Each tick (tu_qtick): while the Big Core is there (stages 1-6, E151, E780
; 1, as lo_boss), its palettes and its core; after, the stage's palettes.
tu_bcq:
    xor a
    ld (tu_bcon),a
    ld a,(0xE061-K)
    dec a
    cp 6
    jr nc,.no
    ld a,(0xE151-K)
    or a
    jr z,.no
    ld a,(0xE780-K)
    cp 1
    jr nz,.no
    ld a,(tu_bcp)
    or a
    call z,.pal
    ld a,(0xE155-K)             ; the core gone: none
    or a
    jr nz,.none
    ld a,(0xE786-K)
    cp 2
    jr z,.none
    ld a,(0xE789-K)             ; (22 - life) / 2, 4 at most: grey to blue
    ld b,a
    ld a,22
    sub b
    jr nc,.c1
    xor a
.c1:
    srl a
    cp 5
    jr c,.c2
    ld a,4
.c2:
    ld hl,tu_bcv
    cp (hl)
    call nz,.send
    ld a,1
    ld (tu_bcon),a
    ret
.none:
    ld a,5
    ld (tu_bcv),a
    ret
.no:
    ld a,0xFF
    ld (tu_bcv),a
    ld a,(tu_bcp)
    or a
    ret z
    xor a                       ; the stage's palettes 14 and 15 again
    ld (tu_bcp),a
    call .p0
    db 0xED,0x91,0x52,LO_TAB
    call lo_pal1415
    jr .p1
.send:                          ; core A to pattern BC_PAT
    ld (hl),a
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,BC_CORES
    add hl,de
    ld a,BC_PAT
    ld (lo_bsend),a
    jp tu_bsend
.pal:                           ; the arcade's palettes 14 and 15
    ld a,1
    ld (tu_bcp),a
    call .p0
    db 0xED,0x91,0x52,BC_PAGE
    xor a
    ld (tu_s8f),a
    db 0xED,0x91,0x43,0x20
    db 0xED,0x91,0x40,0xE2
    ld hl,BC_PAL
    call tu_s8pal.w
    db 0xED,0x91,0x40,0xF2
    call tu_s8pal.w
.p1:                            ; MMU2 and the palette control as they were
    ld a,(tu_bcm)
    db 0xED,0x92,0x52
    ld a,(tu_bc43)
    db 0xED,0x92,0x43
    pop af
    ret po
    ei
    ret
.p0:                            ; (MMU2 and the palette control kept;
    pop hl                      ; interrupts as they were on the stack)
    ld a,i
    push af
    ld a,0x52
    call tu_rreg
    ld (tu_bcm),a
    ld a,0x43
    call tu_rreg
    ld (tu_bc43),a
    jp (hl)

; The ending's Vic Viper zoom (nx_pack.py VV_PAGES, mapped at 4000 here:
; made by tools/arcade/vv_zoom_make.py), in Konami's steps 4 and 5 of
; the ending (E1D1; 0:4BD8, 0:4C16): 16 sizes for Konami's 6, as sprites (palette
; 15), each size's drawings sent as it comes (to patterns 104-114 and
; 116-126 in turn, so the size shown keeps its own); Konami's drawings
; (characters A1h-EAh, rows 6-11, columns 10-21, 0:4EDA) taken out of the
; screen.  The tick of the zoom is Konami's own: its drawing (E1D9) and
; what is left of that drawing's ticks (E1D2).
VV_PAGE     equ 61
VV_PAGE2    equ 63
VV_TAB      equ 0x4000          ; the size for each tick
VV_FR       equ 0x40C0          ; each size: first drawing, number
VV_PAL      equ 0x40E0          ; palette 15, entries 2-15
VV_POS      equ 0x4100          ; each drawing's X, Y
tu_zoom:
    ld a,(0xE1D1-K)
    cp 4
    jr z,.s4
    cp 5
    jr z,.s5
    ld a,0xFF                   ; not zooming
    ld (tu_zf),a
    ret
.s5:
    ld a,176                    ; step 5: the last 32 ticks (E1D2 from 20h down)
    ld hl,0xE1D2-K
    sub (hl)
    cp 176
    jr c,.t
    ld a,175
    jr .t
.s4:
    ld a,(0xE1D9-K)             ; step 4: drawing E1D9's start and length
    cp 6
    jr c,.s6
    ld a,5
.s6:
    ld e,a
    ld d,0
    ld hl,.st
    add hl,de
    ld b,(hl)
    ld hl,.du
    add hl,de
    ld a,(hl)
    ld hl,0xE1D2-K
    sub (hl)
    jr nc,.s7
    xor a
.s7:
    add a,b
.t:
    ld e,a                      ; the tick: the size
    ld d,0
    db 0xED,0x91,0x52,VV_PAGE
    ld hl,VV_TAB
    add hl,de
    ld a,(hl)
    ld hl,tu_zf
    cp (hl)
    call nz,tu_znew
    ld hl,name_shadow+6*32+10   ; Konami's drawing out of the screen
    ld c,6
.kr:
    ld b,12
.kc:
    ld a,(hl)
    cp 0xA1
    jr c,.kn
    cp 0xEB
    jr nc,.kn
    ld (hl),0
    push bc
    push hl
    ld de,-name_shadow
    add hl,de
    ld b,h
    ld c,l
    call dirty_cell
    pop hl
    pop bc
.kn:
    inc hl
    djnz .kc
    ld de,20
    add hl,de
    dec c
    jr nz,.kr
    ld a,(tu_zf)                ; the size's sprites
    add a,a
    ld e,a
    ld d,0
    ld hl,VV_FR
    add hl,de
    ld a,(hl)                   ; its first drawing
    inc hl
    ld b,(hl)
    ld e,a
    ld d,0
    ld iy,VV_POS
    add iy,de
    add iy,de
    ld a,(tu_zset)              ; the patterns it was sent to
    sub BPAT
    ld d,a
.sp:
    push bc
    push de
    ld l,(iy+0)
    ld h,(iy+1)
    ld b,0xF0
    ld c,0
    ld e,0
    call tu_put
    pop de
    pop bc
    inc d
    inc iy
    inc iy
    djnz .sp
    ret
.st:        db 0,64,104,120,132,140
.du:        db 64,40,16,12,8,4

; A new size (A): its drawings sent to the other set of patterns; palette 15
; set for the zoom when it starts.  Page VV_PAGE at 4000 on entry and exit.
tu_znew:
    ld c,a
    ld a,(hl)                   ; (tu_zf: FFh before the first)
    ld (hl),c
    inc a
    jr nz,.pp
    push bc
    xor a
    ld (tu_s8f),a
    ld a,i
    push af
    ld a,0x43
    call tu_rreg
    ld e,a
    db 0xED,0x91,0x43,0x20
    db 0xED,0x91,0x40,0xF2
    ld hl,VV_PAL
    call tu_s8pal.w
    ld a,e
    db 0xED,0x92,0x43
    pop af
    jp po,.d1
    ei
.d1:
    pop bc
.pp:
    ld a,(tu_zset)              ; the other set
    xor 104^116
    ld (tu_zset),a
    ld (lo_bsend),a
    ld a,c
    add a,a
    ld e,a
    ld d,0
    ld hl,VV_FR
    add hl,de
    ld a,(hl)                   ; first drawing
    inc hl
    ld b,(hl)
.p:
    push bc
    push af
    cp 60                       ; drawing A: page 61 from 4200, or page 63
    jr nc,.p2
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,0x4200
    add hl,de
    jr .p3
.p2:
    sub 60
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,0x4000
    add hl,de
    db 0xED,0x91,0x52,VV_PAGE2
.p3:
.r:
    push hl
    xor a
    ld (lo_brst),a
    ld a,(lo_bsend)
    call lo_psend
    ld a,(lo_brst)
    or a
    jr z,.ok
    pop hl
    jr .r
.ok:
    pop hl
    db 0xED,0x91,0x52,VV_PAGE
    ld hl,lo_bsend
    inc (hl)
    pop af
    inc a
    pop bc
    djnz .p
    ld a,(tu_zset)              ; (lo_bsend back to the set's first)
    ld (lo_bsend),a
    ret

tu_rnd:                         ; A: the next of a shift register (x^8+x^4+x^3+x^2+1)
    ld a,(tu_rng)
    add a,a
    jr nc,.n
    xor 0x1D
.n:
    ld (tu_rng),a
    ret

; The pieces watched, a record each (QRS bytes: +0 shown last tick, +1 ticks
; since its X changed, +2 the ticks between its last two changes; its ghost:
; +3 on, +4 X, +5 Y, +6 drawing, +7 the step, +8 ticks a step, +9 the count).
; Only while lo_pieces shows them as sprites (LO_QOK 1: then LO_QTAB has
; last tick's, one an entry, in the slots' order).
tu_qwatch:
    ld a,(0xE151-K)
    or a
    jr z,.clr
    ld a,(LO_QOK)
    dec a
    jr nz,.clr
    ld a,(0xE152-K)
    ld b,8
    cp 1
    jr z,.k
    cp 5
    jr z,.k
    ld b,1
    cp 6
    jr z,.k
.clr:
    ld iy,tu_qr
    ld b,8
    ld de,QRS
.c:
    ld (iy+0),0
    add iy,de
    djnz .c
    ret
.k:
    ld ix,0xE780-K
    ld iy,tu_qr
    ld hl,LO_QTAB
.s:
    push bc
    ld a,(iy+0)
    or a
    jr nz,.was
    ld a,(ix+0)                 ; new
    or a
    jr z,.nx
    ld (iy+0),1
    ld (iy+1),0
    ld (iy+2),1
    jr .nx
.was:
    inc (iy+1)                  ; HL: its entry (X, Y, drawing) last tick
    ld a,(ix+5)
    cp (hl)
    jr z,.same
    ld a,(iy+1)
    ld (iy+2),a
    ld (iy+1),0
.same:
    ld a,(ix+0)
    or a
    jr nz,.on
    ld (iy+0),0                 ; gone
    ld a,(ix+5)
    cp 0xE0
    jr c,.on                    ; (on the screen: shot)
    ld (iy+4),a
    ld c,a
    ld a,(hl)
    sub c                       ; the step: 1 to 8
    jr z,.on
    cp 9
    jr nc,.on
    ld (iy+7),a
    ld a,(ix+3)
    ld (iy+5),a
    inc hl
    inc hl
    ld a,(hl)
    dec hl
    dec hl
    ld (iy+6),a
    ld a,(iy+2)
    or a
    jr nz,.n1
    inc a
.n1:
    ld (iy+8),a
    ld (iy+9),0
    ld (iy+3),1
.on:
    inc hl                      ; the next entry
    inc hl
    inc hl
.nx:
    ld bc,16
    add ix,bc
    ld bc,QRS
    add iy,bc
    pop bc
    djnz .s
    ret

; A piece's ghost (IY its record): a step every so many ticks; gone past -32;
; its four sprites as lo_qspr's.
tu_qg1:
    inc (iy+9)
    ld a,(iy+9)
    cp (iy+8)
    jr c,.d
    ld (iy+9),0
    ld a,(iy+4)
    sub (iy+7)
    ld (iy+4),a
.d:
    ld a,(iy+4)
    cp 0x80
    jr c,.s
    cp 0xE1
    jr nc,.s
    ld (iy+3),0
    ret
.s:
    ld (tu_gadd),a
    ld hl,lo_qpat               ; the kind's patterns, the drawing's four
    ld a,(LO_QK)
    cp 5
    jr nz,.k
    ld hl,lo_qpat5
.k:
    ld a,(iy+6)
    or a
    jr z,.k2
    ld bc,4
    add hl,bc
.k2:
    ld c,0
.q:
    push bc
    push hl
    ld a,(hl)
    sub BPAT
    ld d,a
    ld a,c                      ; X + 16 on the right, Y + 16 below
    and 1
    rrca
    rrca
    rrca
    rrca
    ld b,a
    ld a,c
    and 2
    add a,a
    add a,a
    add a,a
    ld e,a
    ld c,b
    ld b,0
    ld l,0
    ld h,(iy+5)
    call tu_put
    pop hl
    pop bc
    inc hl
    inc c
    ld a,c
    cp 4
    jr nz,.q
    ret

; IX a chain's slot, IY its state (CST bytes: on, its drawing and place from
; the brain (Konami's) as last seen, ticks into the slide, then the balls'
; places from the brain: the slide's start, its end, now; X, Y each).
tu_chain:
    ld a,(ix+0)
    cp 4
    jr z,.on
    ld (iy+0),0
    ret
.on:
    ld a,(ix+6)
    cp 40
    ret nc
    ld (tu_cd),a
    add a,a
    ld l,a
    ld h,0
    ld de,TB_CHW
    add hl,de
    ld b,(hl)
    inc hl
    ld c,(hl)
    ld a,(ix+3)
    ld e,(ix+5)
    call tu_lift
    ld a,(tu_kx)                ; its place from the brain
    ld b,a
    ld a,(ix+5)
    sub b
    ld (tu_crx),a
    ld a,(tu_ky)
    ld b,a
    ld a,(ix+3)
    sub b
    ld (tu_cry),a
    ld a,(iy+0)
    or a
    jr z,.new
    ld a,(tu_cd)
    cp (iy+1)
    jr nz,.chg
    ld a,(tu_crx)
    cp (iy+2)
    jr nz,.chg
    ld a,(tu_cry)
    cp (iy+3)
    jr nz,.chg
    ld a,(iy+4)
    cp NSL-1
    jr nc,.draw
    inc (iy+4)
    jr .draw
.new:
    ld (iy+0),1
    call tu_cto
    ld de,5                     ; the start: the end
    ld bc,5+14
    call tu_ccopy
    ld (iy+4),NSL-1
    jr .draw
.chg:
    ld de,5                     ; the start: where they are now
    ld bc,5+28
    call tu_ccopy
    call tu_cto
    ld (iy+4),0
.draw:
    push iy
    pop hl
    ld de,5
    add hl,de                   ; the starts (the ends 14 on, now 28 on)
    ld a,(iy+4)
    inc a
    ld (tu_k),a
    ld b,14
.lp:
    push bc
    push hl
    ld de,14
    add hl,de
    ld d,(hl)
    pop hl
    push hl
    ld a,(tu_k)
    ld c,a
    ld e,NSL
    ld a,(hl)
    call tu_lerp
    ld de,28
    add hl,de
    ld (hl),a
    pop hl
    inc hl
    pop bc
    djnz .lp
    push iy
    pop hl
    ld de,5+28
    add hl,de
; A chain's balls, their places from the brain at HL (X, Y each), from the
; brain shown (tu_dx, tu_dy): purple, the fourth grey-brown.
tu_balls:
    ld b,7
.bl:
    push bc
    ld a,b
    cp 4                        ; (the fourth from the brain: B = 4)
    ld a,11
    ld c,0x40                   ; palette 4
    jr nz,.pu
    ld a,12
    ld c,0xF0                   ; palette 15
.pu:
    ld d,a
    ld b,c
    ld c,(hl)                   ; X, Y from the brain shown
    inc hl
    ld e,(hl)
    inc hl
    push hl
    ld a,(tu_dx)
    ld l,a
    ld a,(tu_dy)
    ld h,a
    call tu_put
    pop hl
    pop bc
    djnz .bl
    ret
tu_cto:                          ; the key, and the balls' places in this drawing
    ld a,(tu_cd)
    ld (iy+1),a
    ld a,(tu_crx)
    ld (iy+2),a
    ld a,(tu_cry)
    ld (iy+3),a
    ld a,(tu_cd)                ; TB_CHB + drawing * 14
    ld l,a
    ld h,0
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,hl
    add hl,hl
    or a
    sbc hl,de                   ; * 14
    ld de,TB_CHB
    add hl,de
    push iy
    pop de
    push hl
    ld hl,5+14
    add hl,de
    ex de,hl                    ; DE: the ends
    pop hl
    ld b,7
.tb:
    ld a,(tu_crx)
    add a,(hl)
    ld (de),a
    inc hl
    inc de
    ld a,(tu_cry)
    add a,(hl)
    ld (de),a
    inc hl
    inc de
    djnz .tb
    ret
tu_ccopy:                        ; 14 bytes in the state from offset BC to DE
    push iy
    pop hl
    add hl,de
    ex de,hl
    push iy
    pop hl
    add hl,bc
    ld bc,14
    ldir
    ret

; A sprite: C X and E Y (signed) from L X and H Y (the brain shown), D the
; pattern (0-12), B the palette byte.  Not if past the list's end, or off the
; screen's edges.
tu_put:
    ld a,(tu_bn)
    cp NB6S
    ret nc
    ld a,d
    ld (tu_pp),a
    ld a,b
    ld (tu_ppal),a
    ld a,e
    ld (tu_pyr),a
    ld a,c                      ; X + 32, 9 bits
    ld e,l
    ld d,0
    ld l,a
    rla
    sbc a,a
    ld b,h                      ; (Y shown)
    ld h,a
    add hl,de
    ld a,(tu_gadd)              ; (a brain gliding off: its X, signed)
    ld e,a
    rla
    sbc a,a
    ld d,a
    add hl,de
    ld de,(tu_xw)               ; (stage 8's bolts: their screen's place)
    add hl,de
    ld de,32
    add hl,de
    bit 7,h
    ret nz
    ld a,h
    cp 2
    ret nc
    or a
    jr z,.xok
    ld a,l
    cp 0x40                     ; from 140h on: off the right
    ret nc
.xok:
    ex de,hl
    ld a,(tu_pyr)               ; Y + 32
    ld l,a
    rla
    sbc a,a
    ld h,a
    ld c,b
    ld b,0
    add hl,bc
    ld bc,32
    add hl,bc
    ld a,h
    or a
    ret nz
    ld c,l
    ld hl,(tu_bsp)
    ld (hl),e
    inc hl
    ld (hl),c
    inc hl
    ld a,(tu_ppal)
    or d                        ; X bit 8
    ld (hl),a
    inc hl
    ld a,(tu_pp)
    add a,BPAT
    ld c,a
    srl a
    or 0xC0                     ; visible, a fifth attribute
    ld (hl),a
    inc hl
    ld a,c
    and 1
    rrca
    rrca
    or 0x80                     ; 4-bit
    ld (hl),a
    inc hl
    ld (tu_bsp),hl
    ld hl,tu_bn
    inc (hl)
    ret

; Characters out of name_shadow: B columns, C rows from Y A, X E (pixels),
; Konami's map's in their place, the cells marked.  Rows past 21 (or wrapped
; above the top) and columns past 31 are not Konami's.
tu_lift:
    rrca
    rrca
    rrca
    and 31
    ld d,a                      ; the row
    ld a,e
    rrca
    rrca
    rrca
    and 31
    ld (tu_lc),a
.r:
    ld a,d
    cp 22
    jr nc,.rn
    push bc
    ld l,d                      ; HL = MAPK + row * 32 + column
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,(tu_lc)
    ld e,a
    add a,l
    ld l,a
    ld a,h
    add a,MAPK_K>>8
    ld h,a
.c:
    ld a,e
    cp 32
    jr nc,.ce
    push de
    ld a,(hl)
    push hl
    ld de,name_shadow-MAPK_K
    add hl,de
    cp (hl)
    jr z,.same
    ld (hl),a
    pop hl
    push bc
    ld c,l
    ld a,h
    sub MAPK_K>>8
    ld b,a
    call dirty_cell
    pop bc
    jr .cn
.same:
    pop hl
.cn:
    pop de
    inc hl
    inc e
    djnz .c
.ce:
    pop bc
.rn:
    inc d
    dec c
    jr nz,.r
    ret

; A = from + (D - from) * C / E, the difference signed, rounded towards from.
tu_lerp:
    push bc
    push hl
    ld b,a
    ld a,d
    sub b
    jr z,.z
    push af
    jp p,.p
    neg
.p:
    ld l,a                      ; HL = |difference| * C
    ld h,0
    push de
    ld d,h
    ld e,l
    ld hl,0
    ld a,c
    or a
    jr z,.m2
.m:
    add hl,de
    dec a
    jr nz,.m
.m2:
    pop de
    xor a                       ; / E
    ld (tu_q),a
.dv:
    ld a,h
    or a
    jr nz,.sb
    ld a,l
    cp e
    jr c,.dn
.sb:
    ld a,l
    sub e
    ld l,a
    jr nc,.nb
    dec h
.nb:
    ld a,(tu_q)
    inc a
    ld (tu_q),a
    jr .dv
.dn:
    pop af
    ld a,(tu_q)
    jp p,.ps
    neg
.ps:
    add a,b
    pop hl
    pop bc
    ret
.z:
    ld a,b
    pop hl
    pop bc
    ret

; A brain's sprites, worked out at the tick, at DE (moved on), as many as
; fit.  From lo_qspr.
tu_bspr:
    ld a,(tu_bcon)              ; the Big Core's core, where lo_bossspr has
    or a                        ; the boss
    jr z,.l
    ld a,(lo_bon)
    or a
    jr z,.l
    ld a,e
    cp (LO_ATTR+NSPR*5)&0xff
    jr nz,.cc
    ld a,d
    cp (LO_ATTR+NSPR*5)>>8
    ret z
.cc:
    ld a,(lo_bx)                ; X: lo_bx - lo_bdx + its place + 32
    ld l,a
    ld h,0
    ld bc,BC_CX+32
    add hl,bc
    ld a,(lo_bdx)
    ld c,a
    ld b,0
    or a
    sbc hl,bc
    ld a,l
    ld (de),a
    inc de
    ld a,(lo_bdy)               ; Y: lo_by + lo_bdy + its place + 32
    ld c,a
    ld a,(lo_by)
    add a,c
    add a,BC_CY+32
    ld (de),a
    inc de
    ld a,h
    and 1
    or 0xE0                     ; palette 14
    ld (de),a
    inc de
    ld a,0xC0|(BC_PAT>>1)
    ld (de),a
    inc de
    ld a,0x80|((BC_PAT&1)<<6)
    ld (de),a
    inc de
.l:
    ld a,(tu_bn)
    or a
    ret z
    ld b,a
    ld hl,tu_bs
.c:
    ld a,e
    cp (LO_ATTR+NSPR*5)&0xff
    jr nz,.ok
    ld a,d
    cp (LO_ATTR+NSPR*5)>>8
    ret z
.ok:
    push bc
    ld bc,5
    ldir
    pop bc
    djnz .c
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
BST         equ 8+2*CST         ; a brain's state (tu_brain)
CST         equ 5+3*14          ; a chain's (tu_chain)
tu_bst0:    ds BST
tu_bst1:    ds BST
tu_gh0:     ds BST              ; their ghosts (2*BST on: tu_ghost)
tu_gh1:     ds BST
tu_qr:      ds 8*QRS            ; stages 3 and 4's pieces (tu_qwatch)
tu_s8ok:    db 0                ; stage 8: the bolts' drawings sent
tu_s8fv:    db 0                ; stage 8: the bolts' fade as set,
tu_s8f:     db 0                ; tu_s8pal's
tu_s8sh:    dw 0                ; stage 8: the brain's screen's columns to come * 8
tu_xw:      dw 0                ; tu_put: added to X (stage 8's bolts)
tu_s8st:    ds 6                ; each bolt: 0 gone, 1 on,
tu_s8fl:    ds 6                ; ticks of flicker left,
tu_s8pl:    ds 6                ; its palette (E0h or F0h),
tu_s8v:     ds 6                ; and as shown this tick (0: not)
tu_rng:     db 1
tu_bcb:     db 0                ; the Big Core: the block being made,
tu_bcm:     db 0                ; MMU2 as it was,
tu_bc43:    db 0                ; the palette control as it was,
tu_bcp:     db 0                ; its palettes set,
tu_bcv:     db 0xFF             ; the core sent (5: none; FFh: not there),
tu_bcon:    db 0                ; and the core shown this tick
tu_zf:      db 0xFF             ; the ending's zoom: the size shown (FFh none),
tu_zset:    db 104              ; and the patterns it was sent to (104 or 116)
tu_bn:      db 0                ; the brains' sprites,
tu_bsp:     dw 0                ; the next in the list,
tu_bs:      ds NB6S*5           ; the list (5 attributes each)
tu_kx:      db 0                ; tu_brain: Konami's X, Y,
tu_ky:      db 0
tu_dx:      db 0                ; those shown,
tu_dy:      db 0
tu_fr:      db 0                ; through the step (0-9),
tu_bd:      db 0                ; the drawing
tu_cd:      db 0                ; tu_chain: the drawing,
tu_crx:     db 0                ; its place from the brain,
tu_cry:     db 0
tu_k:       db 0                ; the slide's numerator
tu_gadd:    db 0                ; tu_put: added to X (a brain gliding off)
tu_lc:      db 0                ; tu_lift: the first column
tu_q:       db 0                ; tu_lerp: the quotient
tu_pp:      db 0                ; tu_put: the pattern,
tu_ppal:    db 0                ; the palette byte,
tu_pyr:     db 0                ; Y from the brain
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
    assert tu_end <= TB
    savebin "nx_tur.bin", 0x6000, tu_end - 0x6000
