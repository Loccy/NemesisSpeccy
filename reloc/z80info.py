"""Z80 instruction length and 16-bit operand kind, for relocation.

Every Z80 instruction that carries a 16-bit immediate or address carries it
in its last two bytes.  kind is one of:
  'imm16'  LD rr,nn / LD IX,nn / LD IY,nn   (pointer or plain number)
  'abs16'  LD (nn),r / LD r,(nn) forms        (always an address)
  'jp16'   JP nn / JP cc,nn                    (code address)
  'call16' CALL nn / CALL cc,nn                (code address)
  None     no 16-bit operand
"""
LD_R_N = {0x06, 0x0E, 0x16, 0x1E, 0x26, 0x2E, 0x36, 0x3E}
ALU_N = {0xC6, 0xCE, 0xD6, 0xDE, 0xE6, 0xEE, 0xF6, 0xFE}
REL = {0x10, 0x18, 0x20, 0x28, 0x30, 0x38}
IO_N = {0xD3, 0xDB}
IMM16 = {0x01, 0x11, 0x21, 0x31}
ABS16 = {0x22, 0x2A, 0x32, 0x3A}
JP16 = {0xC3, 0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA, 0xF2, 0xFA}
CALL16 = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
HL_MEM = {0x34, 0x35, 0x46, 0x4E, 0x56, 0x5E, 0x66, 0x6E, 0x7E,
          0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x77,
          0x86, 0x8E, 0x96, 0x9E, 0xA6, 0xAE, 0xB6, 0xBE}
ED_ABS = {0x43, 0x4B, 0x53, 0x5B, 0x63, 0x6B, 0x73, 0x7B}

def base(op):
    if op in IMM16:
        return 3, 'imm16'
    if op in ABS16:
        return 3, 'abs16'
    if op in JP16:
        return 3, 'jp16'
    if op in CALL16:
        return 3, 'call16'
    if op in LD_R_N or op in ALU_N or op in REL or op in IO_N or op == 0xCB:
        return 2, None
    return 1, None

def info(read, a):
    """read(addr) -> byte.  Returns (length, kind)."""
    op = read(a)
    if op == 0xED:
        o2 = read(a + 1)
        return (4, 'abs16') if o2 in ED_ABS else (2, None)
    if op in (0xDD, 0xFD):
        o2 = read(a + 1)
        if o2 == 0xCB:
            return 4, None
        if o2 == 0x21:
            return 4, 'imm16'
        if o2 in (0x22, 0x2A):
            return 4, 'abs16'
        if o2 == 0x36:
            return 4, None
        if o2 in HL_MEM:
            return 3, None
        if o2 in (0xDD, 0xFD, 0xED):
            return 1, None                       # prefix acts alone
        n, kind = base(o2)
        return 1 + n, kind
    return base(op)
