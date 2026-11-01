"""Generate the 128K .SNA and the original-level-data graphics assets.

Usage: python tools/build.py /path/to/nemesis.rom
No ROM is bundled with the project. Requires Pillow.
"""
import hashlib
import os
from pathlib import Path
import sys
from extract import Nemesis
from convert import tile_table,make_screen,screen_to_png
from mini_asm import assemble
from konami import BLOCKS, make_rom_blocks, as_db, ORIGINAL_LABELS
from enemies import extract_enemy_integrator,extract_type4, ORIGINAL_START, ORIGINAL_END
from enemy_dispatch import report as enemy_dispatch_report
from native_stage1 import code_from_rom

ROOT=Path(__file__).resolve().parent.parent
SHA='3210f8a0f2309dd4b9a89fc2b24d0f178ce4393a0a1f2854fbce545c361261bc'
START_COL=0
MAP_START=0x9500
BANK=16384

def physical_pixel_addr(y):
    return 0x4000 + ((y&0xc0)<<5) + ((y&7)<<8) + ((y&0x38)<<2)


def transition_routines(m,gfx):
    """One routine per distinct (third, old, new) tile transition in the
    stage map.  Each is called with HL = bank-5 pixel address of the cell,
    BC = hidden bank offset, and writes only what differs."""
    W=len(m[0])
    def tile(th,i): return gfx[th*2304+i*9:th*2304+i*9+9]
    pairs=sorted({(r>>3,m[r][c],m[r][(c+1)%W]) for c in range(W) for r in range(22) if m[r][c]!=m[r][(c+1)%W]})
    bodies={}; index={}
    for th,a,b in pairs:
        ta,tb=tile(th,a),tile(th,b)
        rows=[i for i in range(8) if ta[i]!=tb[i]]; at=ta[8]!=tb[8]
        if not rows and not at: index[(th,a,b)]=0; continue
        delta_t=sum(10 for r in rows)+4*(rows[-1] if rows else 0)+(65 if at else 0)
        if len(rows)<=2:
            body=[]; cur=0
            for r in rows:
                body+=['    inc h']*(r-cur)+['    ld (hl),0x%02x'%tb[r]]; cur=r
            if at: body+=['    call hl_to_attr','    ld (hl),0x%02x'%tb[8]]
            body+=['    ret']
        else:
            body=['    ld de,0x%02x%02x'%(0x5b+9*th,b),'    jp copy_de_hl']
        body='\n'.join(['    add hl,bc']+body)
        if body not in bodies: bodies[body]=len(bodies)+1
        index[(th,a,b)]=bodies[body]
    assert len(bodies)<256
    asm='\n'.join('pf_%d:\n%s'%(k,body) for body,k in bodies.items())
    return pairs,index,len(bodies),asm

def transition_tables(m,pairs,index,count,labels):
    W=len(m[0]); blob=bytearray(0x700)
    ids=[sorted({m[r][c] for r in range(a,z) for c in range(W)}) for a,z in ((0,8),(8,16),(16,22))]
    for th in range(3):
        for k,i in enumerate(ids[th]): blob[th*256+i]=k
    for k in range(1,count+1):
        addr=labels['pf_%d'%k]; blob[0x300+k]=addr&255; blob[0x400+k]=addr>>8
    for th in range(3):
        n=len(ids[th]); assert n<=64
        for co,a in enumerate(ids[th]):
            addr=0xc000+len(blob); blob[0x500+th*64+co]=addr&255; blob[0x600+th*64+co]=addr>>8
            blob+=bytes(index.get((th,a,b),0) for b in ids[th])
    assert len(blob)<=0x2000, len(blob)
    return bytes(blob)

def max_list_entries(m,index):
    W=len(m[0])
    return max(sum(1 for x in range(32) for r in range(22)
                   if m[r][(c+x)%W]!=m[r][(c+x+1)%W] and index[(r>>3,m[r][(c+x)%W],m[r][(c+x+1)%W])])
               for c in range(W))

