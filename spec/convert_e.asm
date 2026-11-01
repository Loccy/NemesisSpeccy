; The colour fit (convert_tile) and recolouring, run with page B mapped
; (F900 on, past MSX bank 5's used part): they run rarely, and fixed RAM is
; full.  convert_cached and recolour_e map page B around them.

    align 256
cv_w:       ds 256              ; w[ci][k], 8 x 16 words
cv_counts:  ds 16               ; pixels per MSX colour
cv_pm:      ds 16               ; present MSX colours
cv_pn:      ds 16               ; and their pixel counts (must follow cv_pm)
cv_np:      db 0
cv_cz:      ds 8                ; candidate ZX colours for this bright
cv_nc:      db 0
cv_br:      db 0
cv_ii:      db 0
cv_pi:      db 0
cv_err:     dw 0
cv_wlo:     db 0
cv_best_err: dw 0
cv_best_sec: dw 0
cv_best_br:  db 0
    assert (cv_cz & 0xff) < 0xf8 && (cv_counts & 0xff) < 0xf0 && (cv_pm & 0xff) < 0xe0

convert_tile:
    ; --- pixel count per MSX colour ---
    ld hl,cv_counts
    xor a
    ld b,16
.clr:
    ld (hl),a
    inc hl
    djnz .clr
    ld hl,cv_w                  ; per colour: bit 7 = in a textured row, else solid rows
    ld b,16
.clr2:
    ld (hl),a
    inc l
    djnz .clr2
    ld ix,cv_pat
    ld b,8
    ld d,cv_counts>>8
.row:
    ld a,(ix+0)                 ; set pixels in this row
    ld c,0
.pop:
    or a
    jr z,.popped
    ld h,a
    dec a
    and h
    inc c
    jr .pop
.popped:
    ld a,(ix+8)                 ; colour row
    ld e,a
    rrca
    rrca
    rrca
    rrca
    and 15
    add a,cv_counts&0xff
    ld l,a
    ld h,d
    ld a,(hl)
    add a,c
    ld (hl),a
    ld a,e
    and 15
    add a,cv_counts&0xff
    ld l,a
    ld a,8
    sub c
    add a,(hl)
    ld (hl),a
    ; a row of one colour (allowing one odd pixel) counts as a line of that
    ; colour; otherwise both colours are marked as part of the texture
    ld h,cv_w>>8
    ld a,c
    cp 2
    jr c,.sbg                   ; 0 or 1 pixel set: a line of the background colour
    cp 7
    jr nc,.sfg                  ; 7 or 8 set: a line of the foreground colour
    ld a,e
    rrca
    rrca
    rrca
    rrca
    xor e
    and 15
    jr z,.sfg
    ld a,e
    and 15
    ld l,a
    set 7,(hl)
    ld a,e
    rrca
    rrca
    rrca
    rrca
    and 15
    ld l,a
    set 7,(hl)
    jr .rdone
.sbg:
    ld a,e
    and 15
    jr .solid
.sfg:
    ld a,e
    rrca
    rrca
    rrca
    rrca
    and 15
.solid:
    ld l,a
    inc (hl)
.rdone:
    inc ix
    djnz .row
    ; --- a colour seen only in one or two line rows (a border) does
    ; not vote in the fit, unless fewer than two others are left; its pixels
    ; still go to whichever of the chosen ink and paper is nearer ---
    ld hl,cv_w
    ld bc,16*256
.x1:
    ld a,(hl)
    cp 3
    jr c,.x1n
    inc c
.x1n:
    inc l
    djnz .x1
    ld a,c
    cp 2                        ; at least two colours must still vote
    jr c,.keep
    ld hl,cv_w
    ld de,cv_counts
    ld b,16
.x2:
    ld a,(hl)
    dec a
    cp 2
    jr nc,.x2n
    xor a
    ld (de),a
.x2n:
    inc l
    inc de
    djnz .x2
.keep:
    ; --- present colours ---
    ld hl,cv_counts
    ld de,cv_pm
    ld c,0
.pres:
    ld a,(hl)
    or a
    jr z,.pnext
    ld (hl),0
    push hl
    ld hl,16
    add hl,de
    ld (hl),a                   ; cv_pn[k]
    pop hl
    ld a,c
    ld (de),a                   ; cv_pm[k]
    inc de
.pnext:
    inc hl
    inc c
    bit 4,c
    jr z,.pres
    ld a,e
    sub cv_pm&0xff
    ld (cv_np),a
    ld hl,0xffff
    ld (cv_best_err),hl
    ld (cv_best_sec),hl
    xor a
    ld (cv_br),a
.bright:
    add a,cv_dist>>8
    ld (cv_dbase),a
    ; --- candidates: nearest ZX colour of each present MSX colour ---
    xor a
    ld (cv_nc),a
    ld a,(cv_np)
    ld b,a
    ld de,cv_pm
.cand:
    ld a,(cv_br)
    add a,a
    add a,a
    add a,a
    add a,a
    ld l,a
    ld a,(de)
    add a,l
    ld hl,cv_near
    add a,l
    ld l,a
    jr nc,.cn
    inc h
.cn:
    ld c,(hl)                   ; nearest ZX colour
    ld hl,cv_cz
    ld a,(cv_nc)
    or a
    jr z,.add
    push bc
    ld b,a
.seek:
    ld a,(hl)
    cp c
    jr z,.have
    inc hl
    djnz .seek
    pop bc
.add:
    ld (hl),c
    ld hl,cv_nc
    inc (hl)
    jr .cnext
.have:
    pop bc
.cnext:
    inc de
    djnz .cand
    ; --- weights w[ci][k] = pn[k] * D[pm[k]][cz[ci]], by quarter squares ---
    ld a,(cv_nc)
    ld b,a
    ld c,0                      ; ci
.wci:
    push bc
    ld a,c
    add a,cv_cz&0xff
    ld l,a
    ld h,cv_cz>>8
    ld a,(hl)
    add a,a
    ld (.zz+1),a                ; 2 * cz[ci]
    ld a,c
    rrca
    rrca
    rrca                        ; ci * 32
    ld (cv_wlo),a
    ld a,(cv_np)
    ld b,a
    ld ix,cv_pm
.wk:
    ld a,(ix+0)
    add a,a
    add a,a
    add a,a
    add a,a
.zz:
    add a,0                     ; patched: 2 * cz[ci]
    ld l,a
    ld a,(cv_dbase)
    ld h,a
    ld e,(hl)
    inc l
    ld d,(hl)                   ; DE = distance d
    ld a,(ix+16)                ; n = pixel count (0-64)
    ; n * d: shift and add from bit 6 down, unrolled (bit 7 of n is never
    ; set, so it is shifted out first) (0.106)
    ld hl,0
    add a,a
    rept 7
    add hl,hl
    add a,a
    jr nc,$+3
    add hl,de
    edup
    ex de,hl                    ; DE = n * d
    ld a,(cv_wlo)
    ld l,a
    ld h,cv_w>>8
    ld (hl),e
    inc l
    ld (hl),d
    inc l
    ld a,l
    ld (cv_wlo),a
    inc ix
    djnz .wk
    pop bc
    inc c
    djnz .wci
    ; --- every unordered pair {ii, pi}: err once, both orientations keyed ---
    xor a
    ld (cv_ii),a
.pii:
    ld (cv_pi),a
.ppi:
    ld a,(cv_ii)
    rrca
    rrca
    rrca
    ld e,a                      ; w[ii]'s row
    ld a,(cv_pi)
    rrca
    rrca
    rrca
    ld l,a                      ; w[pi]'s row
    ld a,(cv_np)
    add a,a
    add a,l
    ld (.pend+1),a              ; the end of w[pi]'s row
    ld h,cv_w>>8
    ld d,h
    ld ix,0                     ; err accumulator
.sum:                           ; err += min(w[ii][k], w[pi][k]) (0.106: no stack)
    ld a,(de)
    sub (hl)
    inc e
    inc l
    ld a,(de)
    sbc a,(hl)                  ; carry: w[ii][k] < w[pi][k]
    jr c,.tii
    ld b,(hl)                   ; w[pi][k] (also when they are equal)
    dec l
    ld c,(hl)
    inc l
    jr .acc
.tii:
    ex de,hl
    ld b,(hl)                   ; w[ii][k]
    dec l
    ld c,(hl)
    inc l
    ex de,hl
.acc:
    add ix,bc
    inc e
    inc l
    ld a,l
.pend:
    cp 0                        ; patched: the end of the row
    jr nz,.sum
    ld (cv_err),ix
    ; a pair whose error is above the best so far cannot win in either
    ; orientation (cv_try would keep neither); equal errors still go to the
    ; tie-break (0.106)
    push ix
    pop hl
    ld de,(cv_best_err)
    or a
    sbc hl,de
    jr z,.try
    jp nc,.oneonly
.try:
    ; orientation 1: ink = cz[ii], paper = cz[pi]
    ld a,(cv_ii)
    ld e,a
    ld a,(cv_pi)
    ld d,a
    call cv_try
    ld a,(cv_ii)
    ld e,a
    ld a,(cv_pi)
    cp e
    jr z,.oneonly
    ld d,e
    ld e,a
    call cv_try                 ; orientation 2: ink = cz[pi], paper = cz[ii]
.oneonly:
    ld hl,cv_pi
    inc (hl)
    ld a,(cv_nc)
    cp (hl)
    jp nz,.ppi
    ld hl,cv_ii
    inc (hl)
    cp (hl)
    ld a,(hl)
    jp nz,.pii
    ld hl,cv_br
    inc (hl)
    ld a,(hl)
    cp 2
    jp nz,.bright
    ; --- the winning attribute ---
    ld a,(cv_best_pap)
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,(cv_best_ink)
    or b
    ld b,a
    ld a,(cv_best_br)
    rrca
    rrca
    or b
    ld (cv_out+8),a
    jp cv_pixels

; Candidate indices E (ink) and D (paper), err in cv_err: keep if better.
cv_try:
    ld hl,cv_cz
    ld a,l
    add a,e
    ld l,a
    ld b,(hl)                   ; ink
    ld hl,cv_cz
    ld a,l
    add a,d
    ld l,a
    ld c,(hl)                   ; paper
    ; secondary key: (ink==paper)<<9 | (ink!=7 && paper!=0)<<8 | ink | paper<<3 | br<<6
    ld d,0
    ld a,b
    cp c
    jr nz,.ne
    set 1,d
.ne:
    cp 7
    jr z,.f0
    ld a,c
    or a
    jr z,.f0
    set 0,d
.f0:
    ld a,c
    add a,a
    add a,a
    add a,a
    or b
    ld e,a
    ld a,(cv_br)
    rrca
    rrca
    or e
    ld e,a                      ; DE = secondary key
    ld hl,(cv_err)
    push de
    ld de,(cv_best_err)
    or a
    sbc hl,de
    pop de
    jr c,.better
    ret nz
    ld hl,(cv_best_sec)
    ex de,hl
    or a
    sbc hl,de                   ; sec - best_sec
    ret nc
    ex de,hl                    ; DE = sec... restore: HL = best, DE = sec - best
    add hl,de
    ex de,hl                    ; DE = sec
.better:
    ld hl,(cv_err)
    ld (cv_best_err),hl
    ld (cv_best_sec),de
    ld a,b
    ld (cv_best_ink),a
    ld a,c
    ld (cv_best_pap),a
    ld a,(cv_br)
    ld (cv_best_br),a
    ret

; Pixels for the chosen ink/paper/bright in cv_out+8: each MSX colour goes to
; whichever of ink/paper is strictly nearer (ink only if ink != paper).
cv_pixels:
    ld a,(cv_best_br)
    add a,cv_dist>>8
    ld (cv_dbase),a
    ld ix,cv_pat
    ld iy,cv_out
    ld b,8
.bits:
    ld a,(ix+8)
    rrca
    rrca
    rrca
    rrca
    and 15
    call nearer_ink             ; A = 0xFF if fg -> ink
    and (ix+0)
    ld c,a
    ld a,(ix+8)
    and 15
    call nearer_ink
    ld e,a
    ld a,(ix+0)
    cpl
    and e
    or c
    ld (iy+0),a
    inc ix
    inc iy
    djnz .bits
    ret

; Pattern rows changed, colours did not: keep the attribute already in
; cv_out+8 and map the new pixels.
recolour_tile:
    ld a,(cv_out+8)
    ld b,a
    and 7
    ld (cv_best_ink),a
    ld a,b
    rrca
    rrca
    rrca
    and 7
    ld (cv_best_pap),a
    ld a,b
    rlca
    rlca
    and 1
    ld (cv_best_br),a
    jp cv_pixels


; Konami's screen dissolve (0.107; dz_on): it turns every background black,
; then eats the pixels away, while the foreground keeps its colour.  So a
; tile whose MSX rows all have a black background (0 or 1) keeps the colour
; that showed its foreground, as ink on black paper, and its pixels are
; mapped as recolour_tile does.  Which of the old ink and paper showed the
; foreground: whichever drew more of the pattern's pixels (the ink on a tie).
; In: cv_pat, cv_col (the MSX rows now), cv_out (the tile as it was, its
; attribute possibly flagged).  Out: carry if a row has another background
; (the colour fit then), else cv_out the new tile.
dz_tile:
    ld hl,cv_col
    ld b,8
.bg:
    ld a,(hl)
    and 0x0e
    scf
    ret nz
    inc hl
    djnz .bg
    ld e,0
    ld a,(cv_out+8)
    and 0x38
    jr z,.attr                  ; black paper: the ink showed it (E = 0)
    ld e,0x80
    ld a,(cv_out+8)
    and 7
    jr z,.attr                  ; black ink, coloured paper: the paper
    ld ix,cv_pat
    ld e,0                      ; pattern pixels the ink drew less those the paper drew
    ld c,8
.row:
    ld a,(ix+0)
    or a
    jr z,.next                  ; no pixels in this row
    ld d,a
    ld a,(ix+cv_out-cv_pat)     ; the old row
    ld b,8
.px:
    rlca                        ; old pixel -> carry
    rl d                        ; ...into D bit 0, pattern pixel -> carry
    jr nc,.nopx
    bit 0,d
    jr z,.pap
    inc e
    jr .nopx
.pap:
    dec e
.nopx:
    djnz .px
.next:
    inc ix
    dec c
    jr nz,.row
.attr:
    ld a,(cv_out+8)
    and 0x7f
    ld b,a
    bit 7,e
    jr z,.ink
    rrca                        ; the paper showed it
    rrca
    rrca
.ink:
    and 7
    ld c,a
    ld a,b
    and 0x40                    ; bright kept, paper black
    or c
    ld (cv_out+8),a
    and 7
    ld (cv_best_ink),a
    xor a
    ld (cv_best_pap),a
    ld a,(cv_out+8)
    rlca
    rlca
    and 1
    add a,cv_dist>>8
    ld (cv_dbase),a
    ; the pixels: each row's background is black, which is the paper; its
    ; foreground goes to the ink if strictly nearer it (cv_pixels' rule),
    ; one test per foreground colour while it repeats
    ld ix,cv_pat
    ld b,8
    ld c,0xff                   ; the last foreground tested (none yet)
.pix:
    ld a,(ix+8)
    rrca
    rrca
    rrca
    rrca
    and 15
    cp c
    jr z,.same
    ld c,a
    call nearer_ink
    ld e,a                      ; its mask
.same:
    ld a,(ix+0)
    and e
    ld (ix+cv_out-cv_pat),a
    inc ix
    djnz .pix
    or a
    ret
