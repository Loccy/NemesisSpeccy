"""Generate relocated Konami game code for the Spectrum 128K layout.

MSX banks 0-3 (game code) and 7 (sound driver) are regenerated from
antxiko's listing with every address symbolic (label m<bank>_<addr> on every
item), so code may grow (RST 20h -> CALL) and items may move.  Banks 4, 5, 8
and 11 are placed raw.  Konami RAM E000-F0FF moves by RAM_DELTA.

Each item has a home section:
  fixed   MSX bank 0 at 5B00 (+ the 8-byte loop tail from bank 1 at 6000)
  fixed2  data moved out of a full page (fixed RAM overflow area)
  hot     copies of routines in uncontended fixed memory (HOT_CLONES; the 128K build only)
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
# The 48K demo (stage 1 only): one memory map, no paging, only the items in
# z48_keep.txt (the rest become the trap), no sound driver.
Z48 = TARGET == 'spec' and os.environ.get('NEM_Z48') == '1'

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
NO_EMIT = set()          # data banks placed (for their addresses) but not carried
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
    # The native build (no MSX graphics; the development notes, 1.1): the
    # graphics streams and character lists are gone; the game reads only
    # bank 5's object shapes (formas_de_objeto, 91D1-92E2) in play, bank 9's
    # two title panels (names, 9B3F-9C56) and bank 10 from A000 less the
    # ending's graphics (A0DB-A808).  Bank 4 is not carried at all.
    DATA_RANGE[5] = (0x91D1, 0x92E3)
    DATA_RANGE[9] = (0x9B3F, 0x9C57)
    NO_EMIT = {4}
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
    DATA_SKIP[10] = [(0xA0DB, 0xA758), (0xA758, 0xAAA6)]   # the ending's graphics; A758-AAA5 -> E769+0x758 = EEC1 .. F20E
    DATA_PIECES[12] = [(0xA2D8, 0xA428, 'E', 0xEEC1),  # stage 9's script
                       (0xA578, 0xA668, 'E', 0xF011),  # stage 11's
                       (0xA668, 0xA878, 'E', 0xF692),  # stage 12's
                       (0xA428, 0xA578, 'E', 0xF8A2),  # stage 10's
                       (0xB2E4, 0xB64C, 'E', 0xFC13)]  # tabla_de_finales and its records
    DATA_ALIAS[(12, 0xB2D2)] = 0xB2E4
Z48_SHAPES = 0xD9EE                 # bank 5's object shapes (91D1-92E2) in the 48K demo
if Z48:
    DATA_PLACE[5] = ('Z', Z48_SHAPES - (0x91D1 - 0x8000), 0x8000)
    DATA_RANGE[5] = (0x91D1, 0x92E3)
    NO_EMIT = {4, 8, 9, 10, 11, 12}
    DATA_PIECES = {}
    DATA_SKIP = {}

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
    # No Konami logo and no attract cycle (demo, illustration): straight to the
    # 1/2 player select, which waits there (Paul, 24 Oct; frees banks 9/10/12 space).
    (0, 0x52D9): ['    jp spec_title'],              # estado_0 sub 1: the title (and the controls) instead of the logo
    (0, 0x5308): ['    jp title_tick'],              # estado_1: the attract cycle's tune, looped on the title (0.102)
    (0, 0x537F): ['    jp title_end'],               # estado_3 (the game starting): the title's tune stopped (0.102)
    (0, 0x530F): ['    jp m0_5BD3'],                 # estado_1: keep blinking the choice, never the attract cycle
    (3, 0xA765): ['    jp dz_chunk'],                # come_un_trozo, one chunk of the dissolve, done natively (0.107)
    # di that only matter on the MSX (see 'mapper di' in emit_item): before the
    # sound request's pushes (the queue itself, 4A02-4A11, keeps its di), and
    # around RDPSG, which here reads the keyboard cache, not the AY.
    (0, 0x49DE): ['    nop'],
    (0, 0x49E9): ['    nop'],
    (0, 0x57B6): ['    nop'],
}
for _a in (0x567D, 0x5691, 0x5697, 0x56D2, 0x58F7, 0x5BA9):
    SPEC_PATCH[(0, _a)] = ['    call vdp_out_a']   # out (c),a to the VDP data port
# The native build: Konami's graphics loads become native loads of sets
# converted when the game is built (spec/native_sets.py, nl_load in
# native.asm).  Each site is a load event the census of 8 November 2026
# found (the development notes, 1.1).
SPEC_PATCH.update({
    (0, 0x422A): ['    jp nl_stage'],               # carga_los_graficos_de_la_fase: the stage's set
    (0, 0x4A8A): ['    call nl_bigcore'],           # the Big Core's characters (its call of carga_fichas)
    (0, 0x4B04): ['    call nl_ending'],            # the ending's graphics (its call of carga_el_marcador)
    (0, 0x4C2E): ['    call nl_marcador'],          # the ending, step 6: the status line again
    (0, 0x5300): ['    call nl_title'],             # estado_0: the title's graphics (its call of carga_el_marcador)
    (0, 0x53D4): ['    call nl_prestage'],          # the screen before each life (its call of carga_la_fuente)
    (0, 0x54DD): ['    call nl_gameover'],          # game over (its call of carga_el_marcador_en_dos_tercios)
    (0, 0x5A54): ['    ret'],                       # presentacion: its loads are in the title's set
    # Konami's block routines into VRAM, reached now only from dead code
    # (the attract cycle) or code the native build replaces
    (0, 0x4960): ['    ret'], (0, 0x4964): ['    ret'], (0, 0x4977): ['    ret'],
    (0, 0x4988): ['    ret'], (0, 0x49B3): ['    ret'], (0, 0x49B9): ['    ret'],
})
# Items left out of the native build (bank, first, last item start): the
# loaders and their data, and the calls the events above take the place of.
LEAVE_OUT = [(0, 0x422D, 0x4298),     # carga_los_graficos_de_la_fase's body (4299 stays: devuelve_el_reparto_de_siempre)
             (0, 0x42B3, 0x4498),     # graficos_por_fase, the character lists, the mirrors (4499-449E stay: 0:41CA's
                                      # base for the table at 449F is 4499)
             (0, 0x4961, 0x4963), (0, 0x4965, 0x4976), (0, 0x4978, 0x4987), (0, 0x4989, 0x4997),
             (0, 0x49B4, 0x49B8), (0, 0x49BC, 0x49DD),    # the block routines and the decompressor
             (0, 0x4A96, 0x4A98),     # the Big Core's call of monta_un_espejo
             (0, 0x4B11, 0x4B2B),     # the ending's three loads
             (0, 0x53F0, 0x5425),     # the screen before each life: its six blocks
             (0, 0x544F, 0x5451),     # ... and its call of carga_el_marcador_en_dos_tercios
             (0, 0x5851, 0x5A45),     # the status line's loaders and their data
             (0, 0x5A57, 0x5A67),     # presentacion's loads
             (0, 0x5B4D, 0x5B61)] if TARGET == 'spec' else []
def left_out(b, a):
    return any(lb == b and lo <= a <= hi for lb, lo, hi in LEAVE_OUT)

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
    (2, 0x99A1): ['    call 0x0124'],    # the ship's sprites, its ld a,(E200): lo_shipst (with the MSX2 graphics, always the plain ship, as the patch; the shield is drawn on its own)
    (2, 0x99C3): ['    call 0x0124'],    # the same, for the blink
    (3, 0xA19B): ['    call 0x0124'],    # the same, where the ship's second sprite is put 8 pixels right with the shield
    # pide_sonido's request into the queue: no di (an interrupt that comes while
    # they are off is lost on the Next, and the scroll is not set that frame);
    # snd_busy instead, and the interrupt leaves the sound driver for a frame
    (0, 0x4A02): ['    call snd_hold'],
    # an effect (sound below 16h) goes to one of our own three channel
    # records (nx_pick), played on AY 2 (plat_spec nx_sfx), in place of
    # channel C's, which the music holds
    (0, 0x4A3C): ['    call nx_pick'],
    (0, 0x4A11): ['    call snd_free'],
}
# Next hooks inside code the native build leaves out (LEAVE_OUT): the Next
# still needs the call there (the 128K build has nothing in its place).
# 0:544F, the call of 0:5874 before each life: its graphics come with the
# native load at 0:53D4, but lo_prestage still puts the stage's colours and
# status line in.  (0:5851, lo_marcador's hook, is not kept: the native
# loads of the title, the ending and its status line call lo_marcador.)
NEXT_KEEP = {(0, 0x544F)}
# What Konami has at each of them (checked when generating, so a moved or
# changed site stops the build instead of being overwritten).
NEXT_PATCH_WAS = {
    (0, 0x46A1): 'edb0', (2, 0x9251): '3a00e1', (0, 0x4100): 'cd2a42',
    (0, 0x414B): 'cd2a42', (0, 0x5851): '110659', (0, 0x544F): 'cd7458',
    (2, 0x99A1): '3a00e2', (2, 0x99C3): '3a00e2', (3, 0xA19B): '3a00e2',
    (0, 0x4A02): 'f3', (0, 0x4A11): 'fb', (0, 0x4A3C): '2e34',
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
if Z48:
    BANK_SECTION[2] = 'A2'          # the 48K demo: bank 2 placed apart from bank 1
    # and parts of a bank in sections of their own: (bank, first item, section),
    # from NEM_Z48_SPLIT ("2:9000:A3,..."); the bank's items from there on
    Z48_SPLIT = [(int(b), int(a, 16), sec) for b, a, sec in
                 (x.split(':') for x in os.environ.get('NEM_Z48_SPLIT', '').split(',') if x)]
# (bank, first, last) -> section, emitted right after bank `after`'s own items
ITEM_MOVES = [((1, 0x6000, 0x6007), 'fixed', 0)] + ([] if Z48 else [((3, 0xA000, 0xA021), 'A', 2)])   # (the 48K: no pages; bank 1 is cut, fit48.py)
if TARGET == 'spec':      # the boss pieces' drawing and turrets, with bank 10 in page E
    ITEM_MOVES.append(((2, 0x8290, 0x839E), 'E', 2))
DATA_MOVES = [(1, 0x7EE6, 88)]          # -> fixed2

# Routines copied into uncontended fixed memory (section 'hot', written to
# konami_spec_hot.asm and included after the platform's buffers), the 128K
# build only.  Every call, jump and code pointer to an item of a range goes
# to its copy there (labels H_m<bank>_<addr>), from whatever page, with no
# far stub: for a small routine in a paged bank called across pages many
# times a tick that saves a page switch there and back, about 520 T-states a
# call.  Over the first loop these took 191,000 of the 360,000 switching far
# calls (11 November 2026).
# They are copies, not moves: the original stays where it is, whole.  Konami
# takes addresses relative to its code (2:90D4's ld hl,9262h is the table at
# 9264 less 2, and 9262 is inside se_corre_con_el_scroll_ocho: moving that
# routine sent the table lookup into fixed memory, and the lockstep stopped
# at stage 1's first enemy), and anything that still reaches the original
# (a jump from beside it, an address in a register) finds it as it was.
# A range's last item must be a ret or an unconditional jump (checked when
# generating); none of these reads its own bank's data.  B42E-B452 is the
# turrets' loop: its body (B453, with its tables) stays in page C and is
# reached from the copy only while a turret is out.
# The Next build has no copies (NEM_NEXT=1: its layout as before);
# NEM_HOT=0 builds the 128K without them.
HOT_CLONES = [(2, 0x9235, 0x9250),      # dispara_sin_apuntar
              (2, 0x9251, 0x9263),      # se_corre_con_el_scroll_ocho
              (3, 0xA22D, 0xA27E),      # guarda_lo_de_debajo_del_laser
              (3, 0xA2C7, 0xA30F),      # devuelve_lo_de_debajo
              (3, 0xB42E, 0xB452)]      # pinta_las_torretas (the loop over the four)
# Konami's bank 0 code is in fixed memory, but at 5B00-760A, which the 128K's
# ULA contends: its instructions run 20% to 31% slower there than they would
# above 8000 (the exact profile of 11 November 2026, run with and without
# contention).  These are the bank 0 routines the game spends its time in:
# 1,146 of its 6,923 bytes, 93% of its time (21,565 of 23,161 T-states a tick
# over the first loop), chosen as whole runs of instructions that end in a
# ret or a jump (chunks0.py).  0:4028-4059
# (interrupcion) is left where it is: the checks stop at 0:4054 for the end
# of a tick, and the platform calls 0:4045 by name.
HOT_CLONES += [(0, 0x405D, 0x4070),     # suma_a_a_hl, suma_a_a_de, despachador
               (0, 0x44E7, 0x45F4),     # mira_la_tecla_de_pausa, un_cuadro_de_juego
               (0, 0x4664, 0x4669),     # marca_que_no_toca
               (0, 0x47AE, 0x47C2),     # dame_palabra, corre_los_sprites
               (0, 0x47CE, 0x47FD),     # sube_los_sprites_rotando
               (0, 0x481C, 0x48DF),     # monta_los_sprites, pon_atributo, esconde_el_sprite
               (0, 0x48F7, 0x493C),     # borra_un_rectangulo, copia_un_rectangulo, recorta_por_la_derecha
               (0, 0x494A, 0x4955),     # pon_escritura_vram
               (0, 0x4D7E, 0x4E12),     # mueve_la_metralla, sube_la_metralla_al_buffer, anima_la_metralla
               (0, 0x5464, 0x546E),     # estado_5
               (0, 0x5682, 0x569C),     # escribe_las_cifras
               (0, 0x571B, 0x572E),     # casilla_a_direccion_de_ram
               (0, 0x5767, 0x5773),     # lee_el_mando
               (0, 0x577D, 0x57BC),     # junta_joystick_y_teclado, lee_el_joystick
               (0, 0x5DC8, 0x5E5C),     # corre_los_doce_objetos, despacha_el_motor_del_objeto, anima_cuatro_dibujos
               (0, 0x5F66, 0x5FA4)]     # mira_si_el_objeto_se_ha_ido, suma_la_velocidad, suma_una_palabra
if os.environ.get('NEM_HOT') == 'paged':    # (the paged banks' routines alone, as first built)
    HOT_CLONES = [r for r in HOT_CLONES if r[0] != 0]
if not (TARGET == 'spec' and os.environ.get('NEM_NEXT') != '1' and os.environ.get('NEM_HOT') != '0') or Z48:
    HOT_CLONES = []
if Z48:
    CLONES = {}
    # the map pieces and scripts (bank 11) are the demo's own (map48.asm)
    Z48_IMM = {0x46C3: 'map48_table', 0x46F2: 'map48_pieces', 0x4708: 'map48_pieces'}
    # no sound driver: a request is noted by the platform (z48_snd)
    SPEC_PATCH[(0, 0x4A22)] = ['    jp z48_snd']
    # the pause without Konami's typed codes (13 November): its call to
    # mira_lo_que_se_teclea (left out) gone
    SPEC_PATCH[(0, 0x451C)] = []
    # Stage 5 (13 November, the user's choice): the skeletons and the skulls
    # are there already, not rising.  The skeletons (background types 1-4)
    # keep Konami's rise timer, but start on their risen picture and the
    # timer no longer changes it, so their rising pictures go (tools/z48/
    # keepC.py); the skulls (the turrets of E880) start at the row their
    # rise and slide would have taken them to, at step 2, with their first
    # fan of shots when Konami's would come (15 frames out, 5 a step of the
    # slide, 24 still), and the rise, the slide and the half-drawn skull go
    SPEC_PATCH[(3, 0xB2F3)] = []                                  # inc (ix+6): the picture stays
    SPEC_PATCH[(3, 0xB50F)] = ['    add a,4                     ; (48K: risen)', '    ld (hl),a']
    SPEC_PATCH[(3, 0xB175)] = []                                  # jr z,paso_1_de_e880: no slide
    SPEC_PATCH[(3, 0xB457)] = []                                  # jr z,la_torreta_asoma: never half out
    SPEC_PATCH[(3, 0xB3B9)] = [
        '    ld a,(ix+007h)              ; (48K: the skull is out already) the slide\'s steps',
        '    ld c,a',
        '    add a,a',
        '    add a,a',
        '    add a,c',
        '    add a,027h                  ; its first fan when Konami\'s would come: 15 + 5 a step + 24 frames',
        '    ld (hl),a                   ; byte 4',
        '    inc l',
        '    ld (hl),030h                ; byte 5, as the slide leaves it',
        '    inc l',
        '    ld (hl),000h                ; byte 6: shut',
        '    inc l',
        '    ld (hl),000h                ; byte 7',
        '    ld a,l',
        '    sub 006h',
        '    ld l,a',
        '    ld (hl),002h                ; byte 1: step 2',
        '    inc l',
        '    ld b,c                      ; the slide: steps - 1 moves of 8',
        '    ld a,(hl)                   ; byte 2: the row',
        '    bit 0,(ix+000h)',
        '    jr z,z5t_d2',
        '    sub 018h                    ; up: three rows out first',
        '    jr z5t_u2',
        'z5t_u1:',
        '    sub 008h',
        'z5t_u2:',
        '    djnz z5t_u1',
        '    jr z5t_st',
        'z5t_d1:',
        '    add a,008h',
        'z5t_d2:',
        '    djnz z5t_d1',
        'z5t_st:',
        '    ld (hl),a']
    for _a in (0xB3BB, 0xB3BC, 0xB3BE, 0xB3BF, 0xB3C1, 0xB3C2, 0xB3C5):
        SPEC_PATCH[(3, _a)] = []                                  # (the rest of Konami's set-up)
    # Stage 5's split pieces (type 1F, from the triangle of type 1E) no
    # longer chase the ship while the big flock is out (13 November, the
    # user's choice): they fly on at the speed the split gave them.  The
    # chase's acceleration routine and table (2:95EB-9856, stage 5's alone)
    # go (tools/z48/keepC.py)
    # Game over (13 November): Konami's screen waits for C (continue) or R
    # (the title: rewind, or in stage 1 restart), z48_load.asm z48_go; its
    # third line's word from the stage's header (z48_go_text)
    ITEM_PATCH[(0, 0x584D)] = ['    db 0x00,0x23,0xFE,0xCB,0x39,0x32,0x25    ; " C", then "RE"',
                               'z48_go_word:',
                               '    db 0x37,0x29,0x2E,0x24,0x00,0x00,0x00,0x32,0xFF   ; "WIND  " (or the stage\'s word), "  R"']
    SPEC_PATCH[(0, 0x549F)] = ['    call z48_go                 ; (48K: a key, not the tune)']
    SPEC_PATCH[(0, 0x54A2)] = []
    SPEC_PATCH[(0, 0x54E3)] = ['    call z48_go_text            ; (48K: the stage\'s word, then escribe_caracteres)']
    # Stage 6's boss: its tables in MSX bank 10, which the 48K carries as a
    # copy in stage 6's block (z48_data.py, z48_b10)
    SPEC_PATCH[(2, 0x82CC)] = ['    ld hl,z48_b10               ; (48K: bank 10\'s A:AAA6, copied)']
    SPEC_PATCH[(2, 0x82D1)] = ['    ld hl,z48_b10+10            ; (A:AAB0)']
    SPEC_PATCH[(2, 0x831B)] = ['    ld hl,z48_b10               ; (48K: bank 10\'s A:AAA6, copied)']
    SPEC_PATCH[(2, 0x834F)] = ['    ld hl,z48_b10+10            ; (A:AAB0)']
    # The end (14 November, as agreed): no Konami ending after stage 8's
    # boss (1:6F72 started it: the debris, the ship flying off, the message);
    # the stage is over at once (1:6FD0), Konami's wrap to stage 1 follows
    # (1:6FE6; E061 9 would be the first bonus stage), and the load from
    # stage 8's block to stage 1 shows THE END (z48_other)
    SPEC_PATCH[(1, 0x6F72)] = ['    jp m1_6FD0                  ; (48K: no ending sequence)']
    # No cursor (14 November): when fire is pressed Konami shows its menu's
    # cursor solid (0:5533, into 0:5BDD); our title has no menu, and the
    # screen's copy kept the cursor, drawn in the wrong tiles as play began
    SPEC_PATCH[(0, 0x5533)] = ['    ret                         ; (48K: no menu cursor)']
    SPEC_PATCH[(3, 0xBD8C)] = ['    ret                         ; (48K: no chase)']
    SPEC_PATCH[(3, 0xBD8F)] = []
    SPEC_PATCH[(3, 0xBD92)] = []
    Z48_KEEP = set()
    Z48_STAGE_N = int(os.environ.get('NEM_Z48_STAGE', '1'))
    # tables read by an index across what the core keeps and what it does
    # not: whole into the core (the explosion's three frames, 13 November)
    # (all of them: every split table was found read across the split, in
    # some stage, 13 November, with scratch tools not kept)
    Z48_WHOLE = 'all'
    # the front end that no stage's play runs: stage 1's alone (tools/z48/keepC.py)
    Z48_FEONLY = set()
    if _os.path.exists(NEM_ROOT + '/reloc/z48_feonly.txt'):
        for _l in open(NEM_ROOT + '/reloc/z48_feonly.txt'):
            _b, _a = _l.split(); Z48_FEONLY.add((int(_b), int(_a, 16)))
    # tables read on into the next one: 1:64C8, the trajectories' block 13,
    # runs into 1:64D4
    Z48_JOIN = {(1, 0x64D4)}
    _st = int(os.environ.get('NEM_Z48_STAGE', '1'))
    for _l in open(NEM_ROOT + '/reloc/z48_keepc_%d.txt' % _st):   # (tools/z48/keepC.py: from the census)
        if _l.strip() and not _l.startswith('#'):
            _b, _a = _l.split(); Z48_KEEP.add((int(_b), int(_a, 16)))
    # The shared layout (NEM_Z48_SHARED=1): the core, what every stage keeps,
    # at the same addresses in every stage's build; the rest of the stage's
    # list in section OV (the stage's own block).  The core reaches the
    # stage's code only through jump slots (section ZS, the same in every
    # build: jp the item, or the trap where the stage lacks it); data the
    # core reads is made core itself (z48_shared_home).
    Z48_SHARED = os.environ.get('NEM_Z48_SHARED') == '1'
    if Z48_SHARED:
        Z48_LISTS = []
        for _n in range(1, 9):
            _s = set()
            for _l in open(NEM_ROOT + '/reloc/z48_keepc_%d.txt' % _n):
                if _l.strip() and not _l.startswith('#'):
                    _b, _a = _l.split(); _s.add((int(_b), int(_a, 16)))
            Z48_LISTS.append(_s)
        Z48_UNION = set().union(*Z48_LISTS)
else:
    Z48_SHARED = False
FIXED_SECTIONS = ('fixed', 'fixed2', 'hot')

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
        self.items = {}; self.labels = {}; self.raw = {}; self.starts = {}; self.kinds = {}; self.z48_base = set(); self.z48_codedata = set(); self.z48_dataref = set(); self.z48_core = None
        for b in (0, 1, 2, 3, 7):
            it, lab, raw = parse(b, rom)
            self.items[b] = it; self.labels[b] = lab; self.raw[b] = raw
            self.starts[b] = [i[0] for i in it]
            self.kinds.update(((b, i[0]), i[2]) for i in it)
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
            self.home_base = dict(self.home)
            if Z48:
                for b in self.items:
                    for it in self.items[b]:
                        sp = [(sa, ssec) for sb, sa, ssec in Z48_SPLIT if sb == b and it[0] >= sa]
                        if sp and self.home[(b, it[0])] == BANK_SECTION[b]: self.home[(b, it[0])] = max(sp)[1]
                        if b == 7 or ((b, it[0]) not in Z48_KEEP and not left_out(b, it[0])): self.home[(b, it[0])] = 'dropped'   # (an item left out is emitted as nothing anyway)
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
        if Z48_SHARED and self.z48_core is not None and getattr(self, 'cur_core', False) and bank in (0, 1, 2, 3) and (bank, a) not in self.z48_core and (bank, a) not in self.z48_ta and not left_out(bank, a):
            if getattr(self, '_tgt', False) and a == v and self.kinds.get((bank, a)) == 'code':
                self.z48_slots.add((bank, a)); return 'zs_%d_%04X' % (bank, a)
            self.z48_need.add((bank, a))        # data the core reads: core too (z48_shared_home)
        if Z48 and not getattr(self, '_tgt', False) and self.home.get((bank, a)) == 'dropped':
            self.z48_dref.add((bank, a))        # (an address taken as data: see generate)
        if Z48 and not getattr(self, '_tgt', False) and a != v and self.kinds.get((bank, a)) == 'code':
            # an address inside a code item taken as data: a
            # table based on it may lie after it (2:9DBD's ld hl,9DCD reads
            # 9DCE on), so fit48.py must not cut bank 2 just after this item
            self.z48_base.add((bank, a, v))
        if Z48 and not getattr(self, '_tgt', False) and a == v and self.kinds.get((bank, a)) == 'code':
            self.z48_codedata.add((bank, a))
        if Z48 and not getattr(self, '_tgt', False) and a == v and self.kinds.get((bank, a)) != 'code':
            self.z48_dataref.add((bank, a))      # (a table named by its first byte: one that may move)
        return 'm%d_%04X' % (bank, a) if a == v else 'm%d_%04X+%d' % (bank, a, v - a)

    def page_of(self, bank, v):
        if Z48: return 'fixed'
        if bank in DATA_PLACE: return DATA_PLACE[bank][0]
        sec = self.home[(bank, self.item_of(bank, v))]
        return 'fixed' if sec in FIXED_SECTIONS else sec

    def ram(self, v):
        return '0x%04X' % (v + (0 if self.identity else RAM_DELTA))

    def clone_label(self, bank, v, cur_sec):
        if self.identity: return None
        for cb, lo, hi in HOT_CLONES:
            if cb == bank and lo <= v <= hi and v == self.item_of(bank, v):
                return 'H_m%d_%04X' % (bank, v)
        for (cb, lo, hi), secs in CLONES.items():
            if cb == bank and lo <= v <= hi and cur_sec in secs and v == self.item_of(bank, v):
                return '%s_m%d_%04X' % (cur_sec, bank, v)
        return None

    def target(self, bank, v, cur_sec, site):
        tb = SITE_BANK.get(site, bank)
        cl = self.clone_label(tb, v, cur_sec)
        if cl: self.report['clone call'] += 1; return cl
        self._tgt = True; s = self.sym(tb, v); self._tgt = False
        if self.identity: return s
        tp = self.page_of(tb, v)
        cp = 'fixed' if cur_sec in FIXED_SECTIONS else cur_sec
        if tp != 'fixed' and any(lo <= site <= hi for lo, hi in NORESTORE_SITES):
            name = 'nfar_' + s.replace('+', '_')
            self.nstubs[name] = (tp, s); self.report['far no-restore'] += 1
            return name
        if tp != 'fixed' and tp != cp:
            name = 'far_' + s.replace('+', '_')
            self.stubs[name] = (tp, s); self.report['far'] += 1
            return name
        return s

    def check_hot(self):
        """A hot copy must not run off its end into the next one: its last
        item must be a ret or an unconditional jump."""
        for b, lo, hi in HOT_CLONES:
            its = [it for it in self.items[b] if lo <= it[0] <= hi]
            assert its and its[0][0] == lo and its[-1][0] + its[-1][1] - 1 == hi, 'hot range %d:%04X-%04X is not whole items' % (b, lo, hi)
            assert its[-1][2] == 'code' and self.raw[b][its[-1][0] - ORG[b]] in (0xC9, 0xC3, 0x18, 0xE9), 'hot range %d:%04X-%04X runs off its end' % (b, lo, hi)

    def emit_item(self, b, it, sec, out):
        raw = self.raw[b]; org = ORG[b]; I = self.identity
        a, n = it[0], it[1]
        if Z48_SHARED: self.cur_core = self.home.get((b, a)) not in ('OV', 'TA', 'TAX')
        if not I and left_out(b, a):
            self.report['left out'] += 1
            if TARGET == 'spec' and (b, a) in NEXT_KEEP:
                raw_ = raw[a - org:a - org + n].hex()
                assert raw_ == NEXT_PATCH_WAS[(b, a)], 'Next hook %d:%04X is %s, not %s' % (b, a, raw_, NEXT_PATCH_WAS[(b, a)])
                out += ['    ifdef NEXT'] + NEXT_PATCH[(b, a)] + ['    endif']
                self.report['next patched'] += 1
            return
        if not I and TARGET == 'spec' and (b, a) in NEXT_PATCH and not getattr(self, 'in_next', False) and not getattr(self, 'hot_ctx', None):   # (a hot copy is the 128K's alone)
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
        hot = getattr(self, 'hot_ctx', None)        # emitting a hot copy: its own labels, H_m<bank>_<addr>
        out.append('%sm%d_%04X:' % ('H_' if hot else '', b, a))
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
            ctx = getattr(self, 'hot_ctx', None)       # emitting a hot copy: jumps inside it stay relative
            if ctx: tsec = sec if (tb == ctx[0] and ctx[1] <= t <= ctx[2]) else None
            if (tsec == sec or I) and (I or TARGET != 'spec' or (b, a) not in JR_LONG):
                mn = {0x10: 'djnz ', 0x18: 'jr ', 0x20: 'jr nz,', 0x28: 'jr z,', 0x30: 'jr nc,', 0x38: 'jr c,'}[op]
                out.append('    %s%s%s' % (mn, 'H_' if ctx else '', self.sym(tb, t)))
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
            elif not I and Z48 and b == 0 and a in Z48_IMM: s = Z48_IMM[a]
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
        if Z48:                                 # (a jump table's entry: a target)
            self._tgt = True; s = self.sym(tb, v); self._tgt = False; return s
        cl = self.clone_label(tb, v, sec)
        if cl: return cl
        tp = self.page_of(tb, v)
        if tp == 'fixed': return self.sym(tb, v)
        cp = 'fixed' if sec in FIXED_SECTIONS else sec
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

    def z48_set_homes(self):
        for b in self.items:
            for it in self.items[b]:
                k = (b, it[0]); base = self.home_base[k]
                if b == 7: self.home[k] = 'dropped'
                elif k in self.z48_core or left_out(b, it[0]):
                    sp = [(sa, ssec) for sb, sa, ssec in Z48_SPLIT if sb == b and it[0] >= sa]
                    self.home[k] = max(sp)[1] if sp and base == BANK_SECTION[b] else base
                elif k in self.z48_ta: self.home[k] = 'TA' if Z48_STAGE_N in self.z48_ta_runs[self.z48_ta[k]][1] else 'TAX'
                elif k in Z48_KEEP: self.home[k] = 'OV'
                else: self.home[k] = 'dropped'

    def z48_tables(self, core, named_of):
        """The shared table area (13 November): a table the core reads that
        not every stage keeps leaves the core for a fixed place at the start
        of each stage's block (after the slots).  Each stage holds there only
        the tables it keeps; tables no stage shares overlap, so the area is
        about the largest stage's share, not the sum."""
        inter = set.intersection(*Z48_LISTS)
        runs = []
        for b in (0, 1, 2, 3):
            named = named_of(b); run = []
            for it in self.items[b] + [(None, 0, 'code')]:
                k = (b, it[0])
                ok = it[2] != 'code' and k in core and not left_out(*k)
                if ok and run and it[0] in named and k not in Z48_JOIN:
                    runs.append(run); run = []
                if ok: run.append(k); continue
                if run: runs.append(run)
                run = []
        # a table's stages: those whose list keeps any of it beyond what all
        # eight keep, and those whose test runs read any of it (tools/z48/
        # tabread.py: every list keeps the first entry of a table that code
        # in every list names, read or not).  None: it stays in the core, as
        # does a table the platform names
        reads = collections.defaultdict(set)
        for l in open(NEM_ROOT + '/reloc/z48_reads.txt'):
            b, a, st = l.split(); reads[(int(b), int(a, 16))] = {int(x) for x in st.split(',')}
        out = []
        for run in runs:
            if any(x in self.z48_plat for x in run): continue
            if all(x in inter for x in run): continue       # (every list keeps it whole)
            st = {n + 1 for n, L in enumerate(Z48_LISTS) if any(x in L and x not in inter for x in run)}
            for x in run: st |= reads.get(x, set())
            st = frozenset(st)
            if not st or len(st) == 8: continue
            b, a0 = run[0]; last = run[-1][1]
            size = last + next(it[1] for it in self.items[b] if it[0] == last) - a0
            out.append([run, st, size, 0])
        place = []
        for r in sorted(out, key=lambda r: (-r[2], r[0][0])):
            o = 0
            while True:
                clash = [p for p in place if p[1] & r[1] and p[3] < o + r[2] and o < p[3] + p[2]]
                if not clash: break
                o = max(p[3] + p[2] for p in clash)
            r[3] = o; place.append(r)
        self.z48_ta_runs = sorted(place, key=lambda r: r[3])
        self.z48_ta = {x: i for i, r in enumerate(self.z48_ta_runs) for x in r[0]}
        self.z48_ta_size = max((r[3] + r[2] for r in place), default=0)
        return set(self.z48_ta)

    def z48_shared_home(self):
        """The core: what every stage's list keeps, and every item the core
        takes as data (a table, a table's base) that some stage keeps; for a
        base no stage keeps, the item after it that one does.  The same in
        every stage's build."""
        core = set.intersection(*Z48_LISTS); core0 = len(core); self.z48_plat = set()
        self.z48_ta = {}; self.z48_ta_runs = []; self.z48_ta_size = 0
        # and every item the platform names (its calls into Konami's code)
        import glob as _glob, re as _re2
        for fn in _glob.glob(NEM_ROOT + '/spec/*.asm'):
            if _os.path.basename(fn).startswith(('konami_spec', 'z48_slots', 'z48_tables', 'z48_ovhigh', 'z48_hplace', 'z48_layout', 'z48_ovhead', 'z48_data', 'nx_', 'fullcmp')): continue
            for m in _re2.finditer(r'\bm([0-3])_([0-9A-F]{4})\b', open(fn).read()):
                k = (int(m.group(1)), int(m.group(2), 16))
                if k in Z48_UNION: core.add(k); self.z48_plat.add(k)
        self.z48_core = core; self.z48_splits = set()
        while True:
            self.z48_set_homes()
            self.z48_need = set(); self.z48_slots = set()
            for b in (0, 1, 2, 3):
                for it in self.items[b]:
                    if self.home[(b, it[0])] in ('dropped', 'OV') or left_out(b, it[0]): continue
                    self.emit_item(b, it, self.home[(b, it[0])], [])
            self.cur_core = False
            new = set()
            for b, a in self.z48_need:
                if (b, a) in Z48_UNION: new.add((b, a)); continue
                its = self.items[b]; k = self.starts[b].index(a)
                n = next(((b, it[0]) for it in its[k + 1:] if (b, it[0]) in Z48_UNION or (b, it[0]) in core), None)
                if n and n not in core and n[1] - a <= 256: new.add(n)
            # a table split between the core and a stage's block is read
            # wrongly by an index (1:633A, the explosion's frames, 13
            # November): a run of data items, one after another, that some
            # stage keeps goes whole into the core if any of it is there
            for b in (0, 1, 2, 3):
                run = []
                named = {a for n, a in self.labels[b].items() if a is not None and not n.startswith('L_')}
                for it in self.items[b] + [(None, 0, 'code')]:
                    k = (b, it[0])
                    if it[2] != 'code' and k in Z48_UNION and not left_out(*k):
                        if it[0] in named and run and k not in Z48_JOIN:      # (a table's own name starts a new run)
                            self.z48_split(run, core, new); run = []
                        run.append(k); continue
                    if run: self.z48_split(run, core, new)
                    run = []
            # a table of addresses after `call 0x4067` goes where its call goes
            # (the dispatcher reads it through the return address)
            for b in (0, 1, 2, 3):
                its = self.items[b]
                for j, it in enumerate(its):
                    if it[2] == 'code' and (b, it[0]) in core and self.raw[b][it[0] - ORG[b]:it[0] - ORG[b] + 3] == bytes((0xCD, 0x67, 0x40)):
                        j2 = j + 1
                        while j2 < len(its) and its[j2][2] != 'code':
                            if (b, its[j2][0]) in Z48_UNION or not left_out(b, its[j2][0]): new.add((b, its[j2][0]))
                            j2 += 1
            new -= core
            if not new: break
            core |= new
        # the tables not every stage keeps: out to the shared table area
        named_of = lambda b: {a for n, a in self.labels[b].items() if a is not None and not n.startswith('L_')}
        ta = self.z48_tables(core, named_of)
        core -= ta
        self.z48_set_homes(); self.z48_need = set(); self.z48_slots = set()
        for b in (0, 1, 2, 3):
            for it in self.items[b]:
                if self.home[(b, it[0])] in ('dropped', 'OV', 'TA', 'TAX') or left_out(b, it[0]): continue
                self.emit_item(b, it, self.home[(b, it[0])], [])
        self.cur_core = False
        miss = {k for k in self.z48_need if k in Z48_UNION} - core - ta
        assert not miss, 'the core takes items neither it nor the table area holds: %s' % sorted(miss)[:8]
        # every stage's own code read for what it takes as data, so that the
        # places fit48.py must not cut (z48_nocut.txt) are the same in every
        # stage's build, and with them the core (13 November: stage 8's
        # differed from stage 5's)
        keep = (set(self.z48_need), set(self.z48_slots), set(self.z48_dref), dict(self.home))
        for b in (0, 1, 2, 3):
            for it in self.items[b]:
                k = (b, it[0])
                if k in Z48_UNION and k not in core and not left_out(*k):
                    self.home[k] = 'OV'; self.emit_item(b, it, 'OV', [])
        self.cur_core = False
        self.z48_need, self.z48_slots, self.z48_dref, self.home = keep
        self.report['z48 table area'] = self.z48_ta_size; self.report['z48 table area tables'] = len(self.z48_ta_runs)
        self.report['z48 core items'] = len(core); self.report['z48 core forced'] = len(core) - core0
        with open(NEM_ROOT + '/reloc/z48_splits.txt', 'w') as f:
            for run in sorted(self.z48_splits):
                f.write(' '.join('%d:%04X%s' % (b, a, '*' if (b, a) in core else '') for b, a in run) + '\n')
        open(NEM_ROOT + '/reloc/z48_core.txt', 'w').write(''.join('%d %04X\n' % x for x in sorted(core)))

    def z48_split(self, run, core, new):
        """A table part in the core and part not: whole into the core where
        it is known to be read by an index across the parts (Z48_WHOLE),
        else noted in reloc/z48_splits.txt to be looked at."""
        inc = [x for x in run if x in core]
        if not inc or len(inc) == len(run): return
        self.z48_splits.add(tuple(run))
        if Z48_WHOLE == 'all' or any(x in Z48_WHOLE for x in run): new.update(run)

    def z48_slot(self, k):
        self.z48_slots.add(k); return 'zs_%d_%04X' % k

    def z48_emit(self, b, k, sec, sections):
        """Item k of bank b, and a jump on to the next item where this one
        runs on into it and it is not emitted next."""
        its = self.items[b]; it = its[k]
        self.emit_item(b, it, sec, sections[sec])
        if not Z48 or it[2] != 'code': return
        bs = self.raw[b][it[0] - ORG[b]:it[0] - ORG[b] + it[1]]
        if bs[0] in (0xC9, 0xC3, 0x18, 0xE9) or (bs[0] in (0xDD, 0xFD) and bs[1] == 0xE9) or (bs[0] == 0xED and bs[1] in (0x4D, 0x45)): return
        j = k + 1
        while j < len(its) and left_out(b, its[j][0]): j += 1      # (emitted as nothing)
        if j == len(its):
            # the bank's last instruction runs on into the next bank (2:9FFx into 3:A000)
            if b in (0, 1, 2):
                sections[sec].append('    jp ' + self.z48_name(b + 1, ORG[b + 1])); self.report['z48 bank run-on'] += 1
            return
        nk = (b, its[j][0]); nh = self.home[nk]
        if nh == sec: return
        if Z48_SHARED and sec != 'OV' and nh in ('OV', 'dropped'):
            sections[sec].append('    jp ' + self.z48_slot(nk)); self.report['z48 slot run-on'] += 1
        elif nh == 'dropped':
            sections[sec].append('    jp z48_trap'); self.report['z48 fall-through trap'] += 1
        else:
            sections[sec].append('    jp ' + self.z48_name(*nk)); self.report['z48 split jump'] += 1

    def z48_name(self, b, a):
        """A jump to item (b, a) from the item being emitted."""
        self._tgt = True; s = self.sym(b, a); self._tgt = False
        return s

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
        sections = collections.OrderedDict((k, []) for k in ('fixed', 'A', 'C', 'D', 'fixed2', 'E', 'hot') + (('A2',) + tuple(x[2] for x in Z48_SPLIT) if Z48 else ()) + (('OV',) if Z48_SHARED else ()))
        self.z48_dref = set()
        if Z48_SHARED: self.z48_shared_home()
        self.check_hot()
        drops = []; self.z48_dref = set()   # (the dry pass's are not kept)
        for b in (0, 1, 2, 3, 7):
            its = self.items[b]
            for k, it in enumerate(its):
                sec = self.home[(b, it[0])]
                if sec == 'dropped':
                    if not left_out(b, it[0]): drops.append((b, k))
                    continue
                if sec != BANK_SECTION[b] and not (Z48 and any(sb == b and sec == ssec for sb, sa, ssec in Z48_SPLIT)): continue
                self.z48_emit(b, k, sec, sections)
            for (mb, lo, hi), sec, after in ITEM_MOVES:
                if after == b:
                    for it in self.items[mb]:
                        if self.home[(mb, it[0])] in ('dropped', 'OV'): continue      # (its trap: the bank loop's)
                        if lo <= it[0] <= hi: self.emit_item(mb, it, sec, sections[sec])
        for b, lo, ln in DATA_MOVES:
            for it in self.items[b]:
                if self.home[(b, it[0])] in ('dropped', 'OV'): continue
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
        for cb, lo, hi in HOT_CLONES:
            body = []; self.hot_ctx = (cb, lo, hi)
            for it in self.items[cb]:
                if lo <= it[0] <= hi: self.emit_item(cb, it, 'hot', body)
            self.hot_ctx = None
            # No renaming of what the copy refers to: its jumps and calls to
            # copied code come out as H_ labels (clone_label, and the
            # relative jumps inside the range), and every address it takes
            # as data (a table, a base less an offset) is the original's,
            # which is still there.
            sections['hot'].append('; copy of MSX bank %d %04X-%04X' % (cb, lo, hi))
            sections['hot'] += body
        out = []
        hot = sections.pop('hot')
        open(path.replace('.asm', '_hot.asm'), 'w').write('\n'.join(
            ['; ===== section hot: copies of routines in uncontended fixed memory (gen.py HOT_CLONES) =====']
            + hot + ['section_hot_end:']) + '\n')
        if Z48_SHARED:
            # the stage's own tables that fit the high areas' leftovers
            # (build48.py, Z48_HIGH_FREE): there, each whole, best fit,
            # largest first (z48_ovhigh.asm)
            free = [[int(x, 16) for x in r.split('-')] for r in os.environ.get('Z48_HIGH_FREE', '').split(',') if r]
            moved = {}; oh = ['; generated by gen.py: stage %d\'s own tables in the high areas\' leftovers' % Z48_STAGE_N]
            if free:
                runs = []
                for b in (0, 1, 2, 3):
                    named = {a for n, a in self.labels[b].items() if a is not None and not n.startswith('L_')}
                    bases = [(x, v) for bb, x, v in self.z48_base if bb == b]
                    run = []; prev = None
                    for it in self.items[b] + [(None, 0, 'code')]:
                        k = (b, it[0])
                        ok = it[0] is not None and self.home.get(k) == 'OV' and it[2] != 'code' and not left_out(*k)
                        if ok and run and it[0] in named and k not in Z48_JOIN:
                            runs.append(run); run = []
                        if ok and not run:
                            # a table moves only if code names its first byte, and
                            # nothing just before it is code taken as data (an inline
                            # dispatch table after `call 0x4067`, 1:7C93, is neither)
                            if k not in self.z48_dataref: ok = False
                            elif any(x < it[0] <= v + 64 for x, v in bases): ok = False
                            elif any(bb == b and 0 < it[0] - a <= 64 for bb, a in self.z48_codedata): ok = False
                        if ok: run.append((b, it)); continue
                        if run: runs.append(run)
                        run = []
                for run in sorted(runs, key=lambda r: -sum(it[1] for _, it in r)):
                    n = sum(it[1] for _, it in run)
                    r = min((r for r in free if r[1] - r[0] >= n), key=lambda r: r[1] - r[0], default=None)
                    if r is None: continue
                    b0, it0 = run[0]
                    oh.append('    org 0x%04X          ; %d:%04X, %d bytes' % (r[0], b0, it0[0], n))
                    for b, it in run:
                        self.emit_item(b, it, 'OV', oh); moved[(b, it[0])] = r[0]
                    r[0] += n
            # then the stage's own code: runs of whole instructions from just
            # after a return or jump to one (nothing runs into them or out of
            # them), with no relative jump into or out of the run and nothing
            # in it taken as data
            if free:
                def term(b, a):
                    bs = self.raw[b][a - ORG[b]:a - ORG[b] + 2]
                    return bs[0] in (0xC9, 0xC3, 0x18, 0xE9) or (bs[0] in (0xDD, 0xFD) and bs[1] == 0xE9) or (bs[0] == 0xED and bs[1] in (0x4D, 0x45))
                def jr_t(b, a):
                    bs = self.raw[b][a - ORG[b]:a - ORG[b] + 2]
                    if bs[0] not in (0x10, 0x18, 0x20, 0x28, 0x30, 0x38): return None
                    return a + 2 + (bs[1] - 256 if bs[1] > 127 else bs[1])
                taken = {(b, a) for b, a in self.z48_codedata} | {(b, x) for b, x, v in self.z48_base}
                blocks = []
                for b in (0, 1, 2, 3):
                    its = self.items[b]; jrs = {}
                    for it in its:
                        if it[2] == 'code' and self.home.get((b, it[0])) == 'OV':
                            t = jr_t(b, it[0])
                            if t is not None: jrs[it[0]] = t
                    cur = []; ok_start = False
                    for j, it in enumerate(its):
                        k = (b, it[0])
                        good = self.home.get(k) == 'OV' and k not in moved and it[2] == 'code' and k not in taken and not left_out(*k)
                        if not good:
                            cur = []; ok_start = j > 0 and its[j - 1][2] == 'code' and term(b, its[j - 1][0]) and False
                            ok_start = False; continue
                        if not cur:
                            pv = its[j - 1] if j else None
                            if not (pv and pv[2] == 'code' and term(b, pv[0])): continue      # (something may run into it)
                        cur.append(it)
                        if term(b, it[0]):
                            lo, hi = cur[0][0], it[0] + it[1]
                            inside = lambda x: lo <= x < hi
                            if all(inside(jrs[i[0]]) for i in cur if i[0] in jrs) and not any(inside(t) for a, t in jrs.items() if not inside(a)):
                                blocks.append((b, list(cur)))
                            cur = []
                ncode = 0
                for b, blk in sorted(blocks, key=lambda x: -sum(i[1] for i in x[1])):
                    n = sum(i[1] for i in blk)
                    r = min((r for r in free if r[1] - r[0] >= n), key=lambda r: r[1] - r[0], default=None)
                    if r is None: continue
                    oh.append('    org 0x%04X          ; %d:%04X, %d bytes (code)' % (r[0], b, blk[0][0], n))
                    for it in blk:
                        self.emit_item(b, it, 'OV', oh); moved[(b, it[0])] = r[0]
                    r[0] += n; ncode += n
                self.report['z48 own code in the high areas'] = ncode
            self.report['z48 own tables in the high areas'] = len(moved)
            open(NEM_ROOT + '/spec/z48_ovhigh.asm', 'w').write('\n'.join(oh) + '\n')
            for b in (0, 1, 2, 3):
                for k, it in enumerate(self.items[b]):
                    if self.home[(b, it[0])] == 'OV' and (b, it[0]) not in moved: self.z48_emit(b, k, 'OV', sections)
            zs = ['; generated by gen.py: the jump slots of the shared layout (the same', '; in every stage\'s build; each jumps to the stage\'s item or the trap)']
            for k in sorted(self.z48_slots):
                zs.append('zs_%d_%04X:' % k)
                if self.home[k] != 'dropped': t = 'm%d_%04X' % k
                elif k in Z48_FEONLY: t = 'z48_fe'         # (the front end: stage 1's, loaded for it)
                else: t = 'z48_trap'
                zs.append('    jp ' + t)
            zs.append('zs_end:')
            open(NEM_ROOT + '/spec/z48_slots.asm', 'w').write('\n'.join(zs) + '\n')
            # the shared table area, after the slots: the same place for a
            # table in every stage's build; this stage's own tables in it
            ta = ['; generated by gen.py: the shared table area (the tables the core', '; reads that not every stage keeps; stage %d\'s own here)' % Z48_STAGE_N, 'z48_ta:']
            for run, st, size, off in self.z48_ta_runs:
                b, a0 = run[0]
                if Z48_STAGE_N in st:
                    ta.append('    org z48_ta + %d          ; %d:%04X, %d bytes (stages %s)' % (off, b, a0, size, ','.join(map(str, sorted(st)))))
                    for it in self.items[b]:
                        if (b, it[0]) in run: self.emit_item(b, it, 'OV', ta)
                else:
                    for b2, a in run: ta.append('m%d_%04X equ z48_ta + %d' % (b2, a, off + a - a0))
            ta += ['    org z48_ta + %d' % self.z48_ta_size, 'z48_ta_end:']
            open(NEM_ROOT + '/spec/z48_tables.asm', 'w').write('\n'.join(ta) + '\n')
            self.report['z48 slots'] = len(self.z48_slots)
        if drops:
            # A left-out item is z48_trap, which shows a jump or call to it;
            # but one whose address a kept item takes as data (a table's
            # base, from which it reads further on: 3:A5AF, the stage list
            # from 1) is placed where it would be, before the next kept item.
            out.append('\n; ===== items the 48K demo leaves out (gen.py Z48) =====')
            for b, k in drops:
                its = self.items[b]; a = its[k][0]
                if (b, a) in self.z48_dref:
                    n = next((it[0] for it in its[k + 1:] if self.home[(b, it[0])] not in (('dropped', 'OV') if Z48_SHARED else ('dropped',))), None)
                    if n is not None and n - a <= 256:
                        out.append('m%d_%04X equ m%d_%04X-%d' % (b, a, b, n, n - a)); self.report['z48 data base'] += 1
                        continue
                    self.report['z48 data ref trapped'] += 1
                    print('z48: %d:%04X, left out, is taken as data (a trap)' % (b, a))
                out.append('m%d_%04X equ z48_trap' % (b, a))
            self.report['z48 dropped'] = len(drops)
        if Z48:
            open(NEM_ROOT + '/reloc/z48_codedata.txt', 'w').write(''.join('%d %04X\n' % x for x in sorted(self.z48_codedata)))
            for b, a in self.z48_codedata:      # a code item's own address as a base, data just after (2:90D4's 9262)
                k = self.starts[b].index(a)
                if any(it[2] != 'code' for it in self.items[b][k + 1:k + 4] if it[0] <= a + 8):
                    self.z48_base.add((b, a, a))
            open(NEM_ROOT + '/reloc/z48_nocut.txt', 'w').write(''.join('%d %04X %04X\n' % x for x in sorted(self.z48_base)))
        for sec, body in sections.items():
            out.append('\n; ===== section %s =====' % sec)
            out.append('    section_%s' % sec)
            out += body
            out.append('section_%s_end:' % sec)
        for b, data in self.placed_data().items():
            if b in NO_EMIT: continue
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
        assert Z48 or g.report['next patched'] == len([k for k in NEXT_PATCH if not left_out(*k) or k in NEXT_KEEP]), 'a Next hook site is not an item start'   # (the 48K leaves some sites out)
