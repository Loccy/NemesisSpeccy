"""ROM-derived Nemesis graphics and map extraction.

Adaptation of algorithms and addresses documented in antxiko/Nemesis-disassembly
(see README for source acknowledgement); the original ROM is not included.
"""
from pathlib import Path

BANK_ORIGINS = {0:0x4000, 1:0x6000, 4:0x6000,
                2:0x8000,5:0x8000,7:0x8000,9:0x8000,11:0x8000,
                3:0xA000,6:0xA000,8:0xA000,10:0xA000,12:0xA000}
GFX = {0x6000:4,0x8000:5,0xA000:6}
MAP = {0x8000:11,0xA000:12}
TMS = [(0,0,0),(0,0,0),(33,200,66),(94,220,120),(84,85,237),
       (125,118,252),(212,82,77),(66,235,245),(252,85,84),(255,121,120),
       (212,193,84),(230,206,128),(33,176,59),(201,91,186),(204,204,204),(255,255,255)]

class Nemesis:
    def __init__(self, path):
        self.rom = Path(path).read_bytes()
        if len(self.rom) != 0x20000: raise ValueError('ROM must be exactly 128 KB')
    def u8(self, bank, address):
        pos = (address - BANK_ORIGINS[bank])
        if not (0 <= pos < 0x2000): raise ValueError('bank boundary: %d:%04X' %(bank,address))
        return self.rom[bank*0x2000+pos]
    def u16(self, bank, address):
        return self.u8(bank,address)|self.u8(bank,address+1)<<8
    @staticmethod
    def bank_for(address,layout):
        if address < 0x6000: return 0
        return layout[address & 0xE000]
    def decompress(self, vram, bank, address, dst):
        """Replay 0x49B9, respecting the active MSX 8KB graphics windows.

        Some compressed streams cross 0x7FFF -> 0x8000, so the bank must
        be selected for each source address, not frozen to its first bank.
        """
        p=address
        def get_byte():
            nonlocal p
            value=self.u8(self.bank_for(p,GFX),p)
            p+=1
            return value
        while True:
            cmd=get_byte()
            if cmd == 0: return
            if cmd == 0x80:
                dst=get_byte() | (get_byte()<<8)
                continue
            if cmd & 0x80:
                count=cmd&0x7F
                for _ in range(count):
                    vram[dst&0x3FFF]=get_byte()
                    dst+=1
            else:
                value=get_byte()
                for _ in range(cmd):
                    vram[dst&0x3FFF]=value
                    dst+=1
    def load_records(self,vram,pointer):
        bank=self.bank_for(pointer,GFX)
        while True:
            flags=self.u8(bank,pointer)
            if not flags: return
            patterns=self.u16(bank,pointer+1)
            char=self.u8(bank,pointer+3)
            colours=self.u16(bank,pointer+4)
            for bit,base in ((0,0x1000),(1,0x800),(2,0)):
                if flags & 1<<bit:
                    self.decompress(vram,self.bank_for(patterns,GFX),patterns,0x2000+char*8+base)
                    self.decompress(vram,self.bank_for(colours,GFX),colours,char*8+base)
            pointer+=6
    def mirror(self, vram, table, stage, vertical):
        """Replay Konami 0x433F-0x4498 on MSX character tables.

        Mirror records are FOUR bytes: source character, target character,
        source/destination third flags, number of consecutive characters.
        Earlier code incorrectly read (count, 16-bit source, dest), corrupting
        the original VRAM. 0x4450 selects one source third; 0x4408 may write
        to several destination thirds. Horizontal mirrors flip pattern bits
        only; vertical mirrors reverse rows of BOTH patterns and colours.
        """
        bank = self.bank_for(table, GFX)
        pointer = self.u16(bank, table + 2 * stage)
        bank = self.bank_for(pointer, GFX)
        while True:
            source = self.u8(bank, pointer)
            if source == 0:
                return
            target = self.u8(bank, pointer + 1)
            flags = self.u8(bank, pointer + 2)
            count = self.u8(bank, pointer + 3)
            # The original routine tests bit 2, then bit 1, otherwise third.
            source_third = 0 if flags & 0x04 else (1 if flags & 0x02 else 2)
            src = source_third * 0x800 + source * 8
            size = count * 8
            # Konami reads both tables into E300/E700 BEFORE mirroring.
            patterns = bytearray(vram[0x2000+src:0x2000+src+size])
            colours = bytearray(vram[src:src+size])
            if vertical:
                for i in range(0, size, 8):
                    patterns[i:i+8] = patterns[i:i+8][::-1]
                    colours[i:i+8] = colours[i:i+8][::-1]
            else:
                patterns = bytearray(int(f'{value:08b}'[::-1], 2) for value in patterns)
            for dest_third, bit in ((0,0x20),(1,0x10),(2,0x08)):
                if flags & bit:
                    dst = dest_third*0x800+target*8
                    vram[0x2000+dst:0x2000+dst+size] = patterns
                    vram[dst:dst+size] = colours
            pointer += 4
    def stage_loaded_vram(self,stage=1):
        """The untouched stage graphics immediately after RLE loads, before
        the two mirror-table transforms. Keep this for provenance debugging.
        """
        vram=bytearray(0x4000)
        self.load_records(vram,0x932D)
        self.load_records(vram,self.u16(5,0x92E3+2*stage))
        return vram

    def stage_vram(self,stage=1):
        vram=bytearray(0x4000)
        self.load_records(vram,0x932D)
        self.load_records(vram,self.u16(5,0x92E3+2*stage))
        self.mirror(vram,0x92FB,stage,False)
        self.mirror(vram,0x9313,stage,True)
        self.decompress(vram, self.bank_for(0x86BB,GFX),0x86BB,0x1800)
        # The stage's synthetic star characters use F6/F7 only.
        # F8 is the FIRST NORMAL SHOT glyph (F8-FB), not starfield data.
        # Replacing its first row with 0x10 puts a stray pixel above shots.
        for ch in (0xF6,0xF7):
            for third in range(3): vram[0x2000+third*0x800+ch*8] = 0x10
        return vram
    def stage_limits(self,stage):
        base=0x4499+6*stage
        return self.u16(0,base),self.u16(0,base+2)
    def stage_map(self,stage=1):
        start,finish=self.stage_limits(stage)
        if start==0xFFFF: width,start,finish=256,1,0
        else: width=finish+0x28
        output=[[0]*width for _ in range(22)]
        script=self.u16(11,0x97DE+2*stage)
        piece_base=0x8FF0 if stage in (5,9,10,12) else 0x8000
        for d in range(width):
            if start<=d<=finish:
                column=[]
                offset=((d-start)//4)*6
                for n in range(6):
                    piece=self.u8(self.bank_for(script+offset+n,MAP),script+offset+n)
                    base=piece_base+piece*16+((d-start)&3)
                    for row in range(2 if n==5 else 4):
                        column.append(self.u8(self.bank_for(base+4*row,MAP),base+4*row))
            else:
                column=[0]*22
                r=self.u8(0,0x478E+(d&31))
                if 1<=r<=22: column[r-1]=0xF6
            for r in range(22): output[r][d]=column[r]
        return output
    @staticmethod
    def msx_tile(vram,ch,third):
        ix=third*0x800+ch*8
        out=[]
        for r in range(8):
            pattern=vram[0x2000+ix+r]
            attr=vram[ix+r]
            ink, paper=attr >> 4, attr&15
            out.extend(ink if pattern&(128>>x) else paper for x in range(8))
        return out