def check_change_list_fits(m,gfx,labels):
    """Replay emit_change's byte layout for every stage-1 scroll step and
    prove the compiled list never overruns diff_code / diff_code2."""
    W=len(m[0]); worst=(0,0)
    def tile(r,i):
        th=r>>3; return gfx[th*2304+i*9:th*2304+i*9+9]
    for c in range(W):
        out=labels['diff_code']; end=labels['diff_code_end']; in_b=False
        for x in range(32):
            for r in range(22):
                a=m[r][(c+x)%W]; b=m[r][(c+x+1)%W]
                if a==b: continue
                ta,tb=tile(r,a),tile(r,b)
                rows=[i for i in range(8) if ta[i]!=tb[i]]
                if len(rows)>=3: n=9
                else:
                    n=(6+(rows[-1]-rows[0])+2*(len(rows)-1)) if rows else 0
                    if ta[8]!=tb[8]: n+=6
                out+=n
                if out+1>(0x8000 if in_b else end): raise ValueError('change list overflow at step %d: main area %d bytes, needs %d more'%(c,end-labels['diff_code'],out+1-(0x8000 if in_b else end)))
                if not in_b and out>=end-28:
                    out=0x7e00; in_b=True
        worst=max(worst,(out if in_b else 0, out if not in_b else 0))
    return worst

def ytab(bank):
    # Per screen row y: [pixel high byte, tile page, row low byte base, attribute high byte]
    return '\n'.join('    db 0x%02x,0x%02x,0x%02x,0x%02x'%(0x40|(y&0x18)|bank,0x5b+9*(y>>3),(y&7)<<5,0x58|(y>>3)|bank) for y in range(22))

def planar_tiles(gfx):
    assert len(gfx)==6912
    out=bytearray(6912)
    for third in range(3):
        for tid in range(256):
            for row in range(9):
                out[(third*9+row)*256+tid]=gfx[third*2304+tid*9+row]
    return bytes(out)

def snapshot(banks,pc=0x8000):
    # Standard extended 128K SNA: header, RAM banks 5/2/7, PC, 7FFD,
    # TR-DOS, then remaining banks 0/1/3/4/6. This maps bank 7 at C000.
    header=bytearray(27)
    header[15:17]=(0x5C3A).to_bytes(2,'little') # IY for Spectrum ROM IM1 interrupt
    header[19]=0                # interrupts off until entry sets up IM2
    header[23:25]=(0xbff0).to_bytes(2,'little')
    header[25]=1                # IM 1
    payload=bytes(header)+bytes(banks[5])+bytes(banks[2])+bytes(banks[7])
    payload+=pc.to_bytes(2,'little')+bytes([0x17,0])
    for b in (0,1,3,4,6):payload+=banks[b]
    assert len(payload)==131103,len(payload)
    return payload

