; The native build's graphics (claude/native-128k-plan.md): Konami's
; graphics loads become loads of sets converted when the game is built
; (native_sets.py, packed by native_pack.py into native_data.asm), and
; Konami's screen dissolve works on the converted tiles.  Fixed memory, after
; Konami's bank 0 (whose loaders the native build leaves out).
;
; The packed pieces are in the switched banks, as is the tile set (bank 7,
; DB00-F5FF), and only one bank can be at C000 at a time; ZX0 reads its input
; in order, so the unpacker reads it through nl_buf (256 bytes, refilled from
; the source bank) and writes straight into the destination bank.  A patch is
; unpacked into page D's work area (E800) and copied in a character at a time.

NL_WORK equ 0xE800              ; page D: a patch, unpacked

nl_srcpg:   db 0                ; the source's page
nl_src:     dw 0                ; the next source byte to copy into nl_buf
nl_dstpg:   db 0                ; the destination's page
nl_w:       dw 0                ; scatter: the next byte of the patch
nl_m:       db 0                ; scatter: the mask byte's index
nl_mb:      db 0                ; scatter: the mask byte, turning
nl_count:   db 0                ; loads and dissolve chunks so far (for the checks)

; ---- the event entry points (Konami's sites, reloc/gen.py) -------------------

; 0:422A, carga_los_graficos_de_la_fase: the stage's set, then E100 = 1 and
; the mapper put back as Konami's routine leaves them.
nl_stage:
    call nl_save
    ifndef NEXT
    ld a,(0xE061+KRAM)
    call nl_full
    else
    call nl_done                ; Next: lo_stage's lo_apply copies the stage file
    endif
    pop ix
    pop af
    pop bc
    pop de
    pop hl
    ld a,1
    ld (0xE100+KRAM),a
    jp m0_4299                  ; devuelve_el_reparto_de_siempre

    ifndef NEXT
nl_bigcore:                     ; 0:4A8A (the Big Core's characters)
    call nl_save
    ld a,(0xE061+KRAM)
    dec a
    ld l,a
    add a,a
    add a,l
    ld l,a
    ld h,0
    ld de,nl_bigcore_tab
    add hl,de
    jr nl_desc
nl_title:                       ; 0:5300
    call nl_save
    ld hl,nl_title_d
    jr nl_desc
nl_prestage:                    ; 0:53D4
    call nl_save
    ld hl,nl_prestage_d
    jr nl_desc
nl_gameover:                    ; 0:54DD
    call nl_save
    ld hl,nl_gameover_d
    jr nl_desc
nl_marcador:                    ; 0:4C2E
    call nl_save
    ld hl,nl_marcador_d
    jr nl_desc
nl_ending:                      ; 0:4B04
    call nl_save
    ld hl,nl_ending_d
nl_desc:                        ; HL = a patch's descriptor (page, address)
    call nl_patch
    jp nl_restore

    else
; The Next (claude/native-128k-plan.md, step 3): the same events load the
; bytes Konami's loaders wrote (native_next.py) into its store of character
; rows (pages C and D, E800: colours and patterns as the MSX's tables) and
; sprite patterns (bank 7, F800), from the Next's 8K pages, raw.  A character
; that changes is marked in tile_cdirty or tile_pdirty, as Konami's writes
; were (the pool then leaves it to the rows: nx_l2.asm lo_cmap).  The title,
; the ending and its status line put the TMS9918's colours back
; (lo_marcador, nx_low.asm's 011E), as Konami's 0:5851 did on the Next.
nl_bigcore:                     ; 0:4A8A (the Big Core's characters)
    call nl_save
    ld a,(0xE061+KRAM)
    dec a
    ld l,a
    add a,a
    add a,a
    add a,a
    add a,l                     ; 9 bytes a stage
    ld l,a
    ld h,0
    ld de,nxl_bigcore_tab
    add hl,de
    jr nx_desc
nl_title:                       ; 0:5300
    call nl_save
    ld hl,nxl_title_d
    call nx_load
    ld a,1                      ; the title: its logo's colours too
    jr nx_tms
nl_prestage:                    ; 0:53D4 (lo_prestage follows, at 0:544F)
    call nl_save
    ld hl,nxl_prestage_d
    jr nx_desc
nl_gameover:                    ; 0:54DD
    call nl_save
    ld hl,nxl_gameover_d
    call nx_load
    call nx_gopal               ; (1.1.3) its text in stage 1's colours, whatever the stage
    jp nl_restore
nl_marcador:                    ; 0:4C2E
    call nl_save
    ld hl,nxl_marcador_d
    call nx_load
    xor a
    jr nx_tms
nl_ending:                      ; 0:4B04
    call nl_save
    xor a
    call 0x011E                 ; lo_marcador first, as 0:5851 came first
    ld hl,nxl_ending_d
nx_desc:
    call nx_load
    jp nl_restore
nx_tms:
    call 0x011E                 ; lo_marcador (A = 1: the title)
    jp nl_restore
; Game over (nl_gameover): Layer 2's entries 0-15, which text drawn from the
; copies uses, get stage 1's 16 colours (the status line's, F0-FF), so GAME
; OVER looks the same after every stage; everything else stays as in play (no
; lo_marcador: that is Konami's original look, for the title and the ending
; only).  A continue's stage load (lo_apply) puts the stage's colours back.
NX_ST1PAL   equ 33              ; 8K page: stage 1's VRAM 2000-3FFF, its palette at 1800
nx_gopal:
    db 0xED,0x91,0x52,NX_ST1PAL ; at 4000
    db 0xED,0x91,0x43,0x10      ; Layer 2's first palette, from entry 0
    db 0xED,0x91,0x40,0x00
    ld hl,0x5800
    ld b,32
.p:
    ld a,(hl)
    db 0xED,0x92,0x44
    inc hl
    djnz .p
    db 0xED,0x91,0x43,0x00
    db 0xED,0x91,0x52,0x0A
    ret

; HL = an event's descriptors (colours, patterns, sprite patterns).
nx_load:
    ld bc,PAGE_C*256+0x00       ; colours: page C, tile_cdirty
    call nx_chars
    ld bc,PAGE_D*256+0x80       ; patterns: page D, tile_pdirty
    call nx_chars
    call nx_sprites
    jp nl_done

; HL = a descriptor (page, address at 4000; page FF: none), moved on.  The
; marked characters' 8 bytes each go to E800 + character * 8 in page B (C or D); one
; that changes is marked in the bitmap at tile_cdirty + C.
nx_chars:
    ld a,(hl)
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    cp 0xff
    ret z
    push hl
    db 0xED,0x92,0x52           ; nextreg 0x52,a: the piece at 4000
    ld a,b
    call out_page
    ld a,c
    ld (.map+1),a
    push de
    pop ix                      ; the mask
    ld hl,96
    add hl,de                   ; the bytes
    ld de,0xE800
    xor a
    ld (nx_i),a
.byte:
    ld a,(ix+0)
    ld (nx_mb),a
    ld b,8
.bit:
    ld a,(nx_mb)
    rrca
    ld (nx_mb),a
    jr c,.one
    ld a,e
    add a,8
    ld e,a
    jr nc,.next
    inc d
    jr .next
.one:
    push bc
    ld bc,0x0800                ; B = 8 bytes, C = changed
.cp:
    ld a,(de)
    cp (hl)
    jr z,.eq
    ld a,(hl)
    ld (de),a
    ld c,1
.eq:
    inc hl
    inc de
    djnz .cp
    ld a,c
    pop bc
    or a
    jr z,.next
    push hl                     ; mark it: bit 8 - B of byte nx_i
    ld a,8
    sub b
    ld l,a
    ld h,bitmask>>8
    ld a,(nx_i)
.map:
    add a,0
    ld c,(hl)
    ld l,a
    ld h,tile_cdirty>>8
    ld a,c
    or (hl)
    ld (hl),a
    pop hl
.next:
    djnz .bit
    inc ix
    ld a,(nx_i)
    inc a
    ld (nx_i),a
    cp 96
    jr nz,.byte
    db 0xED,0x91,0x52,0x0A      ; bank 5 back at 4000
    call unborrow_page
    pop hl
    ret

; HL = a descriptor: the marked sprite patterns' 32 bytes each to F800 +
; pattern * 32 in bank 7.
nx_sprites:
    ld a,(hl)
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    cp 0xff
    ret z
    db 0xED,0x92,0x52
    ld a,PAGE_7
    call out_page
    push de
    pop ix
    ld hl,8
    add hl,de
    ld de,0xF800
    ld c,8
.byte:
    ld a,(ix+0)
    ld b,8
.bit:
    rrca
    jr nc,.skip
    push bc
    ld bc,32
    ldir
    pop bc
    jr .next
.skip:
    ex de,hl
    push bc
    ld bc,32
    add hl,bc
    pop bc
    ex de,hl
.next:
    djnz .bit
    inc ix
    dec c
    jr nz,.byte
    db 0xED,0x91,0x52,0x0A
    jp unborrow_page

; From lo_stage, after lo_apply: bonus stages 10-12 are stage 9's file, but
; Konami's load gives character 44's colours otherwise (native_next.py).
nx_bonusfix:
    ld a,(0xE061+KRAM)
    sub 10
    cp 3
    ret nc
    ld hl,nxl_bonus_tab
    or a
    jr z,.at
    ld b,a
.skip:
    ld a,(hl)                   ; count, then 10 bytes each
    inc hl
    or a
    jr z,.sk
    ld e,a
.sk1:
    ld a,l
    add a,10
    ld l,a
    jr nc,.sk2
    inc h
.sk2:
    dec e
    jr nz,.sk1
.sk:
    djnz .skip
.at:
    ld b,(hl)
    inc hl
    inc b
    dec b
    ret z
    ld a,PAGE_C
    call out_page
.ch:
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    push hl
    ex de,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,0xE800
    add hl,de
    ex de,hl
    pop hl
    push bc
    ld bc,8
    ldir
    pop bc
    djnz .ch
    jp unborrow_page

nx_i:       db 0
nx_mb:      db 0

    endif

nl_save:                        ; every register kept for Konami; a graphics
    ex (sp),hl                  ; load ends a dissolve (as in 1.0: dz_on is up
    push de                     ; from its first chunk to the next load)
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
    ld (spx_stale),a            ; the sprite patterns' extents to be worked out again
    endif
nl_done_t:                      ; the same for tiles alone (a chunk of the dissolve):
    ld a,0xff                   ; the sprite patterns are as they were, and working
    ld (chg_n),a                ; their extents out again takes over two frames
    ld a,1
    ld (star_stale),a
    ifdef NEXT
    ld (spr_new),a              ; Next: lo_sprites compares all 64 patterns again,
    call nx_cclr                ; and makes every character enemy afresh
    endif
    ld hl,nl_count
    inc (hl)
    ret

    ifndef NEXT
; ---- loading -------------------------------------------------------------------

; A = stage 1-12: its complete set.
nl_full:
    dec a
    ld l,a
    add a,a                     ; 15 bytes an entry
    add a,a
    add a,a
    add a,a
    sub l
    ld l,a
    ld h,0
    ld de,nl_stage_tab
    add hl,de
    push hl
    ld de,0xDB00                ; the tiles
    call nl_unpack7
    pop hl
    inc hl
    inc hl
    inc hl
    push hl
    ld a,(hl)                   ; a patch over them (stages 10-12)
    inc a
    call nz,nl_patch
    ld hl,nl_spr_common         ; sprite patterns 0-39
    ld de,0xF800
    call nl_unpack7
    pop hl
    inc hl
    inc hl
    inc hl
    push hl
    ld de,0xFD00                ; 40-63
    call nl_unpack7
    pop hl
    inc hl
    inc hl
    inc hl
    ld de,star_attr
    ld bc,6
    ldir
    call bl_reset
    jr nl_done

; HL = a descriptor (page, address): unpack it into bank 7 at DE.
nl_unpack7:
    ld a,PAGE_7
    ld (nl_dstpg),a
    ld a,(hl)
    inc hl
    push af
    ld a,(hl)
    inc hl
    ld h,(hl)
    ld l,a
    pop af
    call nl_unpack
    jp unborrow_page

; HL = a patch's descriptor: unpack it into the work area, then copy its
; characters and sprite patterns into place.
nl_patch:
    ld a,PAGE_D
    ld (nl_dstpg),a
    ld a,(hl)
    inc hl
    push af
    ld a,(hl)
    inc hl
    ld h,(hl)
    ld l,a
    pop af
    ld de,NL_WORK
    call nl_unpack
    call nl_scatter
    call unborrow_page
    jp nl_done

; The patch in the work area: a 96-byte mask (bit k = character
; third * 256 + char), the 9 bytes of each marked character, an 8-byte mask
; of sprite patterns, 32 bytes each.
nl_scatter:
    ld hl,NL_WORK+96
    ld (nl_w),hl
    xor a
    ld (nl_m),a
.mbyte:
    ld a,PAGE_D
    call out_page
    ld a,(nl_m)
    ld l,a
    ld h,NL_WORK>>8
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
    ld hl,nl_m
    inc (hl)
    ld a,(hl)
    cp 96
    jr nz,.mbyte
    ; the sprite patterns
    ld a,PAGE_D
    call out_page
    ld hl,(nl_w)
    ld de,nl_buf+32             ; the mask, out of the way of the patterns' copies
    ld bc,8
    ldir
    ld (nl_w),hl
    ld de,0xF800                ; pattern 0
    ld hl,nl_buf+32
    ld c,8
.sbyte:
    ld b,8
    ld a,(hl)
.sbit:
    rrca
    call c,.spr
    push hl
    ld hl,32
    add hl,de
    ex de,hl
    pop hl
    djnz .sbit
    inc hl
    dec c
    jr nz,.sbyte
    ret
.spr:                           ; 32 bytes to DE in bank 7.  Keeps A, BC, DE, HL
    push af
    push bc
    push de
    push hl
    push de
    ld a,PAGE_D
    call out_page
    ld hl,(nl_w)
    ld de,nl_buf
    ld bc,32
    ldir
    ld (nl_w),hl
    ld a,PAGE_7
    call out_page
    pop de
    ld hl,nl_buf
    ld bc,32
    ldir
    pop hl
    pop de
    pop bc
    pop af
    ret
.one:                           ; character nl_m * 8 + B: its 9 bytes from the work area
    push bc
    ld hl,(nl_w)
    ld de,nl_buf
    ld bc,9
    ldir                        ; (page D is in)
    ld (nl_w),hl
    pop bc
    ld a,(nl_m)                 ; third = m >> 5, char = (m & 31) * 8 + bit
    ld c,a
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
    ld d,a
    add a,a
    add a,a
    add a,a
    add a,d
    add a,TILE_PAGES
    ld d,a                      ; row 0's page
    push bc
    ld a,PAGE_7
    call out_page
    ld hl,nl_buf
    ld b,9
.row:
    ld a,(hl)
    ld (de),a
    inc hl
    inc d
    djnz .row
    ld a,PAGE_D
    call out_page
    pop bc
    ret

; ---- the unpacker: ZX0 (Einar Saukas's format; tape/dzx0_standard.asm),
; its input read through nl_buf -----------------------------------------------

; A = the source's page, HL = its address, DE = the destination in page
; nl_dstpg (left mapped).
nl_unpack:
    ld (nl_srcpg),a
    ld (nl_src),hl
    push de
    call nl_fill
    pop de
    ld bc,0xffff
    push bc
    inc bc
    ld a,0x80
.literals:
    call .elias
    push af
.lit:
    call nl_get
    ld (de),a
    inc de
    dec bc
    ld a,b
    or c
    jr nz,.lit
    pop af
    add a,a
    jr c,.new_offset
    call .elias
.copy:
    ex (sp),hl
    push hl
    add hl,de
    ldir
    pop hl
    ex (sp),hl
    add a,a
    jr nc,.literals
.new_offset:
    pop bc
    ld c,0xfe
    call .elias_loop
    inc c
    ret z
    ld b,c
    push af
    call nl_get
    ld c,a
    pop af
    rr b
    rr c
    push bc
    ld bc,1
    call nc,.elias_backtrack
    inc bc
    jr .copy
.elias:
    inc c
.elias_loop:
    add a,a
    jr nz,.elias_skip
    call nl_get
    rla
.elias_skip:
    ret c
.elias_backtrack:
    add a,a
    rl c
    rl b
    jr .elias_loop

; A = the next input byte (HL in nl_buf).  Keeps the flags' carry, BC, DE.
nl_get:
    ld a,(hl)
    inc l
    ret nz
    push af
    call nl_fill
    pop af
    ret
; nl_buf = the next 256 source bytes; HL = nl_buf.  Keeps BC, DE.
nl_fill:
    push bc
    push de
    ld a,(nl_srcpg)
    call out_page
    ld hl,(nl_src)
    ld de,nl_buf
    ld bc,256
    ldir
    ld (nl_src),hl
    ld a,(nl_dstpg)
    call out_page
    pop de
    pop bc
    ld hl,nl_buf
    ret

    endif

; ---- Konami's screen dissolve on the converted tiles ----------------------------

; come_un_trozo (MSX 3:A765, patched to come here): one chunk of the
; dissolve, A = its first character, DE = the table (colours 0000/0800/1000,
; patterns 2000/2800/3000; the third from bits 11-12).  Konami's chunks: 64
; characters, 60 from 44 (the score and bar spared), 54 from C0 (F6-FF
; spared).  The colour pass turns every background black: a tile stored the
; other way round (nl_inv7/nl_inv8) goes back to ink on paper with its old
; paper as the ink; every tile's paper becomes black.  After its last chunk
; (Konami's pass does all of them in one tick, third 0's C0 last), the
; stage's patch (nl_dz7_d, nl_dz8_d) gives the tiles for which that rule is
; not what 1.0 shows (native_sets.dz_patch: 1.0's dz_tile, where the pixels
; are the MSX's foreground).  Each pattern pass ANDs
; the rows with Konami's mask for the pass (E1A2, turned three bits a row
; after the first pass, E1A0).  EA00, Konami's chunk buffer, is not kept:
; nothing reads it after the dissolve (the census).
    ifdef NEXT
; The Next: Konami's chunk done on its copies of the tables as Konami does it
; on the MSX's (the colour pass ANDs every byte with E1A2, F0: the
; backgrounds go; each pattern pass ANDs with E1A2, turned three bits a byte
; after the first pass, every character starting again with E1A2).  While
; dz_on is up the pool goes on drawing the scenery and Layer 2's colours fade
; (nx_l2.asm lo_cmap, lo_fadestep); what Konami spares stays.
dz_chunk:
    ld c,64
    cp 0x44
    jr nz,.c1
    ld c,60
.c1:
    cp 0xc0
    jr nz,.c2
    ld c,54
.c2:
    ld l,a
    ld a,1
    ld (dz_on),a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,de                   ; the VRAM address
    ld a,h
    sub 0x20
    ld b,PAGE_D                 ; patterns
    jr nc,.pat
    add a,0x20
    ld b,PAGE_C                 ; colours
.pat:
    add a,0xE8
    ld h,a                      ; the copy's
    ld a,b
    call out_page
    ld a,(0xE1A0+KRAM)
    ld d,a                      ; 0: the same mask every byte
    ld a,(0xE1A2+KRAM)
    ld e,a
.ch:
    ld a,e
    ld b,8
.by:
    ld (.m+1),a
    and (hl)
    ld (hl),a
    inc hl
.m:
    ld a,0
    inc d
    dec d
    jr z,.same
    rrca
    rrca
    rrca
.same:
    djnz .by
    dec c
    jr nz,.ch
    call unborrow_page
    jp nl_done
    else
dz_chunk:
    ld c,64
    cp 0x44
    jr nz,.c1
    ld c,60
.c1:
    cp 0xc0
    jr nz,.c2
    ld c,54
.c2:
    ld e,a                      ; first character
    ld a,d
    rrca
    rrca
    rrca
    and 3
    ld b,a                      ; third
    ld a,d
    cp 0x20
    push af
    ld a,PAGE_7
    call out_page
    ld a,b
    add a,a
    add a,a
    add a,a
    add a,b
    add a,TILE_PAGES
    ld d,a                      ; DE = row 0 of the first character
    pop af
    jr nc,.pat
    call dz_col
    ld a,b                      ; the colour pass's last chunk (third 0, C0-F5)?
    or a
    jr nz,.out
    ld a,e
    cp 0xF6
    jr nz,.out
    call unborrow_page          ; then 1.0's tiles where the rule is not
    ld a,(0xE061+KRAM)
    ld hl,nl_dz7_d
    cp 7
    jp z,nl_patch
    ld hl,nl_dz8_d
    cp 8
    jp z,nl_patch
    jp nl_done_t
.pat:
    call dz_pat
.out:
    call unborrow_page
    jp nl_done_t

; C characters from DE (row 0's address, page 7 in), B = third.
dz_col:
    ld a,(0xE061+KRAM)
    ld hl,nl_inv7
    cp 7
    jr z,.inv
    ld hl,nl_inv8
    cp 8
    jr z,.inv
    ld hl,0
.inv:
    ld (.ib+1),hl
.tile:
    push de
    ld hl,(.ib+1)               ; stored the other way round?
    ld a,h
    or l
    jr z,.plain
    ld a,b                      ; bit third * 256 + char
    add a,a
    add a,a
    add a,a
    add a,a
    add a,a
    ld l,a
    ld a,e
    rrca
    rrca
    rrca
    and 31
    add a,l
    ld l,a
    ld h,0
    push de
.ib:
    ld de,0
    add hl,de
    pop de
    ld a,e
    and 7
    inc a
    push bc
    ld b,a
    ld a,(hl)
.sh:
    rrca
    djnz .sh
    pop bc
    jr nc,.plain
    push de                     ; rows inverted, ink = the old paper
    ld l,8
.ir:
    ld a,(de)
    cpl
    ld (de),a
    inc d
    dec l
    jr nz,.ir
    ld a,(de)                   ; the attribute
    ld h,a
    rrca
    rrca
    rrca
    and 7
    ld l,a
    ld a,h
    and 0x40
    or l
    ld (de),a
    pop de
    jr .next
.plain:
    ld a,d
    add a,8
    ld h,a
    ld l,e
    ld a,(hl)
    and 0x47                    ; black paper
    ld (hl),a
.next:
    pop de
    inc e
    dec c
    jr nz,.tile
    ret

dz_pat:
    ld a,(0xE1A0+KRAM)
    ld h,a                      ; 0: the same mask every row
    ld a,(0xE1A2+KRAM)
    ld l,a
.tile:
    push de
    push bc
    ld a,l
    ld b,8
.row:
    ld c,a
    ex de,hl                    ; (keep the mask's turning in C)
    and (hl)
    ld (hl),a
    inc h
    ex de,hl
    ld a,h
    or a
    ld a,c
    jr z,.same
    rrca
    rrca
    rrca
.same:
    djnz .row
    pop bc
    pop de
    inc e
    dec c
    jr nz,.tile
    ret
    endif
