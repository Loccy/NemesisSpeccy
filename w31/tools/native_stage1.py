"""Native ROM-derived Konami stage-one enemy routines in RAM bank 1 at C000.

Preserve byte-exact original instructions, adjusting the address operands
necessary because the Spectrum does not map the MSX's four ROM banks at
their original addresses. The type-1 caller uses a direct call to the original type-1 constructor
instead of MSX RST-based cross-bank indexed dispatch. The type-03 flying fish
are also transplanted, together with the type-0F formation experiment.
The rest of Konami's enemy systems have not all been implemented.
"""
from konami import as_db
from mini_asm import assemble

ROM_ORIGIN={0:0x4000,1:0x6000,2:0x8000,3:0xA000}
SEGMENTS=(
 ('native_type1_allocate',1,0x6A72,0x6B46),
 ('native_random',1,0x6B84,0x6B97),
 ('native_random_table',1,0x6B97,0x6BA3),
 ('native_templates',1,0x6BA3,0x6C23),
 ('native_type1_init',1,0x6C23,0x6C3F),
 ('native_type1_move',2,0x9119,0x91C5),
 ('native_speed_table',2,0x91C5,0x9205),
 ('native_aim_patterns',2,0x9205,0x9235),
 ('native_scroll_check',2,0x9251,0x9264),
 ('native_aim_calc',1,0x66D5,0x6729),
 ('native_aim_table',1,0x6753,0x6853),
 ('native_bullet_fire',1,0x6613,0x6677),
 ('native_bullet_velocity',1,0x6677,0x66D5),
 ('native_negate',1,0x6729,0x6731),
 ('native_fixed_multiply',1,0x6731,0x674F),
 ('native_velocity_table',1,0x6853,0x6893),
 ('native_type0f_init',1,0x6C77,0x6CA6),
 ('native_type0f_move',1,0x71AD,0x71C7),
 ('native_accel_add',2,0x953C,0x9550),
 ('native_formation',1,0x70D6,0x7189),
 ('native_formation_tables',1,0x7189,0x71AD),
 ('native_table_word',0,0x47AE,0x47B7),
 # Konami's genuine flying type-03 fish pair (bank 3) and its type-specific state.
 ('native_type3_init',3,0xA821,0xA836),
 ('native_type3_move',3,0xA836,0xA84F),
 ('native_type3_frames',3,0xA84F,0xA857),
 ('native_type3_pair_spawn',3,0xA438,0xA46F),
 ('native_type3_aim',3,0xA49C,0xA4A6),
 ('native_type3_variant',3,0xA5B8,0xA5D7),
 ('native_set_horizontal_vel',1,0x6CBF,0x6CC6),
 ('native_set_vertical_vel',1,0x6CC6,0x6CCC),
 ('native_type3_fire_timer',2,0x9235,0x9251),
 ('native_type3_vel_helpers',2,0x9519,0x953C),
 ('native_type3_add_vel_y',2,0x9550,0x9564),
 ('native_type3_sprite_anim',2,0x95D1,0x95EB),
)

# Addresses of genuine absolute operands in original Konami instruction
# stream. No fuzzy disassembler matching: missing/out-of-range target fails.
PATCHES_OPCODES={
 0x6A86:0x6A98, 0x6AF5:0x6BA3, 0x6B21:0x6B84,0x6B43:'native_alloc_dispatch',
 0x6B88:0x6B97, 0x6C23:0x9181,
 0x9119:0x9251,0x9123:0x66D5,0x9141:0x9205,
 0x9144:'native_hl_plus_a',0x914B:'native_hl_plus_a',
 0x917E:0x6613,0x9181:0x91C5,0x9195:'native_hl_plus_a',0x91A0:'native_hl_plus_a',
 0x925F:'native_retire_type1',
 0x6708:0x6753,0x670B:'native_hl_plus_a',
 0x662C:0x6677,0x6640:'native_hl_plus_a',
 0x6677:0x66D5,0x66A6:0x6853,0x66B4:0x6731,0x66BB:0x6729,
 0x66C6:0x6731,0x66CD:0x6729,
 0x6735:0x6743,
 0x71AD:0x953C,0x71C0:'native_background_collision_stub',0x71C4:'native_collision_terminate',
 0x7102:'native_sound_stub',0x7105:0x711C,0x7108:0x713C,
 0x7113:'native_type1_allocate',0x7122:0x7189,0x712A:0x47AE,
 0x7141:0x718D,0x7144:0x47AE,0x714F:0x6729,
  0x715F:'native_compare_stage1',0x7181:0x6729,
 # Exact type-03 constructor / behaviour / animation dependencies.
 0xA824:0x6CBF, 0xA827:0x9530,0xA82D:0x6CC6,0xA833:0x9522,
 0xA836:0x9235,0xA839:0xA846,0xA83C:0x953C,
 0xA83F:'native_type3_compare_vel',0xA842:0x9519,
 0xA849:0xA84F,0xA84C:0x95D1,
 0xA447:0xA49C,0xA44A:0xA5B8,0xA462:0x6A72,0xA46C:0x6A72,
 0xA5C2:'native_hl_plus_a',
 0x924B:0x6613,0x924E:0x6B84,
 0x951F:0x6729,0x9532:0x6729,


}
# 6B43 CALL 4067 originally invokes MSX's indexed dispatch through the
# inline table at 6B46. Here only type-1 events are dispatched, and the
# direct Konami 6C23 constructor is substituted. 6B46 is made a RET.
# The original A = type - 1 (=0 for type1) remains unmodified.

