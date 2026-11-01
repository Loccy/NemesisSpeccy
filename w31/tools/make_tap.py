"""Build a standard-ROM-loader 128K Spectrum tape image (.tap).

BASIC loads bank 2 (code plus map), screen 5, then a temporary tile table
to fixed bank 5 above RAMTOP. Only after ALL LOAD calls have finished does
the machine-code entry page bank 0 and transfer the tiles there. This avoids
changing the BASIC paging setup in the middle of the ROM tape loader.
Tape layout follows standard Spectrum header and checksum format.
"""
import functools
from pathlib import Path
from mini_asm import assemble
from build import ROOT

# Standard Sinclair BASIC keyword tokens.
TOK = {'CLEAR':0xFD,'VAL':0xB0,'LOAD':0xEF,'CODE':0xAF,
       'RANDOMIZE':0xF9,'USR':0xC0}

def token(tok):return bytes([TOK[tok]])
def q(num):return b'"'+str(num).encode('ascii')+b'"'

def bas_line(number,content):
    data=content+b'\r'
    return number.to_bytes(2,'big')+len(data).to_bytes(2,'little')+data

def block(data,flag):
    body=bytes([flag])+data
    checksum=functools.reduce(lambda a,b:a^b,body,0)
    body+=bytes([checksum])
    return len(body).to_bytes(2,'little')+body

def header(name,content,length_param,secondary,typ):
    h=bytes([typ])+name.encode('ascii')[:10].ljust(10,b' ')+len(content).to_bytes(2,'little')
    h+=length_param.to_bytes(2,'little')+secondary.to_bytes(2,'little')
    assert len(h)==17
    return block(h,0)+block(content,255)

def build_tap(banks,source,sprite_archive=None,native_code=None,pair_blob=None):
    _,labels=assemble(source)
    bootstrap=labels['tape_entry']
    # Reserve 0x6000-0x7AFF for the temporary tiles, with the BASIC stack
    # under 0x6000. All three data blocks are loaded without paging calls.
    clear=token('CLEAR')+b' '+token('VAL')+b' '+q(24575)
    load=token('LOAD')+b' "" '+token('CODE')
    usr=lambda n: token('RANDOMIZE')+b' '+token('USR')+b' '+token('VAL')+b' '+q(n)
    line=clear+b':'+load+b':'+load+b':'+usr(labels['native_tape_loader'])+b':'+load+b':'+usr(labels['pairs_tape_loader'])+b':'+load+b':'+load+b':'+load+b':'+usr(bootstrap)
    program=bas_line(10,line)
    tape=header('NEMESIS128',program,10,len(program),0)
    tape+=header('NEMCODE',bytes(banks[2]),0x8000,0x8000,3)
    assert native_code is not None and 0<len(native_code)<0x2000
    tape+=header('NEMNATIVE',native_code,0x6000,0x8000,3)
    assert pair_blob is not None and len(pair_blob)<=0x2000
    tape+=header('NEMPAIRS',pair_blob,0x6000,0x8000,3)
    # Keep the screen last: its data overwrites the ROM loader's Bytes: banner,
    # leaving the scrolling frame pristine when the machine-code entry runs.
    tape+=header('NEMTILES',bytes(banks[0][:6912]),0x6000,0x8000,3)
    assert sprite_archive is not None and len(sprite_archive)<=1280
    tape+=header('NEMSPR',sprite_archive,0x7b00,0x8000,3)
    tape+=header('NEMSCREEN',bytes(banks[5][:6912]),0x4000,0x8000,3)
    return tape

def verify_tap(data):
    i=0;flags=[]
    while i<len(data):
        ln=int.from_bytes(data[i:i+2],'little');i+=2
        pkt=data[i:i+ln];i+=ln
        assert len(pkt)==ln and functools.reduce(lambda a,b:a^b,pkt,0)==0
        flags.append(pkt[0])
    assert i==len(data) and flags==[0,255]*7,flags

if __name__=='__main__':
    print('Import this module from tools/build.py; it needs the generated RAM bank images.')
