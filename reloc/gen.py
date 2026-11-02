"""Generate relocated Konami game code for the Spectrum 128K layout.

MSX banks 0-3 (game code) and 7 (sound driver) are regenerated from
antxiko's listing with every address symbolic (label m<bank>_<addr> on every
item), so code may grow (RST 20h -> CALL) and items may move.  Banks 4, 5, 8
and 11 are placed raw.  Konami RAM E000-F0FF moves by RAM_DELTA.

Each item has a home section:
  fixed   MSX bank 0 at 5B00 (+ the 8-byte loop tail from bank 1 at 6000)
  fixed2  data moved out of a full page (fixed RAM overflow area)
  A       MSX 1 at C000, MSX 2 after it, + bank 3's A000-A021 laser tail
  C       MSX 3 (rest) at C000
  D       MSX 7 at C000 (sound driver), MSX 8 data at E000
  B, E    data pages (4+5, 11)
Calls/jumps between different pages go through far stubs that page the
target, call it, and restore the previous page on return.

identity=True emits everything at original addresses with no rewrites; it
must reassemble to the ROM byte for byte (regression check of the parser).
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import bisect, collections, os
from listing import parse

# 'sim': layout simulator (MSX hardware stubs).  'spec': the real Spectrum build.
TARGET = os.environ.get('NEM_TARGET', 'sim')

RAM_LO, RAM_HI = 0xE000, 0xF0FF
RAM_DELTA = -0x3100
ORG = {0: 0x4000, 1: 0x6000, 2: 0x8000, 3: 0xA000, 7: 0x8000}
# MSX data bank -> (Spectrum page, address there, MSX window it is used at).
# Banks used together in one mapper configuration share a page with a single
# displacement, so pointer arithmetic inside the data still works:
#   (4,5,6) graphics/fichas  6000->C000, 8000->E000   (+0x6000; bank 6 is empty)
#   (7,8)   sound            8000->C000, A000->E000   (+0x4000)
#   (9,10)  title graphics   8000->C000, A000->E000   (+0x4000)
#   (11,12) map pieces/guiones 8000->C000, A000->E000 (+0x4000)
DATA_PLACE = {4: ('B', 0xC000, 0x6000), 5: ('B', 0xE000, 0x8000),
              8: ('D', 0xE000, 0xA000),
              9: ('F', 0xC000, 0x8000), 10: ('F', 0xE000, 0xA000),
              11: ('E', 0xC000, 0x8000), 12: ('E', 0xE000, 0xA000)}
# Bytes of each data bank actually emitted (default: all 8KB).
DATA_RANGE = {}
if TARGET == 'spec':
    # Banks 9/10/12 share page E (24 Oct).  With no attract cycle (no demo,
    # no illustration) bank 12 is only read at A000-A2A7 (whole-game census,
    # spec/bankreads.py), so its space after that holds bank 10's used part
    # (A000-AF28: the title's second block, the end-of-loop explosion
    # graphics, the stage 5/6 boss's pieces) and the part of bank 9 the title
    # reads (9B3F-9FFF).  The code that reads bank 10 from bank 2 (8290-839E)
    # moves to page E with it (ITEM_MOVES).
    # The title's compressed stream runs on from bank 9 into bank 10, so the
    # two stay contiguous (one displacement, +0x4769).
    DATA_PLACE[9] = ('E', 0xC769, 0x8000)          # 9B3F -> E2A8 .. 9FFF -> E768
    DATA_PLACE[10] = ('E', 0xE769, 0xA000)         # A000 -> E769 .. AF28 -> F691
    DATA_RANGE[9] = (0x9B3F, 0xA000)
    DATA_RANGE[10] = (0xA000, 0xAF29)
    DATA_RANGE[12] = (0xA000, 0xA2A8)
    # Bank 5 from 98B9 on is never read here: 98B9-9BE3 is what the game loads
    # only when it finds TwinBee (RC-740) in another slot (0xF0F4, set by
    # 0:505A; the port's RDSLT answers FF, so it never does), and 9BE4-9FFF is
    # FF padding.  Its place in page B (F8B9-FFFF) takes the colour fit.
    DATA_RANGE[5] = (0x8000, 0x98B9)
# Parts of a data bank emitted away from the bank's own placement, each with
# its own displacement: bank -> [(first, end, section, Spectrum address)].
# Pointers into them (data tables, code operands) are given the piece's
# address (place_data).  DATA_SKIP: ranges inside DATA_RANGE not emitted, whose
# room the pieces may use.  DATA_ALIAS: an operand that is a table's base
# declared some bytes before the table (0:5D95's ld hl,0xB2D2 for the table at
# B2E4, read with indices 9-12) moves with the table.
DATA_PIECES = {}
DATA_SKIP = {}
DATA_ALIAS = {}
if TARGET == 'spec':
    # The bonus stages (9-12) read, in bank 12, their scripts (A2D8, A428,
    # A578, A668; the four guiones that tabla_de_guiones, 11:97DE, points at)
    # and tabla_de_finales with the records it points at (B2E4-B64B; B649-B64B
    # is padding the last record's reader runs onto).  Measured on the MSX
    # original with every target touched; nothing else they read is missing.
    # They go in page E's gaps: bank 10's records-screen part (A758-AAA5: the
    # high-score table's frame, sprites and code, part of the attract cycle,
    # never shown here), and the room the colour fit left (F692-FB03) and its
    # cache (FC13-FFFF).
    DATA_SKIP[10] = [(0xA758, 0xAAA6)]                 # -> E769+0x758 = EEC1 .. F20E
    DATA_PIECES[12] = [(0xA2D8, 0xA428, 'E', 0xEEC1),  # stage 9's script
                       (0xA578, 0xA668, 'E', 0xF011),  # stage 11's
                       (0xA668, 0xA878, 'E', 0xF692),  # stage 12's
                       (0xA428, 0xA578, 'E', 0xF8A2),  # stage 10's
                       (0xB2E4, 0xB64C, 'E', 0xFC13)]  # tabla_de_finales and its records
    DATA_ALIAS[(12, 0xB2D2)] = 0xB2E4

def place_data(bank, v):
    """Spectrum address of MSX address v of data bank `bank`."""
    for lo, hi, sec, base in DATA_PIECES.get(bank, ()):
        if lo <= v < hi: return base + v - lo
    if (bank, v) in DATA_ALIAS:
        a = DATA_ALIAS[(bank, v)]
        return place_data(bank, a) - (a - v)
    sec, base, org = DATA_PLACE[bank]
    return base + v - org
# Pointer words inside raw data banks, relocated in the placed copy.
#   ('words', bank, first, count, config): plain word table
#   ('fichas', bank, start, config): 6-byte entries, pointers at +1 and +4, ends at a 0 byte
# config maps an MSX window base to the bank seen there when the data is used.
CFG_456 = {0x6000: 4, 0x8000: 5, 0xA000: 6}
CFG_1112 = {0x8000: 11, 0xA000: 12}
DATA_PTRS = [('words', 5, 0x92E3, 37, CFG_456),          # listas_de_fichas_A/B/C
             ('fichas', 5, 0x932D, CFG_456),             # fichas_comunes
             ('fichas', 5, 0x938E, CFG_456),             # fichas_extra_1
             ('fichas', 5, 0x939B, CFG_456),             # fichas_extra_2
             ('fichas', 5, 0x98A3, CFG_456),             # fichas_del_disparador
             ('fichas_from_table', 5, 0x92E3, 13, CFG_456),  # fichas_por_fase (table A only; B/C lead to 4-byte mirror lists).
             # 13: stage 12 reads table A's 13th word, which is table B's first (9689, phase 0's
             # mirror list, never used as one): it is read as stage 12's fichas, the bricks.
             ('words', 11, 0x97DE, 13, CFG_1112),        # tabla_de_guiones
             ('words', 12, 0xB2E4, 4, CFG_1112),         # tabla_de_finales (bonus stages)
             ('words', 10, 0xAAA6, 45, {0xA000: 10})]    # the boss pieces' drawings (AAA6, AAB0)
# Word tables inside regenerated banks whose entries are pointers: (bank, first
# word, count[, stride[, cfg]]).  Target bank from the value (default mapping,
# bank 7/8 for the sound bank) unless cfg is given.  Found by auditing every
# table read through dame_palabra / renglon_del_guion (tables.py) and the
# pointer words the original dereferences in stage 1 (trace/confirm_all.py).
CODE_PTRS = [(7, 0x8328, 80),             # tabla_de_sonidos: sound number -> stream
             (0, 0x4EDA, 6),              # tabla_del_medidor
             (0, 0x4FEA, 5),              # tablas_de_4C4B: lap captions
             (0, 0x5163, 14),             # textos_por_fase
             (0, 0x5D1F, 8),              # finales_por_fase (bank 3 targets)
             (0, 0x42B3, 24, 3, CFG_456), # graficos_por_fase: (bank-5 source, char) x2 per phase
             (1, 0x633A, 3),              # tabla_633A
             (1, 0x6370, 16),             # trayectorias (defb)
             (1, 0x64FC, 11),             # tabla_64FA, phases 1-11 (defb)
             (1, 0x7058, 12),             # tabla_7056
             (2, 0x8B4C, 14),             # tabla_8B4C
             (2, 0x9264, 12),             # tabla_9264
             (2, 0x99E5, 3),              # tabla_99E3, states 1-3 (defb)
             (2, 0x9A27, 3),              # tabla_9A25 (defb)
             (2, 0x9A69, 3),              # tabla_9A67 (defb)
             (2, 0x9BD2, 4),              # tabla_9BD2
             (3, 0xA3A8, 8),              # tabla_A3A6
             (3, 0xB537, 24),             # tabla_B537
             (3, 0xB749, 8)]              # tabla_B749
# Data the pointer tables above point AT: byte rows, never pointers, whatever
# the listing's defw formatting or '->' annotations suggest.
NOT_PTR_RANGES = [(1, 0x6390, 0x64D4),    # trayectorias rows
                  (1, 0x6512, 0x65DC),    # tabla_64FA rows
                  (1, 0x7070, 0x70CA),    # tabla_7056 rows
                  (2, 0x8B68, 0x8CE4),    # tabla_8B4C rows
                  (2, 0x927C, 0x9510),    # tabla_9264 rows (distance, byte)
                  (3, 0xA3B8, 0xA438),    # tabla_A3A6 rows
                  (3, 0xB567, 0xB729),    # tabla_B537 rows
                  (3, 0xB759, 0xB7BF)]    # tabla_B749 rows

# Spectrum-only replacements: the hardware boundary.
SPEC_PATCH = {
    (0, 0x4072): ['    im 2'],                       # INIT's im 1: the Spectrum keeps IM 2 (vector table at AD00)
    (0, 0x40DF): ['    jp plat_main'],               # INIT's endless jr $: the platform main loop takes over
    (0, 0x47FE): ['    jp plat_upload_map'],         # sube_la_pantalla: ED00 -> name-table shadow
    (0, 0x47C8): ['    inc hl', '    dec b'],          # sprite attribute uploads: the renderer reads EC80 itself
    (0, 0x47EF): ['    inc hl', '    dec b'],
    (0, 0x47E7): ['    ret'],
    (0, 0x47CE): ['    call spr_upload'],     # an upload shows the sprites again (after quita_los_sprites)
    (0, 0x475B): ['    jp blink_native'],            # parpadea_dos_caracteres: star tile rows, done natively
    (0, 0x49B9): ['    jp descomprime_native'],      # the graphics decompressor, through a buffer
    # No Konami logo and no attract cycle (demo, illustration): straight to the
    # 1/2 player select, which waits there (Paul, 24 Oct; frees banks 9/10/12 space).
    (0, 0x52D9): ['    jp spec_title'],              # estado_0 sub 1: the title (and the controls) instead of the logo
    (0, 0x5308): ['    jp title_tick'],              # estado_1: the attract cycle's tune, looped on the title (0.102)
    (0, 0x537F): ['    jp title_end'],               # estado_3 (the game starting): the title's tune stopped (0.102)
    (0, 0x530F): ['    jp m0_5BD3'],                 # estado_1: keep blinking the choice, never the attract cycle
    (3, 0xA6C0): ['    call dz_mark'],               # apaga_la_pantalla, the screen dissolve: noted for the renderer (0.107)
    (3, 0xA765): ['    jp dz_chunk'],                # come_un_trozo, one chunk of the dissolve, done natively (0.107)
    # di that only matter on the MSX (see 'mapper di' in emit_item): before the
    # sound request's pushes (the queue itself, 4A02-4A11, keeps its di), and
    # around RDPSG, which here reads the keyboard cache, not the AY.
    (0, 0x49DE): ['    nop'],
    (0, 0x49E9): ['    nop'],
    (0, 0x57B6): ['    nop'],
}
for _a in (0x49CD, 0x49D7, 0x567D, 0x5691, 0x5697, 0x56D2, 0x58F7, 0x5BA9):
    SPEC_PATCH[(0, _a)] = ['    call vdp_out_a']   # out (c),a to the VDP data port
# Writes into Konami's map buffer (ED00-EFBF), found by a census of 30,000
# ticks, and on 24 Oct by censuses through every stage with each weapon
# (spec/census.py, census_check.py).  Each drawing routine notes the region it writes (cell, width,
# rows) in nm_list, mostly by taking over a 3-byte instruction next to the
# write so that page A (MSX 1+2, nearly full) does not grow, and sube_la_pantalla compares just those regions.
# The big copies (start-up, a new game or stage, the scroll's column shift)
# ask for a full comparison instead, and plat_upload_map makes one every 64
# ticks anyway in case a writer was missed.
NM_SITES = {
    'nm_ldir_full': [(0, 0x40AE), (0, 0x5563), (0, 0x4159), (3, 0xA74F)],   # A74F: limpia_el_buffer
    'nm_ldi31_full': [(0, 0x46A1)],                 # the scroll's column shift: 31 bytes a row
    'nm_r21_hl_c': [(0, 0x48F1)],                   # dos_caracteres
    'nm_rect_ld_e_b': [(0, 0x48FA)],                # borra_un_rectangulo, after the clip
    'nm_rect_sub_b': [(0, 0x4911)],                 # copia_un_rectangulo, after the clip
    'nm_69e1': [(1, 0x69E1)],                       # dibuja_dos_por_dos: ld h,(ix+1F), then 2x2 at HL
    'nm_6a5b': [(1, 0x6A5B)],                       # copia_cuatro_por_cuatro: call 571B, then 4x4 at HL
    'nm_902e': [(2, 0x902E)],                       # dibuja_una_de_las_cinco: 2x2 at DE, ld hl,905C
    'nm_9051': [(2, 0x9051)],                       # dibuja_uno_solo: 1x1 at DE, ld hl,8FE4
    'nm_r22_de_ldi': [(0, 0x48CF), (2, 0x909F)],    # dos_por_dos, borra_una_de_las_cinco
    'nm_9fe0': [(2, 0x9FE0), (3, 0xA008)],          # rompe_la_casilla, and the laser breaking a cell: 1x1 at DE, call 49DE
    'nm_r11_de_a': [(3, 0xA2A7), (3, 0xA2F1)],      # the shots
    'nm_r11_hl_a': [(0, 0x4756), (0, 0x471D), (0, 0x4724), (0, 0x472B), (0, 0x4732)],  # stars, new column
    'nm_751d': [(1, 0x751D)],                       # an object turned into an explosion: its 2x2 cleared, call 571B
    'nm_87cf': [(2, 0x87CF)],                       # escribe_dos_caracteres (stage 7 boss): EE5B and the cell below
    'nm_laser_w': [(3, 0xA2BE)],                    # escribe_la_tira_del_laser: B cells at DE
    'nm_laser_e': [(3, 0xA307)],                    # devuelve_lo_del_laser: C cells at DE (ldir)
}
for _h, _ss in NM_SITES.items():
    for _s in _ss:
        SPEC_PATCH[_s] = ['    call ' + _h]

# Spectrum Next only (assembled under NEXT; the Spectrum build keeps the
# instruction or its SPEC_PATCH entry): calls into nx_low.asm's jump table at
# 0100, each the same size as what it replaces, so both builds keep one
# layout.  Each still runs Konami's own instruction or routine.
NEXT_PATCH = {
    (0, 0x46A1): ['    call 0x0118'],    # the scroll's row moves: lo_shiftrow (Layer 2's circular buffer), not nm_ldi31_full
    (2, 0x9251): ['    call 0x0106'],    # se_corre_con_el_scroll_ocho's ld a,(E100): lo_gnd notes the object, then does it
    (0, 0x4100): ['    call 0x011B'],    # carga_los_graficos_de_la_fase (new game): lo_stage, then the MSX2 graphics
    (0, 0x414B): ['    call 0x011B'],    # the same (each stage)
    (0, 0x5851): ['    call 0x011E'],    # carga_el_marcador's ld de,5906: lo_marcador (TMS9918 colours back), then it
    (0, 0x544F): ['    call 0x0121'],    # the screen before each stage (0:53C8), its call to 0:5874: lo_prestage, the stage's colours and status line
}
# What Konami has at each of them (checked when generating, so a moved or
# changed site stops the build instead of being overwritten).
NEXT_PATCH_WAS = {
    (0, 0x46A1): 'edb0', (2, 0x9251): '3a00e1', (0, 0x4100): 'cd2a42',
    (0, 0x414B): 'cd2a42', (0, 0x5851): '110659', (0, 0x544F): 'cd7458',
}

# Relative jumps that the patches above push out of range: emitted as jp.
JR_LONG = set([(0, 0x46B7)])

# Test builds only: Konami's randomness (ld a,r) from a fixed sequence, the same
# one the simulators use, so the Spectrum build can be compared tick by tick.
LD_A_R = [(0, 0x4750), (0, 0x4CDA), (0, 0x4CFF), (0, 0x4D20), (0, 0x4D28), (1, 0x6685), (1, 0x6B90),
          (1, 0x6C9C), (1, 0x713C), (1, 0x7E13), (2, 0x811F), (2, 0x8243), (2, 0x846F), (2, 0x8769),
          (2, 0x8B06), (3, 0xA453), (3, 0xAAE6), (3, 0xABC2), (3, 0xB016), (3, 0xBC59), (3, 0xBDBE),
          (3, 0xBDF5)]
if os.environ.get('NEM_PIN_R') == '1':
    for _s in LD_A_R:
        SPEC_PATCH[_s] = ['    call pinned_r']

# Calls made from the top of Konami's per-tick call list (un_cuadro_de_juego
# and corre_los_sprites, both in bank 0, only ever reached from bank 0 code):
# nothing above them needs its page back, so these far calls map the target's
# page and leave it mapped.
NORESTORE_SITES = [(0x4532, 0x45F4), (0x47B7, 0x47BC)]

# Routines copied into other sections, so that callers there run a local copy
# that reads the caller's own tables (bank 3 passes anima_en_redondo tables
# from bank 3, which is not paged in with bank 2), or simply so that frequent
# calls from there need no page switch: uno_de_cada_treinta_y_dos and
# le_toca_moverse (95A0-95D0), and choca_con_el_mapa_3 (9897-98AB), called
# from bank 3 about 5 times a tick in play; none reads bank 2 data.
# (bank, first, last) -> sections.
CLONES = {(2, 0x95A0, 0x95EA): ['C'], (2, 0x9897, 0x98AB): ['C']}

# Replacement text for single items (non-identity build only).
ITEM_PATCH = {
    # Sound stream 0xFE (repeat) target: MSX 8000-BFFF lives at C000-FFFF.
    # Same size as the original 4 bytes, so the sound data after the driver
    # stays at exactly MSX address + 0x4000.
    (7, 0x8015): ['    call snd_fe_hi'],
    (7, 0x8016): ['    nop'],
    # direccion_en_el_mapa: the map buffer's high byte as an 8-bit immediate.
    (0, 0x572B): ['    add a,0x%02X' % ((0xED + (RAM_DELTA >> 8)) & 0xFF)],
    # pinta_una_casilla_del_medidor indexes its table as 56D1 + 8 * box (box
    # from 1, so the data starts at 56D9).  56D1 is code, and the out (c),a
    # patch at 56D2 grows it, so the base is taken from the data instead.
    (0, 0x56B6): ['    db 0x11', '    dw m0_56D9-8'],
    # presentacion: 0x6200 is a VRAM address (2200 with bit 14 set), not a
    # pointer into bank 1.
    (0, 0x5A57): ['    ld hl,0x6200'],
    # The end of "CONTINUE F5": the Spectrum's continue key is C (tables.py).
    (0, 0x584D): ['    db 0x00,0x23,0x00,0xFF'],
}
BANK_SECTION = {0: 'fixed', 1: 'A', 2: 'A', 3: 'C', 7: 'D'}
# (bank, first, last) -> section, emitted right after bank `after`'s own items
ITEM_MOVES = [((1, 0x6000, 0x6007), 'fixed', 0), ((3, 0xA000, 0xA021), 'A', 2)]
if TARGET == 'spec':      # the boss pieces' drawing and turrets, with bank 10 in page E
    ITEM_MOVES.append(((2, 0x8290, 0x839E), 'E', 2))
DATA_MOVES = [(1, 0x7EE6, 88)]          # -> fixed2

# Immediates that look like addresses but are numbers (BCD scores, X/Y positions, ...).
CONST_IMM = {0xA45E, 0xA467,   # ld de,0xF030 / 0xF060: entry X,Y of a formation
             0x55D1, 0x5742, 0x4C66, 0x703F, 0x76A0, 0x508D, 0xA8CB, 0xA908, 0x879E,
             0x8776,       # ld hl,0xA440: the stage 7 boss's shot start (Y 40, X A4)
             0x8799,       # ld de,0x5F60: the stage 7 boss's two characters (as 879E)
             0x4C93}       # ld de,0x504A: the ship's position after the end-of-loop explosion (Y 4A, X 50)
UNPLACED_IMM = set()
# Operand sites (bank 0) whose 16-bit value refers to a bank other than the
# normal (1,2,3) mapping.  From the runtime trace (trace/sitetrace.py) plus the
# listing comments for sites stage 1 does not execute.
# Operand sites given a platform symbol instead (MSX system variables).
IMM_SYMBOL = {0x40EB: 'hook_FCC1'}      # EXPTBL: slot expansion flags
SITE_BANK = {0x4A49: 7, 0x4035: 7, 0x48CB: 5, 0x46F2: 11, 0x4708: 11, 0x46C3: 11,
             0x424C: 5, 0x42FC: 5, 0x4306: 5, 0x4316: 5, 0x4320: 5, 0x432B: 5, 0x4337: 5,
             0x4284: 5, 0x4293: 5, 0x4A86: 5, 0x4A92: 5,
             0x53F3: 4, 0x53FC: 4, 0x5405: 4, 0x540E: 4, 0x5417: 4, 0x5420: 4,
             0x4B14: 10, 0x4B1D: 10, 0x4B26: 10,
             0x5B50: 9, 0x5B59: 9, 0x5B93: 9, 0x5B98: 9,
             0x5C12: 9, 0x5C1B: 9, 0x5C24: 9, 0x5C2D: 9, 0x5C36: 9, 0x5C3F: 9, 0x5C66: 9,
             0x5C48: 10, 0x5C51: 10, 0x5C5A: 10, 0x5C60: 10,
             0x5D95: 12,
             0x82CC: 10, 0x82D1: 10, 0x831B: 10, 0x834F: 10}   # the boss pieces' tables

def default_bank(v):
    if v < 0x6000: return 0
    if v < 0x8000: return 1
    if v < 0xA000: return 2
    return 3

class Gen:
    def __init__(self, rom, identity=False):
        self.rom = rom; self.identity = identity
        self.items = {}; self.labels = {}; self.raw = {}; self.starts = {}
        for b in (0, 1, 2, 3, 7):
            it, lab, raw = parse(b, rom)
            self.items[b] = it; self.labels[b] = lab; self.raw[b] = raw
            self.starts[b] = [i[0] for i in it]
        self.labelled = {b: set(v for v in self.labels[b].values() if v is not None) for b in self.labels}
        self.home = {}
        for b in self.items:
            for it in self.items[b]:
                self.home[(b, it[0])] = BANK_SECTION[b]
        if not identity:
            for (b, lo, hi), sec, _ in ITEM_MOVES:
                for it in self.items[b]:
                    if lo <= it[0] <= hi: self.home[(b, it[0])] = sec
            for b, lo, ln in DATA_MOVES:
                for it in self.items[b]:
                    if lo <= it[0] < lo + ln: self.home[(b, it[0])] = 'fixed2'
        self.stubs = {}; self.nstubs = {}; self.report = collections.Counter()
        self.reloc_words = set()      # (bank, addr) of data words given a relocated value
        self.code_ptrs = {}
        for e in CODE_PTRS:
            b, a, n = e[:3]; stride = e[3] if len(e) > 3 else 2; cfg = e[4] if len(e) > 4 else None
            for i in range(n): self.code_ptrs[(b, a + i * stride)] = cfg

    def item_of(self, bank, v):
        st = self.starts[bank]
        return st[bisect.bisect_right(st, v) - 1]

    def sym(self, bank, v):
        if bank in DATA_PLACE:
            return '0x%04X' % (v if self.identity else place_data(bank, v))
        a = self.item_of(bank, v)
        return 'm%d_%04X' % (bank, a) if a == v else 'm%d_%04X+%d' % (bank, a, v - a)

    def page_of(self, bank, v):
        if bank in DATA_PLACE: return DATA_PLACE[bank][0]
        sec = self.home[(bank, self.item_of(bank, v))]
        return 'fixed' if sec in ('fixed', 'fixed2') else sec

    def ram(self, v):
        return '0x%04X' % (v + (0 if self.identity else RAM_DELTA))

    def clone_label(self, bank, v, cur_sec):
        if self.identity: return None
        for (cb, lo, hi), secs in CLONES.items():
            if cb == bank and lo <= v <= hi and cur_sec in secs and v == self.item_of(bank, v):
                return '%s_m%d_%04X' % (cur_sec, bank, v)
        return None

    def target(self, bank, v, cur_sec, site):
        tb = SITE_BANK.get(site, bank)
        cl = self.clone_label(tb, v, cur_sec)
        if cl: self.report['clone call'] += 1; return cl
        s = self.sym(tb, v)
        if self.identity: return s
        tp = self.page_of(tb, v)
        cp = 'fixed' if cur_sec in ('fixed', 'fixed2') else cur_sec
        if tp != 'fixed' and any(lo <= site <= hi for lo, hi in NORESTORE_SITES):
            name = 'nfar_' + s.replace('+', '_')
            self.nstubs[name] = (tp, s); self.report['far no-restore'] += 1
            return name
        if tp != 'fixed' and tp != cp:
            name = 'far_' + s.replace('+', '_')
            self.stubs[name] = (tp, s); self.report['far'] += 1
            return name
        return s

    def emit_item(self, b, it, sec, out):
        raw = self.raw[b]; org = ORG[b]; I = self.identity
        a, n = it[0], it[1]
        if not I and TARGET == 'spec' and (b, a) in NEXT_PATCH and not getattr(self, 'in_next', False):
            was = raw[a - org:a - org + n].hex()
            assert was == NEXT_PATCH_WAS[(b, a)], 'Next hook %d:%04X is %s, not %s' % (b, a, was, NEXT_PATCH_WAS[(b, a)])
            spec = []
            self.in_next = True
            self.emit_item(b, it, sec, spec)
            self.in_next = False
            out.append(spec[0])                     # the label
            out.append('    ifdef NEXT')
            out += NEXT_PATCH[(b, a)]
            out.append('    else')
            out += spec[1:]
            out.append('    endif')
            self.report['next patched'] += 1
            return
        byts = raw[a - org:a - org + n]
        out.append('m%d_%04X:' % (b, a))
        if not I and b == 1 and a == 0x7FFE:
            out.append('    ld hl,' + self.sym(2, 0x8041)); out.append('    jp m2_8001'); return
        if it[2] in ('defb', 'defw') and not I and any((b, x) in self.code_ptrs for x in range(a - 1, a + n)):
            parts = []; i = 0
            while i < n:
                if (b, a + i) in self.code_ptrs:
                    assert i + 1 < n, 'pointer word straddles items at %d:%04X' % (b, a + i)
                    v = byts[i] | byts[i + 1] << 8
                    parts.append(('dw', self.code_ptr_value(b, a + i, v))); i += 2
                    self.report['table ptr'] += 1; self.reloc_words.add((b, a + i - 2))
                else:
                    assert (b, a + i - 1) not in self.code_ptrs or i > 0
                    parts.append(('db', '0x%02X' % byts[i])); i += 1
            k = 0
            while k < len(parts):
                kind = parts[k][0]; j = k
                while j < len(parts) and parts[j][0] == kind: j += 1
                out.append('    %s %s' % (kind, ','.join(p[1] for p in parts[k:j]))); k = j
            return
        if not I and (b, a) in ITEM_PATCH:
            out += ITEM_PATCH[(b, a)]; self.report['patched'] += 1; return
        if it[2] == 'defb':
            out.append('    db ' + ','.join('0x%02X' % x for x in byts)); return
        if not I and TARGET == 'spec' and (b, a) in SPEC_PATCH:
            out += SPEC_PATCH[(b, a)]; self.report['spec patched'] += 1; return
        if not I and TARGET == 'spec' and it[2] == 'code' and n == 1 and byts[0] == 0xF3 and self.di_for_mapper(b, a):
            # Konami's di around a mapper write keeps its interrupt (which pages
            # banks 7/8 and back from F0F2/F0F3) from seeing the two disagree.
            # The Spectrum's interrupt restores the paging port itself
            # (port_now), and its interrupt is a short pulse that a di loses
            # outright (the MSX's waits until acknowledged): so no di.
            out.append('    nop'); self.report['mapper di'] += 1; return
        if it[2] == 'defw' and not I and any(nb == b and lo <= a < hi for nb, lo, hi in NOT_PTR_RANGES):
            out.append('    db ' + ','.join('0x%02X' % x for x in byts)); self.report['not ptr rows'] += 1; return
        if it[2] == 'defw':
            ann = '->' in it[4]; ws = []
            for i in range(0, n, 2):
                v = byts[i] | byts[i + 1] << 8
                if RAM_LO <= v <= RAM_HI and ann:
                    ws.append(self.ram(v)); self.report['dw ram'] += 1; self.reloc_words.add((b, a + i))
                elif 0x4000 <= v < 0xC000 and (ann or v in self.labelled.get(default_bank(v), ())):
                    ws.append(self.word_ptr(b, sec, default_bank(v), v)); self.report['dw ptr'] += 1; self.reloc_words.add((b, a + i))
                else:
                    ws.append('0x%04X' % v)
            out.append('    dw ' + ','.join(ws)); return
        kind = it[5]; op = byts[0]
        if b == 7:
            if kind is None:
                out.append('    db ' + ','.join('0x%02X' % x for x in byts)); return
            v = byts[-2] | byts[-1] << 8
            if 0x8000 <= v < 0xA000: s = self.sym(7, v)
            elif 0xA000 <= v < 0xC000: s = self.sym(8, v)
            elif RAM_LO <= v <= RAM_HI: s = self.ram(v)
            elif v < 0x4000 and kind in ('jp16', 'call16'): s = ('0x%04X' % v) if I else 'bios_%04X' % v
            else: s = '0x%04X' % v
            out.append('    db ' + ','.join('0x%02X' % x for x in byts[:-2])); out.append('    dw ' + s); return
        if op == 0xE7 and not I:
            out.append('    call dcompr'); self.report['rst20'] += 1; return
        if op in (0x10, 0x18, 0x20, 0x28, 0x30, 0x38):
            d = byts[1] - 256 if byts[1] > 127 else byts[1]
            t = a + 2 + d
            tb = b if ORG[b] <= t < ORG[b] + 8192 else default_bank(t)
            tsec = self.home[(tb, self.item_of(tb, t))]
            if (tsec == sec or I) and (I or TARGET != 'spec' or (b, a) not in JR_LONG):
                mn = {0x10: 'djnz ', 0x18: 'jr ', 0x20: 'jr nz,', 0x28: 'jr z,', 0x30: 'jr nc,', 0x38: 'jr c,'}[op]
                out.append('    %s%s' % (mn, self.sym(tb, t)))
            else:
                s = self.target(tb, t, sec, a); self.report['rel->abs'] += 1
                if op == 0x10:
                    out += ['    djnz $+4', '    jr $+5', '    jp %s' % s]
                elif op == 0x18:
                    out.append('    jp %s' % s)
                else:
                    cc = {0x20: 'nz', 0x28: 'z', 0x30: 'nc', 0x38: 'c'}[op]
                    out.append('    jp %s,%s' % (cc, s))
            return
        if kind is None:
            out.append('    db ' + ','.join('0x%02X' % x for x in byts)); return
        v = byts[-2] | byts[-1] << 8
        pre = 'db ' + ','.join('0x%02X' % x for x in byts[:-2])
        if kind in ('jp16', 'call16'):
            if v < 0x4000:
                s = ('0x%04X' % v) if I else 'bios_%04X' % v; self.report['bios'] += 1
            else:
                s = self.target(default_bank(v), v, sec, a)
        elif kind == 'abs16':
            if v in (0x6000, 0x8000, 0xA000) and op == 0x32 and not I:
                out.append('    call map_%04x' % v); self.report['mapper'] += 1; return
            if RAM_LO <= v <= RAM_HI: s = self.ram(v); self.report['ram'] += 1
            elif v < 0x4000: s = ('0x%04X' % v) if I else 'bios_var_%04X' % v
            elif v >= 0xF100: s = ('0x%04X' % v) if I else 'hook_%04X' % v
            else: s = self.sym(SITE_BANK.get(a, default_bank(v)), v); self.report['abs rom'] += 1
        else:
            if not I and a in IMM_SYMBOL: s = IMM_SYMBOL[a]
            elif a in CONST_IMM: s = '0x%04X' % v; self.report['imm const'] += 1
            elif RAM_LO <= v <= RAM_HI: s = self.ram(v); self.report['imm ram'] += 1
            elif 0x4000 <= v < 0xC000 and a not in CONST_IMM and a not in UNPLACED_IMM:
                s = self.sym(SITE_BANK.get(a, default_bank(v)), v); self.report['imm ptr'] += 1
            else:
                s = '0x%04X' % v; self.report['imm const'] += 1
        out.append('    ' + pre); out.append('    dw ' + s)

    def di_for_mapper(self, b, a):
        """The di at (b, a) guards a mapper write: one within the next four
        instructions, before any ei or call."""
        items = self.items[b]; st = self.starts[b]
        i = bisect.bisect_right(st, a) - 1
        org = ORG[b]; raw = self.raw[b]
        for it in items[i + 1:i + 5]:
            if it[2] != 'code': return False
            bs = raw[it[0] - org:it[0] - org + it[1]]
            if bs[0] in (0xFB, 0xCD, 0xF3): return False
            if bs[0] == 0x32 and len(bs) == 3 and (bs[1] | bs[2] << 8) in (0x6000, 0x8000, 0xA000): return True
        return False

    def is_code(self, bank, v):
        if bank not in self.items: return False
        st = self.starts[bank]; i = bisect.bisect_right(st, v) - 1
        return i >= 0 and self.items[bank][i][0] == v and self.items[bank][i][2] == 'code'

    def word_ptr(self, b, sec, tb, v):
        """A data word pointing at (tb, v).  Jump-table entries for code in
        another page go through a far stub: the table's reader jumps with
        whatever page is mapped, and the stub maps the right one."""
        if self.identity or not self.is_code(tb, v): return self.sym(tb, v)
        tp = self.page_of(tb, v)
        if tp == 'fixed': return self.sym(tb, v)
        cp = 'fixed' if sec in ('fixed', 'fixed2') else sec
        if cp == 'fixed' or tp != cp:
            s = self.sym(tb, v); name = 'far_' + s.replace('+', '_')
            self.stubs[name] = (tp, s); self.report['far table'] += 1
            return name
        return self.sym(tb, v)

    def code_ptr_value(self, b, a, v):
        cfg = self.code_ptrs[(b, a)]
        if cfg is not None:
            nv = self.data_ptr(v, cfg)
            if nv is None and 0x4000 <= v < 0x6000:
                return self.sym(0, v)       # bank 0 (graficos_por_fase's empty block, 0:42FB, for stages 9-12)
            return '0x%04X' % (v if nv is None else nv)
        if not (0x4000 <= v < 0xC000): return '0x%04X' % v
        vb = (7 if v < 0xA000 else 8) if b == 7 else default_bank(v)
        return self.sym(vb, v)

    def data_ptr(self, v, cfg):
        """Relocate pointer v seen under mapper config cfg, or None if not one."""
        w = v & 0xE000
        if w not in cfg or cfg[w] not in DATA_PLACE: return None
        return place_data(cfg[w], v)

    def placed_data(self):
        out = {b: bytearray(self.rom[b * 8192:(b + 1) * 8192]) for b in DATA_PLACE}
        done = set()
        def fix(b, a, cfg):
            if (b, a) in done: return
            org = DATA_PLACE[b][2]; d = out[b]; o = a - org
            v = self.rom[b * 8192 + o] | self.rom[b * 8192 + o + 1] << 8
            nv = self.data_ptr(v, cfg)
            if nv is None: return
            d[o] = nv & 255; d[o + 1] = nv >> 8; done.add((b, a)); self.report['data ptr'] += 1
            self.reloc_words.add((b, a))
        def word(b, a):
            o = a - DATA_PLACE[b][2]
            return self.rom[b * 8192 + o] | self.rom[b * 8192 + o + 1] << 8
        def fichas(b, a, cfg):
            org = DATA_PLACE[b][2]
            while org <= a < org + 8192 and self.rom[b * 8192 + a - org] != 0:
                fix(b, a + 1, cfg); fix(b, a + 4, cfg); a += 6
        for e in DATA_PTRS:
            if e[0] == 'words':
                _, b, a, n, cfg = e
                for i in range(n): fix(b, a + 2 * i, cfg)
            elif e[0] == 'fichas':
                _, b, a, cfg = e
                fichas(b, a, cfg)
            elif e[0] == 'fichas_from_table':
                _, b, a, n, cfg = e
                for i in range(n):
                    v = word(b, a + 2 * i)
                    if cfg.get(v & 0xE000) == b: fichas(b, v, cfg)
        return out

    def generate(self, path):
        I = self.identity
        if I:
            out = []
            for b in (0, 1, 2, 3, 7):
                out.append('    output "%s_bank%d.bin"' % (path[:-4], b))
                out.append('    org 0x%04X' % ORG[b])
                for it in self.items[b]:
                    self.emit_item(b, it, BANK_SECTION[b], out)
            open(path, 'w').write('\n'.join(out) + '\n'); return
        sections = collections.OrderedDict((k, []) for k in ('fixed', 'A', 'C', 'D', 'fixed2', 'E'))
        for b in (0, 1, 2, 3, 7):
            for it in self.items[b]:
                sec = self.home[(b, it[0])]
                if sec != BANK_SECTION[b]: continue
                self.emit_item(b, it, sec, sections[sec])
            for (mb, lo, hi), sec, after in ITEM_MOVES:
                if after == b:
                    for it in self.items[mb]:
                        if lo <= it[0] <= hi: self.emit_item(mb, it, sec, sections[sec])
        for b, lo, ln in DATA_MOVES:
            for it in self.items[b]:
                if lo <= it[0] < lo + ln: self.emit_item(b, it, 'fixed2', sections['fixed2'])
        import re as _re
        for (cb, lo, hi), secs in CLONES.items():
            for sec in secs:
                body = []
                for it in self.items[cb]:
                    if lo <= it[0] <= hi: self.emit_item(cb, it, sec, body)
                pat = _re.compile(r'\bm%d_([0-9A-F]{4})\b' % cb)
                def ren(m):
                    v = int(m.group(1), 16)
                    return '%s_m%d_%04X' % (sec, cb, v) if lo <= v <= hi else m.group(0)
                sections[sec].append('; clone of MSX bank %d %04X-%04X' % (cb, lo, hi))
                sections[sec] += [pat.sub(ren, l) for l in body]
        out = []
        for sec, body in sections.items():
            out.append('\n; ===== section %s =====' % sec)
            out.append('    section_%s' % sec)
            out += body
            out.append('section_%s_end:' % sec)
        for b, data in self.placed_data().items():
            sec, base, org = DATA_PLACE[b]
            lo, hi = DATA_RANGE.get(b, (org, org + 0x2000))
            fn = NEM_ROOT + '/reloc/data_%s_bank%d.bin' % (TARGET, b)
            open(fn, 'wb').write(data)
            runs = [(lo, hi)]
            for slo, shi in DATA_SKIP.get(b, ()):
                runs = [r for a0, a1 in runs for r in ((a0, min(a1, slo)), (max(a0, shi), a1)) if r[0] < r[1]]
            for n, (a0, a1) in enumerate(runs):
                out += ['\n; ===== MSX bank %d data %04X-%04X -> %s %04X =====' % (b, a0, a1 - 1, sec, base + a0 - org),
                        '    section_data PAGE_%s,0x%04X' % (sec, base + a0 - org),
                        '    incbin "%s",%d,%d' % (fn, a0 - org, a1 - a0)]
                if n < len(runs) - 1: out.append('data_bank%d_part%d_end:' % (b, n))
            out.append('data_bank%d_end:' % b)
            for n, (a0, a1, psec, pbase) in enumerate(DATA_PIECES.get(b, ())):
                out += ['\n; ===== MSX bank %d data %04X-%04X -> %s %04X (a piece) =====' % (b, a0, a1 - 1, psec, pbase),
                        '    section_data PAGE_%s,0x%04X' % (psec, pbase),
                        'data_bank%d_piece%d:' % (b, n),
                        '    incbin "%s",%d,%d' % (fn, a0 - org, a1 - a0),
                        'data_bank%d_piece%d_end:' % (b, n)]
        stub = ['\n; ===== far-call stubs (fixed RAM) =====',
                '; Each stub is: call far_go / db page / dw target.  If the target page is',
                '; already mapped, far_go jumps straight to the target; otherwise it maps',
                '; it, calls the target and restores the caller\'s page.  Registers and',
                '; flags pass through both ways.  (Not re-entrant from an interrupt: the',
                '; sound interrupt never calls these.)',
                'far_go:', '    ex (sp),hl', '    push af', '    ld a,(cur_page)', '    cp (hl)', '    inc hl',
                '    jr nz,.switch', '    ld a,(hl)', '    inc hl', '    ld h,(hl)', '    ld l,a', '    pop af',
                '    ex (sp),hl', '    ret',
                '.switch:', '    ld a,(hl)', '    ld (far_jp+1),a', '    inc hl', '    ld a,(hl)', '    ld (far_jp+2),a',
                '    dec hl', '    dec hl', '    ld a,(hl)', '    ld hl,(cur_page)', '    call set_page', '    pop af',
                '    ex (sp),hl', '    call far_jp', '    jp far_leave',
                'far_jp:', '    jp 0',
                'far_leave:', '    ex (sp),hl', '    push af', '    ld a,l', '    call set_page', '    pop af',
                '    pop hl', '    ret']
        for name, (page, target) in sorted(self.stubs.items()):
            stub += ['%s:' % name, '    call far_go', '    db PAGE_%s' % page, '    dw %s' % target]
        stub += ['; no-restore variant (see NORESTORE_SITES)',
                 'nfar_go:', '    ex (sp),hl', '    push af', '    ld a,(cur_page)', '    cp (hl)', '    ld a,(hl)',
                 '    call nz,set_page', '    inc hl', '    ld a,(hl)', '    inc hl', '    ld h,(hl)', '    ld l,a',
                 '    pop af', '    ex (sp),hl', '    ret']
        for name, (page, target) in sorted(self.nstubs.items()):
            if TARGET == 'spec':        # inline: these run ~35 times a tick
                stub += ['%s:' % name, '    push af', '    ld a,(cur_page)', '    cp PAGE_%s' % page,
                         '    jr z,$+7', '    ld a,PAGE_%s' % page, '    call set_page', '    pop af',
                         '    jp %s' % target]
            else:
                stub += ['%s:' % name, '    call nfar_go', '    db PAGE_%s' % page, '    dw %s' % target]
        open(path, 'w').write('\n'.join(out) + '\n')
        open(path.replace('.asm', '_stubs.asm'), 'w').write('\n'.join(stub) + '\n')

if __name__ == '__main__':
    import subprocess
    rom = open(NEM_ROOT + '/nem.rom', 'rb').read()
    g = Gen(rom, identity=True); g.generate(NEM_ROOT + '/reloc/ident.asm')
    r = subprocess.run(['sjasmplus', '--nologo', '--msg=war', 'ident.asm'], cwd=NEM_ROOT + '/reloc', capture_output=True, text=True)
    ok = all(open(NEM_ROOT + '/reloc/ident_bank%d.bin' % b, 'rb').read() == rom[b * 8192:(b + 1) * 8192] for b in (0, 1, 2, 3, 7))
    print('identity build reproduces ROM banks 0-3, 7:', ok, (r.stdout + r.stderr)[-300:])
    g = Gen(rom)
    g.generate(NEM_ROOT + '/reloc/konami_reloc.asm' if TARGET == 'sim' else NEM_ROOT + '/spec/konami_spec.asm')
    for k, v in sorted(g.report.items()): print(k, v)
    print('far stubs:', len(g.stubs))
    if TARGET == 'spec':
        assert g.report['next patched'] == len(NEXT_PATCH), 'a Next hook site is not an item start'