TAIL='''
native_hl_plus_a:
    ld e,a
    ld d,0
    add hl,de
    ret
native_alloc_dispatch:
    ld a,(0xe120)
    cp 1
    jp z,native_type1_init
    cp 15
    jp z,native_type0f_init
    cp 3
    jp z,native_type3_init
    ret
native_type3_compare_vel:
    ld e,(ix+7)
    ld d,(ix+8)
    ld a,d
    or a
    call m,native_negate
    ; Original 9564 comparison: absolute first velocity against second.
    ld l,(ix+25)
    ld h,(ix+26)
    or a
    sbc hl,de
    ret
native_sound_stub:
    ret
native_background_collision_stub:
    xor a
    ret
native_collision_terminate:
    xor a
    ld (ix+0),a
    ret
native_compare_stage1:
    ld de,0x00a5
    or a
    sbc hl,de
    ret
native_retire_type1:
    xor a
    ld (ix+0),a
    ld hl,0xe126
    db 0x35
    ret
'''

def code_from_rom(rom):
    spans=[]
    for name,bank,start,end in SEGMENTS:
        offset=bank*8192+(start-ROM_ORIGIN[bank]); block=bytearray(rom[offset:offset+end-start])
        if len(block)!=end-start:raise ValueError(name)
        spans.append((name,bank,start,end,block))
    src='org 0xc000\n'
    for name,_,_,_,block in spans:
        src+=name+':\n'+as_db(bytes(len(block)))+'\n'
        if name=='native_type1_allocate':src+='native_allocator_return:\n    ret\n'
    src+=TAIL
    _,labels=assemble(src,base=0xC000)
    origmap={start+n:labels[name]+n for name,_,start,end,_ in spans for n in range(end-start)}
    audit=[]
    contents={}
    for name,bank,start,end,blob in spans:
        for opcode_site,target in PATCHES_OPCODES.items():
            site=opcode_site+1
            if not start<=site<end:continue
            pos=site-start
            before=int.from_bytes(blob[pos:pos+2],'little')
            if isinstance(target,int):
                assert before==target,(hex(site),hex(before),hex(target))
                destination=origmap[target]
            else:
                assert (opcode_site==0x6B43 and before==0x4067) or (before==0x405D and target=='native_hl_plus_a') or (before==0x5FA5 and target=='native_retire_type1') or (before==0x405D and target=='native_hl_plus_a') or (before==0x9564 and target=='native_type3_compare_vel') or (opcode_site==0x71C0 and before==0x9857) or (opcode_site==0x71C4 and before==0x72D2) or (opcode_site==0x7102 and before==0x71C7) or (opcode_site==0x715F and before==0x00A5) or (opcode_site==0x7113 and before==0x6A72),(hex(site),hex(before),target)
                destination=labels[target]
            blob[pos:pos+2]=destination.to_bytes(2,'little')
            audit.append((site,before,destination))
        if name=='native_formation':
            assert blob[0x715F-start]==0x11
            blob[0x715F-start]=0xCD
            assert blob[0x7162-start]==0xE7
            blob[0x7162-start]=0x00
        contents[name]=bytes(blob)
    final='org 0xc000\n'
    for name,_,_,_,_ in spans:
        final+=name+':\n'+as_db(contents[name])+'\n'
        if name=='native_type1_allocate':final+='native_allocator_return:\n    ret\n'
    final+=TAIL
    payload,actual_labels=assemble(final,base=0xC000)
    assert actual_labels==labels
    assert len(payload)<0x2000
    return payload,labels,audit,final
