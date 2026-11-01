; ---- bulk VRAM writes -------------------------------------------------------
; vbulk: BC (> 0) bytes from HL (fixed RAM) to VRAM from vdp_addr on, which it
; advances.  Colour and pattern bytes go to their shadows up to a tile's 8
; bytes at a time, with one page borrow each; a tile whose bytes changed is
; marked for conversion as a whole.  Other regions go through vram_write
; byte by byte.  Clobbers AF, BC, DE, HL.
vb_src:     dw 0
vb_cnt:     dw 0
vb_off:     dw 0
vb_page:    db 0
vb_map:     db 0                ; tile_cdirty or tile_pdirty low byte (0 or 0x80); 1: sprite patterns
vbulk:
    ld (vb_src),hl
    ld (vb_cnt),bc
.next:
    ld hl,(vb_cnt)
    ld a,h
    or l
    ret z
    ld de,(vdp_addr)
    ld a,d
    cp 0x38
    jr nc,.one
    cp 0x20
    jr nc,.pat
    cp 0x18
    jr nc,.spr
    ld hl,COL_SHADOW
    ld a,PAGE_C
    ld (vb_page),a
    ld a,tile_cdirty&0xff
    jr .chunk
.one:
    dec hl
    ld (vb_cnt),hl
    ld hl,(vb_src)
    ld a,(hl)
    inc hl
    ld (vb_src),hl
    call vram_write
    jr .next