def main():
    if len(sys.argv)!=2:sys.exit('usage: python tools/build.py <your MSX Nemesis ROM>')
    raw=Path(sys.argv[1]).read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=SHA:sys.exit(f'Wrong ROM hash: {digest}')
    n=Nemesis(sys.argv[1]);m=n.stage_map(1);v=n.stage_vram(1)
    gfx=tile_table(v)
    # Maximum sparse patch entries, over every start position including wrap.
    # The 512-byte list at 7600-77FF holds 2 bytes per changed character
    # plus a 0xFF terminator. Fail the build before silently overflowing it.
    most_changed=max(sum(m[row][(col+x)%456] != m[row][(col+x+1)%456]
                         for x in range(32) for row in range(22))
                     for col in range(456))
    assert 2*most_changed+1 <= 512, most_changed
    print('Original stage-1 maximum patch tiles:',most_changed)
    first=make_screen(m,gfx,START_COL)
    pix_lines='\n'.join('    dw '+','.join('0x%04x'%physical_pixel_addr(y) for y in range(i,min(i+8,192))) for i in range(0,192,8))
    attr_lines='\n'.join('    dw '+','.join('0x%04x'%(0x5800+32*y) for y in range(i,min(i+8,24))) for i in range(0,24,8))
    # Screen-independent scenery lives in the otherwise unused bank-5 RAM
    # immediately following its 6912-byte video area (5B00-75FF).
    stage_pix_lines='\n'.join('    dw '+','.join('0x%04x'%(0x5b00+physical_pixel_addr(y)-0x4000) for y in range(i,min(i+8,192))) for i in range(0,192,8))
    stage_attr_lines='\n'.join('    dw '+','.join('0x%04x'%(0x5b00+6144+32*y) for y in range(i,min(i+8,24))) for i in range(0,24,8))
    patch_rows=[]
    for row in range(22):
        screen_pixel=physical_pixel_addr(row*8)
        screen_attr=0x5800+row*32
        patch_rows.append('    dw '+','.join('0x%04x'%v for v in (0x5b00+screen_pixel-0x4000,screen_pixel,0x5b00+6144+row*32,screen_attr)))
    # The TMS9918 stores a 16x16 sprite as two 16-byte half-images.
    # Sprite pattern #2 is Konami's player ship (Vic Viper).
    raw_ship=v[0x1800+2*32:0x1800+3*32]
    ship=bytes(b for y in range(16) for b in (raw_ship[y],raw_ship[y+16]))
    ship_lines='\n'.join('    db '+','.join('0x%02x'%x for x in ship[i:i+8]) for i in range(0,len(ship),8))
    # The authentic normal bullet is NOT hardware sprite pattern 7.
    # Konami's 9E0A routine chooses one of four 8x8 characters (F8..FB).
    # Read bitmap rows from the original MSX VRAM tile pattern table.
    shot_chars=[bytes(v[0x2000+0xf8*8+8*i:0x2000+0xf8*8+8*(i+1)]) for i in range(4)]
    # All 64 ROM sprite patterns, stored in the same interleaved row format
    # accepted by the generic masked 16x16 Spectrum blitter.
    sprite_atlas=bytes(byte for pat in range(64)
                       for y in range(16)
                       for byte in (v[0x1800+pat*32+y], v[0x1800+pat*32+y+16]))
    assert len(sprite_atlas)==2048
    enemy_pattern_ids=(0x8c,0xb0,0xb4,0xb8)
    for pat in enemy_pattern_ids:
        index=pat//4
        raw_enemy=v[0x1800+index*32:0x1800+(index+1)*32]
        enemy=bytes(byte for y in range(16) for byte in (raw_enemy[y],raw_enemy[y+16]))
        if not any(enemy):raise ValueError('Missing ROM enemy sprite pattern %02X'%pat)
        (ROOT/'build').mkdir(exist_ok=True)
        (ROOT/'build'/('enemy_sprite_%02x.bin'%pat)).write_bytes(enemy)
    from original_stage1_events import parse
    (_, flyers, _)=parse(raw)['flying_enemies']
    assert len(flyers)==18
    script=bytes(b for event in flyers for b in
                 (event['distance']&255,event['distance']>>8,event['flags']))
    wave_script='\n'.join('    db '+','.join('0x%02x'%b for b in script[i:i+12])
                          for i in range(0,len(script),12))
    native_code,native_labels,native_audit,native_source=code_from_rom(raw)
    tr_pairs,tr_index,tr_count,tr_asm=transition_routines(m,gfx)
    source=(ROOT/'src/scroller.asm').read_text().replace('{NATIVE_ALLOC_ADDR}',f'0x{native_labels["native_type1_allocate"]:04x}').replace('{NATIVE_MOVE_ADDR}',f'0x{native_labels["native_type1_move"]:04x}') .replace('{NATIVE_TYPE0F_MOVE_ADDR}',f'0x{native_labels["native_type0f_move"]:04x}').replace('{NATIVE_FORMATION_ADDR}',f'0x{native_labels["native_formation"]:04x}').replace('{NATIVE_TYPE3_MOVE_ADDR}',f'0x{native_labels["native_type3_move"]:04x}').replace('{NATIVE_TYPE3_SPAWN_ADDR}',f'0x{native_labels["native_type3_pair_spawn"]:04x}').replace('{NATIVE_BLOB_SIZE}',str(len(native_code))).replace('{STAGE1_FLYING_EVENTS}',wave_script).replace('{PIX_ADDRS}',pix_lines).replace('{ATTR_ADDRS}',attr_lines).replace('{SHIP_BITMAP}',ship_lines).replace('{STAGE_PIX_ADDRS}',stage_pix_lines).replace('{STAGE_ATTR_ADDRS}',stage_attr_lines).replace('{PATCH_TILE_ADDRS}','\n'.join(patch_rows)).replace('{PAIR_ROUTINES}',tr_asm).replace('{PACE_PAL_MIX}','1' if os.environ.get('NEM_PACE')=='palmix' else '0').replace('{YTAB5}',ytab(0)).replace('{YTAB7}',ytab(0x80)).replace('{COL22}','    dw '+','.join(str(22*i) for i in range(33)))
    for i,graphic in enumerate(shot_chars):
        source=source.replace('{SHOT_CHAR_'+('F8','F9','FA','FB')[i]+'}', '    db '+','.join('0x%02x'%x for x in graphic))
    for pat in enemy_pattern_ids:
        enemy=(ROOT/'build'/('enemy_sprite_%02x.bin'%pat)).read_bytes()
        source=source.replace('{ENEMY_SPRITE_%02X}'%pat,as_db(enemy))
    equ_names=list(ORIGINAL_LABELS)
    source='\n'.join(name+' equ 0' for name in equ_names)+'\n'+source
    # Determine relocated destinations using blank placeholder bytes; then
    # generate machine-code bytes directly from the original ROM and resolve
    # ONLY documented original absolute references. No gameplay algorithms
    # are written or reconstructed by the porting tools.
    source=source.replace('{KONAMI_ENEMY_INTEGRATOR}',as_db(bytes(ORIGINAL_END-ORIGINAL_START)))
    type4_intervals={'{KONAMI_ENEMY_TYPE4_INIT}':12,'{KONAMI_ENEMY_TYPE4_MOVE}':70,'{KONAMI_ENEMY_VELOCITY_WRITER}':14}
    type4_fill={'{KONAMI_ENEMY_TYPE4_INIT}':0xA5,'{KONAMI_ENEMY_TYPE4_MOVE}':0xA6,'{KONAMI_ENEMY_VELOCITY_WRITER}':0xA7}
    for token,span in type4_intervals.items():source=source.replace(token,as_db(bytes([type4_fill[token]])*span))
    placeholders={'{KONAMI_MOVEMENT}':BLOCKS[0],'{KONAMI_FIRING}':BLOCKS[1],
                  '{KONAMI_HELPERS}':BLOCKS[2],'{KONAMI_SHOT_MOTION}':BLOCKS[3]}
    provisional=source
    for token,(_,start,end) in placeholders.items():
        provisional=provisional.replace(token,as_db(bytes(end-start)))
    _,prelabels=assemble(provisional)
    enemy_bytes,enemy_audit=extract_enemy_integrator(raw, prelabels['konami_enemy_integrator_blob'])
    enemy_type4,enemy_type4_audit=extract_type4(raw,{'init':prelabels['konami_enemy_type4_init_blob'],
        'move':prelabels['konami_enemy_type4_move_blob'],
        'velocity':prelabels['konami_enemy_velocity_writer_blob'],
        'enemy_fire_stub':prelabels['enemy_fire_not_yet_connected']})
    base={name:prelabels[{'shot_helpers':'konami_helpers_blob','shot_motion':'konami_shot_motion_blob'}.get(name,'konami_'+name+'_blob')] for name,_,_ in BLOCKS}
    extracted,patchlog,original_labels=make_rom_blocks(raw,base,prelabels['konami_sound_stub'],prelabels['konami_weapon_stub'])
    for key,address in original_labels.items():
        source=source.replace(key+' equ 0',key+' equ 0x%04x'%address)
    for token,(name,_,_) in placeholders.items():
        source=source.replace(token,as_db(extracted[name]))
    source=source.replace(as_db(bytes(ORIGINAL_END-ORIGINAL_START)),as_db(enemy_bytes))
    for token,key in [('{KONAMI_ENEMY_TYPE4_INIT}','init'),('{KONAMI_ENEMY_TYPE4_MOVE}','move'),('{KONAMI_ENEMY_VELOCITY_WRITER}','velocity')]:
        source=source.replace(as_db(bytes([type4_fill[token]])*type4_intervals[token]),as_db(enemy_type4[key]))
    code,labels=assemble(source)
    assert {key:labels[{'shot_helpers':'konami_helpers_blob','shot_motion':'konami_shot_motion_blob'}.get(name,'konami_'+name+'_blob')] for key,name in [('m','movement'),('f','firing'),('h','helpers'),('s','shot_motion')]}=={'m':base['movement'],'f':base['firing'],'h':base['shot_helpers'],'s':base['shot_motion']}
    for key,address in original_labels.items():labels[key]=address
    if len(code)>MAP_START-0x8000:raise ValueError('Code and address tables overlap the map')
    worst=max_list_entries(m,tr_index)
    area=labels['diff_code_end']-labels['diff_code']
    print('Transition routines:',tr_count,'; change list worst case',worst,'entries =',6*worst+1,'bytes of',area)
    if 6*worst+1>area: raise ValueError('change list area too small')
    pair_blob=transition_tables(m,tr_pairs,tr_index,tr_count,labels)
    print('Transition tables (bank 6):',len(pair_blob),'bytes')
    output=ROOT/'build';output.mkdir(exist_ok=True)
    images=ROOT/'images';images.mkdir(exist_ok=True)
    banks=[bytearray(BANK) for _ in range(8)]
    # Spectrum 128K fixed screen is bank 5 at address 0x4000.
    # Shadow screen is bank 7 at address 0xC000.
    banks[5][:6912]=first
    banks[7][:6912]=first
    # v0.29: planar tile set (page = third*9 + row, low byte = tile id)
    # lives in fixed RAM at 5B00; the sprite atlas at 7600.  Bank 0 keeps a
    # copy of the planar set only because make_tap reads NEMTILES from it.
    planar=planar_tiles(gfx)
    banks[0][:6912]=planar
    banks[5][0x1b00:0x1b00+6912]=planar
    banks[5][0x3600:0x3600+len(sprite_atlas)]=sprite_atlas
    banks[2][:len(code)]=code
    banks[1][:len(native_code)]=native_code
    banks[6][:len(pair_blob)]=pair_blob
    # Original map, transposed from map rows to sequential map columns.
    columns=bytes(m[row][col] for col in range(len(m[0])) for row in range(22))
    banks[2][MAP_START-0x8000:MAP_START-0x8000+len(columns)]=columns
    # v0.29: first two columns repeated after the end (BC30-BC5B) so sprite
    # erase rectangles never need a wrap check.
    banks[2][MAP_START-0x8000+len(columns):MAP_START-0x8000+len(columns)+44]=columns[:44]
    # The new rightmost column is the first unseen column after the initial view.
    initial_ptr=MAP_START+(START_COL+32)*22
    (output/'nemesis_stage1_scroll_128k.sna').write_bytes(snapshot(banks))
    from make_tap import build_tap,verify_tap
    from sprite_archive import compress, decompress
    archive=compress(sprite_atlas)
    assert decompress(archive)==sprite_atlas
    assert len(archive)<=1280, len(archive)
    tap=build_tap(banks,source,archive,native_code,pair_blob)
    verify_tap(tap)
    (output/'nemesis_stage1_scroll_128k.tap').write_bytes(tap)
    (output/'first_frame.scr').write_bytes(first)
    (output/'code.bin').write_bytes(code)
    (output/'native_bank1.bin').write_bytes(native_code)
    (output/'native_bank1_relocated.asm').write_text(native_source)
    (output/'native_relocations.txt').write_text('Konami type-1 relocations and Spectrum memory-interface patches\n'+''.join('%04X %04X -> %04X\n'%r for r in native_audit))
    (output/'tiles.bin').write_bytes(gfx)
    (output/'sprite_atlas.bin').write_bytes(sprite_atlas)
    (output/'sprite_atlas.rle').write_bytes(archive)
    (output/'stage1_map.bin').write_bytes(columns)
    (output/'vic_viper_16x16.bin').write_bytes(ship)
    for i,graphic in enumerate(shot_chars):
        (output/('normal_shot_char_%02x.bin'%(0xf8+i))).write_bytes(graphic)
    (output/'scroller_expanded.asm').write_text(source)
    (output/'konami_relocations.txt').write_text('Original MSX ROM bank 2 -> fixed Spectrum RAM: call/jump/table operands only\n'+''.join('%04X: %04X -> %04X\n'%r for r in patchlog)+'\nOriginal MSX bank 0 enemy velocity integrator (5F7C-5FA5):\n'+''.join('%04X: %04X -> %04X\n'%r for r in enemy_audit)+'\nOriginal type-4 enemy relocations:\n'+''.join('%s %04X: %04X -> %04X\n'%x for x in enemy_type4_audit))
    (output/'enemy_dispatch_table.tsv').write_text(enemy_dispatch_report(raw))
    (output/'enemy_integrator_original.bin').write_bytes(raw[ORIGINAL_START-0x4000:ORIGINAL_END-0x4000])
    (output/'enemy_integrator_relocated.bin').write_bytes(enemy_bytes)
    (output/'konami_original_blocks.bin').write_bytes(b''.join(raw[2*8192+start-0x8000:2*8192+end-0x8000] for _,start,end in BLOCKS))
    screen_to_png(first,images/'first_frame.png')
    print('Verified ROM sha256:',digest)
    print('Machine code at 8000:',len(code),'bytes; stage map at 9500:',len(columns),'bytes')
    print('Tile table in 128K bank 0:',len(gfx),'bytes; initial scene starts at map column',START_COL)
    print('Original Konami movement/firing transplants:', len(patchlog),'explicit relocations')
    print('Snapshot written:', output/'nemesis_stage1_scroll_128k.sna')
    print('Tape (auto-loading):', output/'nemesis_stage1_scroll_128k.tap')
    print('Z80 snapshot entry=',hex(labels['entry']),'tape entry=',hex(labels['tape_entry']), 'map=',hex(MAP_START), 'data/code gap=',MAP_START-0x8000-len(code))

if __name__=='__main__':main()
