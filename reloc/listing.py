"""Parse antxiko's Nemesis listing into a byte-exact code/data map per bank.

For each bank: a list of items (addr, size, kind, text, comment) where kind is
'code', 'defb' or 'defw'.  Checks the items tile the 8KB bank exactly and that
code lengths agree with the Z80 decoder.  Also returns the label table.
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import re
from z80info import info

SRC = NEM_ROOT + '/ref/Nemesis-disassembly/src/nemesis_p%02d.asm'
ORG = {0: 0x4000, 1: 0x6000, 2: 0x8000, 3: 0xA000, 4: 0x6000, 5: 0x8000, 6: 0xA000,
       7: 0x8000, 8: 0xA000, 9: 0x8000, 10: 0xA000, 11: 0x8000, 12: 0xA000,
       13: 0x8000, 14: 0xA000, 15: 0xA000}

def parse(bank, rom):
    org = ORG[bank]
    raw = rom[bank * 8192:(bank + 1) * 8192]
    read = lambda a: raw[a - org] if org <= a < org + 8192 else 0
    items = []; labels = {}
    for line in open(SRC % bank, encoding='latin1'):
        m = re.match(r'([A-Za-z_][\w]*):\s*equ\s+0x([0-9a-fA-F]+)', line)
        if m:
            labels[m.group(1)] = int(m.group(2), 16); continue
        m = re.match(r'([A-Za-z_][\w]*):', line)
        pending_label = m.group(1) if m else None
        code, _, comment = line.partition(';')
        text = code.strip()
        if pending_label:
            text = text[len(pending_label) + 1:].strip() if text.startswith(pending_label + ':') else text
        if not text or text.startswith('org'):
            if pending_label:
                labels.setdefault(pending_label, None)
                items.append(('label', pending_label))
            continue
        am = re.match(r'\s*([0-9a-fA-F]{4})\b', comment)
        if not am:
            raise ValueError('no address on line: ' + line)
        addr = int(am.group(1), 16)
        if pending_label:
            labels[pending_label] = addr
        rest = comment[am.end():]
        if text.startswith('defb'):
            n = len(text[4:].split(','))
            items.append((addr, n, 'defb', text, rest.strip()))
        elif text.startswith('defw'):
            n = 2 * len(text[4:].split(','))
            items.append((addr, n, 'defw', text, rest.strip()))
        else:
            n, kind = info(read, addr)
            items.append((addr, n, 'code', text, rest.strip(), kind))
    # Resolve labels defined on their own line to the next item's address.
    out = []; waiting = []
    for it in items:
        if it[0] == 'label':
            waiting.append(it[1]); continue
        for w in waiting:
            labels[w] = it[0]
        waiting = []
        out.append(it)
    # Tiling check.
    pos = org
    for it in out:
        if it[0] != pos:
            raise ValueError('bank %d: gap/overlap at %04X (item at %04X: %s)' % (bank, pos, it[0], it[3]))
        pos += it[1]
    if pos != org + 8192:
        raise ValueError('bank %d ends at %04X' % (bank, pos))
    return out, labels, raw

if __name__ == '__main__':
    rom = open(NEM_ROOT + '/nem.rom', 'rb').read()
    for b in range(4):
        items, labels, _ = parse(b, rom)
        code = sum(i[1] for i in items if i[2] == 'code')
        print('bank %d: %d items, %d code bytes, %d data bytes, %d labels'
              % (b, len(items), code, 8192 - code, len(labels)))
