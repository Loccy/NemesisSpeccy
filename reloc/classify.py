"""Classify every 16-bit value in MSX banks 0-3 for relocation.

Output: per-bank list of (item addr, operand kind, value, decision, text).
Decisions:
  ram       Konami RAM address (E000-F0FF)       -> relocate to fixed RAM
  rom       code/data address in a game bank       -> symbolic label (+offset)
  mapper    LD (6000/8000/A000),A                  -> paging call
  bios      call/jp into 0000-3FFF                 -> Spectrum shim
  biosvar   LD A,(0006/0007) etc                   -> shim variable
  hook      MSX system area (FCxx-FFxx RAM)        -> dummy RAM
  const     plain number                           -> unchanged
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import re, sys, collections
from listing import parse

RAM_LO, RAM_HI = 0xE000, 0xF0FF

def window_bank(v, ctx=(0, 1, 2, 3)):
    if v < 0x6000: return 0
    if v < 0x8000: return ctx[1]
    if v < 0xA000: return ctx[2]
    return ctx[3]

def classify_value(kind, v, text):
    if kind in ('jp16', 'call16'):
        return 'bios' if v < 0x4000 else 'rom'
    if kind == 'abs16':
        if v in (0x6000, 0x8000, 0xA000) and text.replace(' ', '').startswith('ld(') and text.endswith(',a'):
            return 'mapper'
        if RAM_LO <= v <= RAM_HI: return 'ram'
        if v < 0x4000: return 'biosvar'
        if v >= 0xF100: return 'hook'
        return 'rom'
    if kind == 'imm16':
        if RAM_LO <= v <= RAM_HI: return 'ram'
        if 0x4000 <= v < 0xC000: return 'rom?'
        return 'const'
    return None

if __name__ == '__main__':
    rom = open(NEM_ROOT + '/nem.rom', 'rb').read()
    totals = collections.Counter(); review = []
    for b in range(4):
        items, labels, raw = parse(b, rom)
        org = 0x4000 if b == 0 else 0x6000 + (b - 1) * 0x2000
        for it in items:
            if it[2] != 'code' or it[5] is None: continue
            a, n, _, text, comment, kind = it
            v = raw[a - org + n - 2] | raw[a - org + n - 1] << 8
            d = classify_value(kind, v, text.lower())
            totals[(kind, d)] += 1
            if d in ('rom?',) or (d == 'rom' and kind == 'abs16') or d in ('biosvar', 'hook'):
                review.append((b, a, kind, v, d, text, comment[:60]))
    for k, n in sorted(totals.items(), key=str): print(k, n)
    print('\nreview list (%d):' % len(review))
    for r in review: print('  bank %d %04X %-6s %04X %-7s %-28s %s' % r)