.spr:
    sub 0x18
    ld d,a
    ld hl,SPR_PAT
    ld a,PAGE_7
    ld (vb_page),a
    ld a,1                      ; no tiles to mark (not 0: tile_cdirty's low byte)
    jr .chunk
.pat:
    sub 0x20
    ld d,a
    ld hl,PAT_SHADOW
    ld a,PAGE_D
    ld (vb_page),a
    ld a,tile_pdirty&0xff
.chunk:
    ld (vb_map),a
    ld (vb_off),de
    add hl,de
    ex de,hl                    ; DE = shadow address
    ld a,(vb_off)
    and 7
    ld b,a
    ld a,8
    sub b
    ld b,a                      ; up to the end of this tile's 8 bytes
    ld hl,(vb_cnt)
    ld a,h
    or a
    jr nz,.kok
    ld a,l
    cp b
    jr nc,.kok
    ld b,a
.kok:
    ld a,l
    sub b
    ld l,a
    jr nc,.c1
    dec h
.c1:
    ld (vb_cnt),hl
    ld hl,(vdp_addr)
    ld a,l
    add a,b
    ld l,a
    jr nc,.c2
    inc h
    ld a,h
    and 0x3f
    ld h,a
.c2:
    ld (vdp_addr),hl
    ld hl,(vb_src)
    ld c,0                      ; bytes changed
    push af                     ; (a placeholder: the stack layout below counts it)
    ld a,(vb_page)
    call borrow_page
.cp:
    ld a,(de)
    cp (hl)
    jr z,.same
    ld a,(hl)
    ld (de),a
    inc c
.same:
    inc hl
    inc de
    djnz .cp
    ld (vb_src),hl
    push bc
    call unborrow_page
    pop bc
    pop af
.di:
    ld a,c
    or a
    jp z,.next
    ld a,(vb_map)
    cp 1
    jp z,.next                  ; sprite patterns
    ld de,(vb_off)
    ld a,(vb_map)
    ld l,a
    ld h,tile_cdirty>>8
    call mark_tile
    jp .next

; descomprime (MSX 49B9), Konami's run-length decompressor into VRAM, here
; collecting its output in dc_buf for vbulk instead of one OUT per byte.
; Leaves the registers as the original does (A = 0 and Z, DE at the end
; marker, HL the VRAM address, B = 0, C' = the VDP port).
DC_LEN equ 64
DC_END equ (dc_buf+DC_LEN)&0xff
descomprime_native:
    xor a
    ld (dz_on),a                ; graphics loading: a dissolve is over (0.107)
    call m0_494A                ; SETWRT HL, C' = VDP port
    push hl
    ld hl,dc_buf
.cmd:
    ld a,(de)
    and a
    jr z,.end
    inc de
    ld b,a
    and 0x7f
    cp b
    jr z,.rep
    and a
    jr z,.dest                  ; 0x80: a new VRAM address follows
    ld b,a
.lit:
    ld a,(de)
    inc de
    ld (hl),a
    inc l
    ld a,l
    cp DC_END
    call z,dc_flush_hl
    djnz .lit
    jr .cmd
.rep:
    ld a,(de)
    inc de
    ld c,a
.r:
    ld (hl),c
    inc l
    ld a,l
    cp DC_END
    call z,dc_flush_hl
    djnz .r
    jr .cmd
.dest:
    call dc_flush_hl
    pop hl
    ex de,hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    ex de,hl
    inc de
    jr descomprime_native
.end:
    call dc_flush_hl
    pop hl
    xor a
    ret

; Write out dc_buf up to HL (exclusive); HL = dc_buf after.  Preserves BC, DE.
dc_flush_hl:
    push bc
    push de
    ld a,l
    sub dc_buf&0xff
    jr z,.empty
    ld c,a
    ld b,0
    ld hl,dc_buf
    call vbulk
.empty:
    ld hl,dc_buf
    pop de
    pop bc
    ret

dc_buf      equ 0xAEB4          ; free: above the IM2 jump at AEAE, below Konami's RAM
    assert dc_buf + DC_LEN <= 0xAF00



; LDIRMV (BIOS 0059): BC bytes from VRAM HL to RAM DE, a run of up to 64
; bytes within one region at a time, copied with the shadow page borrowed.
rm_src:     dw 0
rm_dst:     dw 0
rm_cnt:     dw 0
rm_page:    db 0
bios_0059:
    push af
    push bc
    push de
    push hl
    ld (rm_src),hl
    ld (rm_dst),de
    ld (rm_cnt),bc
.loop:
    ld bc,(rm_cnt)
    ld a,b
    or c
    jp z,.done
    ld hl,(rm_src)
    ld a,h
    and 0x3f
    ld h,a
    cp 0x38
    jr nc,.byte
    ld a,(rm_dst+1)
    cp 0xc0
    jr nc,.byte                 ; (not expected: a paged destination)
    ld a,h
    cp 0x18
    jr c,.col
    cp 0x20
    jr c,.spr
    ld de,PAT_SHADOW-0x2000
    ld a,PAGE_D
    ld b,0x38
    jr .run
.col:
    ld de,COL_SHADOW
    ld a,PAGE_C
    ld b,0x18
    jr .run
.spr:
    ld de,SPR_PAT-0x1800
    ld a,PAGE_7
    ld b,0x20
.run:
    ld (rm_page),a
    ld c,64                     ; n = min(64, to the region's end, count)
    ld a,b
    sub h
    dec a
    jr nz,.r1
    ld a,l
    neg
    jr z,.r1
    cp c
    jr nc,.r1
    ld c,a
.r1:
    ld a,(rm_cnt+1)
    or a
    jr nz,.r2
    ld a,(rm_cnt)
    cp c
    jr nc,.r2
    ld c,a
.r2:
    ld b,0
    push hl
    ld hl,(rm_cnt)
    or a
    sbc hl,bc
    ld (rm_cnt),hl
    pop hl
    push hl
    add hl,bc
    ld (rm_src),hl
    pop hl
    add hl,de                   ; shadow address
    ld de,(rm_dst)
    push af                     ; (a placeholder: the stack layout below counts it)
    ld a,(rm_page)
    call borrow_page
    ldir
    ld (rm_dst),de
    call unborrow_page
    pop af
    jp .loop
.byte:
    call vram_read
    ld de,(rm_dst)
    ld (de),a
    inc de
    ld (rm_dst),de
    inc hl
    ld (rm_src),hl
    ld hl,(rm_cnt)
    dec hl
    ld (rm_cnt),hl
    jp .loop
.done:
    pop hl
    pop de
    pop bc
    pop af
    ret
