"""
LC_DCO_NMOS Full Layout Generator — IHP SG13G2 130nm
Generates a complete transistor-level layout using IHP PCells via KLayout batch mode.

Run with:
  KLAYOUT_PATH=/home/whqkrel/tools/IHP-Open-PDK/ihp-sg13g2/libs.tech/klayout \
  klayout -zz -r generate_lc_dco_layout.py

PCells used (library: SG13_dev):
  nmos     — NMOS LV transistors  (M1, M2 cross-coupled pair, M_tail, M_sense)
  ntap1    — N-substrate tap      (guard rings / substrate contacts)
  cmim     — MIM capacitor        (C_F tank caps, cap bank)
  inductor2— Differential inductor (LC tank, L=4nH)
"""

import pya
import sys, os, math

# ── Output path ───────────────────────────────────────────────────────────────
OUT_GDS  = '/home/whqkrel/rfic_project/layouts/lc_dco_nmos_full.gds'
OUT_OAS  = '/home/whqkrel/rfic_project/layouts/lc_dco_nmos_full.oas'
LIB_NAME = 'SG13_dev'
TECH     = 'sg13g2'

# ── Layer map (GDS layer/datatype → pya.LayerInfo) ───────────────────────────
def L(layer, dt=0):
    return pya.LayerInfo(layer, dt)

LY = {
    'activ':     L(1,  0),
    'gatpoly':   L(5,  0),
    'cont':      L(6,  0),
    'nsd':       L(7,  0),
    'psd':       L(14, 0),
    'nwell':     L(31, 0),
    'metal1':    L(8,  0),
    'via1':      L(19, 0),
    'metal2':    L(10, 0),
    'via2':      L(29, 0),
    'metal3':    L(30, 0),
    'via3':      L(49, 0),
    'metal4':    L(50, 0),
    'via4':      L(66, 0),
    'metal5':    L(67, 0),
    'topvia1':   L(125,0),
    'topmetal1': L(126,0),
    'topvia2':   L(133,0),
    'topmetal2': L(134,0),
    'mim':       L(36, 0),
}

# ── Design parameters ─────────────────────────────────────────────────────────
# All dimensions in μm unless noted

# NMOS cross-coupled pair (M1/M2)
NMOS_W  = 40e-6   # total width  = 40μm
NMOS_L  = 130e-9  # gate length  = 130nm
NMOS_NG = 20      # fingers: 20 × 2μm = 40μm

# NMOS tail current source (M_tail)
TAIL_W  = 200e-6  # total width  = 200μm
TAIL_L  = 500e-9  # gate length  = 500nm
TAIL_NG = 40      # fingers: 40 × 5μm = 200μm

# NMOS sense transistor (M_sense, 1/5 scale of tail)
SENSE_W = 40e-6
SENSE_L = 500e-9
SENSE_NG = 8

# MIM capacitor C_F: 1.975pF each side
# cmim density ≈ 1.0 fF/μm² → area = 1975 μm² → ~44×45μm
CMIM_W = 44e-6
CMIM_L = 45e-6

# Differential inductor (inductor2): L≈4nH
# w=6μm wire, s=3μm space, d_inner=60μm, ~3.5 turns → L≈4nH
IND_W  = '6e-6'   # wire width
IND_S  = '3e-6'   # turn spacing
IND_D  = '60e-6'  # inner diameter
IND_NR = 3        # number of turns (integer)

# Substrate tap
TAP_W = '10e-6'
TAP_L = '10e-6'


def fmt(val_m):
    """Format a value in meters as a string for PCell parameters."""
    return f'{val_m:.6e}'


def add_pcell(layout, top_cell, name, params, x_um, y_um):
    """Instantiate a PCell from SG13_dev library at position (x_um, y_um) in μm."""
    try:
        cell = layout.create_cell(name, LIB_NAME, params)
    except Exception as e:
        print(f'  [WARN] PCell "{name}" creation failed: {e}')
        return None
    trans = pya.DCellInstArray(cell, pya.DTrans(pya.DVector(x_um, y_um)))
    top_cell.insert(trans)
    print(f'  Placed {name} at ({x_um:.1f}, {y_um:.1f}) μm  bbox={cell.dbbox()}')
    return cell


def add_rect(cell, layer_info, x1, y1, x2, y2):
    """Add a filled rectangle on given layer (coords in μm)."""
    shape = pya.DBox(x1, y1, x2, y2)
    cell.shapes(cell.layout().layer(layer_info)).insert(shape)


def add_label(cell, layer_info, text, x, y):
    """Add a text label."""
    cell.shapes(cell.layout().layer(layer_info)).insert(
        pya.DText(text, pya.DVector(x, y))
    )


def route_metal(cell, layer, x1, y1, x2, y2, width):
    """Route a metal wire from (x1,y1) to (x2,y2) with given width on layer."""
    if abs(x2 - x1) > abs(y2 - y1):
        # horizontal dominant: L-route via y-first segment
        add_rect(cell, layer, min(x1,x2)-width/2, y1-width/2, max(x1,x2)+width/2, y1+width/2)
        add_rect(cell, layer, x2-width/2, min(y1,y2)-width/2, x2+width/2, max(y1,y2)+width/2)
    else:
        add_rect(cell, layer, x1-width/2, min(y1,y2)-width/2, x1+width/2, max(y1,y2)+width/2)
        add_rect(cell, layer, min(x1,x2)-width/2, y2-width/2, max(x1,x2)+width/2, y2+width/2)


def generate():
    # ── Create layout ─────────────────────────────────────────────────────────
    layout = pya.Layout()
    layout.dbu = 0.001  # 1nm resolution

    # Load technology
    tech = pya.Technology.technology_by_name(TECH)
    if tech is None:
        print(f'WARNING: Technology "{TECH}" not found. Layers may not be named correctly.')
    else:
        layout.technology_name = TECH
        print(f'Technology "{TECH}" loaded.')

    # Check PCell library
    lib = pya.Library.library_by_name(LIB_NAME, TECH)
    if lib is None:
        lib = pya.Library.library_by_name(LIB_NAME)
    if lib is None:
        print(f'ERROR: PCell library "{LIB_NAME}" not found.')
        print(f'Available libraries: {pya.Library.library_names()}')
        sys.exit(1)
    print(f'PCell library "{LIB_NAME}" found.')

    top = layout.create_cell('LC_DCO_NMOS')

    # ══════════════════════════════════════════════════════════════════════════
    # FLOORPLAN (all coordinates in μm, origin at bottom-left)
    #
    #   Y=350 ┌─────────────────────────────────────────────┐
    #         │  [Inductor2: ~140×140μm, center=(115, 280)] │
    #   Y=200 │                                             │
    #         │  [C1_cmim]          [C2_cmim]               │
    #   Y=140 │  @(10,140)          @(175,140)              │
    #         │     [M1_nmos]  [M2_nmos]                    │
    #   Y=60  │     @(30,60)   @(130,60)                    │
    #         │         [M_tail@(60,0)]                     │
    #   Y=0   │  [ntap] [M_sense@(10,-50)] [ntap]           │
    #         └─────────────────────────────────────────────┘
    #              X=0                           X=230
    # ══════════════════════════════════════════════════════════════════════════

    print('\n--- Placing PCells ---')

    # ── Differential Inductor L1 (inductor2, 4nH) ────────────────────────────
    ind = add_pcell(layout, top, 'inductor2', {
        'w':    IND_W,
        's':    IND_S,
        'd':    IND_D,
        'nr_r': IND_NR,
        'l':    '4e-9',
        'r':    '1.25',
    }, x_um=45, y_um=190)

    # ── NMOS cross-coupled pair ───────────────────────────────────────────────
    # M1 (left) and M2 (right) — mirrored placement for symmetric routing
    m1 = add_pcell(layout, top, 'nmos', {
        'w':  fmt(NMOS_W),
        'l':  fmt(NMOS_L),
        'ng': NMOS_NG,
        'm':  1,
    }, x_um=10, y_um=60)

    m2 = add_pcell(layout, top, 'nmos', {
        'w':  fmt(NMOS_W),
        'l':  fmt(NMOS_L),
        'ng': NMOS_NG,
        'm':  1,
    }, x_um=130, y_um=60)

    # ── NMOS tail current source M_tail ──────────────────────────────────────
    m_tail = add_pcell(layout, top, 'nmos', {
        'w':  fmt(TAIL_W),
        'l':  fmt(TAIL_L),
        'ng': TAIL_NG,
        'm':  1,
    }, x_um=10, y_um=0)

    # ── NMOS sense transistor M_sense (for LDO current sense) ────────────────
    m_sense = add_pcell(layout, top, 'nmos', {
        'w':  fmt(SENSE_W),
        'l':  fmt(SENSE_L),
        'ng': SENSE_NG,
        'm':  1,
    }, x_um=10, y_um=-60)

    # ── MIM capacitors C1 and C2 (tank capacitors, 1.975pF each) ─────────────
    c1 = add_pcell(layout, top, 'cmim', {
        'w': fmt(CMIM_W),
        'l': fmt(CMIM_L),
        'm': 1,
    }, x_um=10, y_um=140)

    c2 = add_pcell(layout, top, 'cmim', {
        'w': fmt(CMIM_W),
        'l': fmt(CMIM_L),
        'm': 1,
    }, x_um=175, y_um=140)

    # ── Substrate taps ntap1 (guard ring around active devices) ──────────────
    for (tx, ty) in [(0, 120), (200, 120), (0, 0), (200, 0)]:
        add_pcell(layout, top, 'ntap1', {
            'w': TAP_W,
            'l': TAP_L,
        }, x_um=tx, y_um=ty)

    # ══════════════════════════════════════════════════════════════════════════
    # METAL ROUTING
    # Basic connections using Metal2 (5μm wide) for signal nets
    # and Metal1 (3μm wide) for local connections
    # ══════════════════════════════════════════════════════════════════════════

    print('\n--- Adding routing ---')
    M1  = layout.layer(LY['metal1'])
    M2  = layout.layer(LY['metal2'])
    M5  = layout.layer(LY['metal5'])
    TM1 = layout.layer(LY['topmetal1'])
    TM2 = layout.layer(LY['topmetal2'])

    W_SIG  = 5.0   # signal wire width μm (metal2)
    W_PWR  = 8.0   # power wire width μm
    W_LOC  = 2.0   # local wire width μm (metal1)

    # outp bus: left side of inductor → M1 drain → C1 top
    # approximate pin locations (estimated from PCell bboxes):
    OUTP_X = 55.0   # X of outp net rail
    OUTN_X = 175.0  # X of outn net rail
    VS_X   = 80.0   # X of vs rail
    GND_Y  = -20.0  # Y of GND rail

    # ── outp vertical bus (Metal2) ────────────────────────────────────────────
    add_rect(top, LY['metal2'],
             OUTP_X - W_SIG/2, GND_Y,
             OUTP_X + W_SIG/2, 330.0)
    add_label(top, LY['metal2'], 'outp', OUTP_X, 330.0)

    # ── outn vertical bus (Metal2) ────────────────────────────────────────────
    add_rect(top, LY['metal2'],
             OUTN_X - W_SIG/2, GND_Y,
             OUTN_X + W_SIG/2, 330.0)
    add_label(top, LY['metal2'], 'outn', OUTN_X, 330.0)

    # ── vs (shared source) bus (Metal1) ──────────────────────────────────────
    add_rect(top, LY['metal1'],
             10.0, 50.0,
             210.0, 50.0 + W_LOC)
    add_label(top, LY['metal1'], 'vs', VS_X, 52.0)

    # ── GND rail (Metal1, bottom) ─────────────────────────────────────────────
    add_rect(top, LY['metal1'],
             0.0, GND_Y - W_PWR/2,
             230.0, GND_Y + W_PWR/2)
    add_label(top, LY['metal1'], 'GND', 5.0, GND_Y)

    # ── VDD rail (Metal2, top) ────────────────────────────────────────────────
    add_rect(top, LY['metal2'],
             0.0, 355.0,
             230.0, 355.0 + W_PWR)
    add_label(top, LY['metal2'], 'vdd', 5.0, 358.0)

    # ── mid_L (inductor center tap → vdd) ────────────────────────────────────
    add_rect(top, LY['metal2'],
             110.0, 330.0,
             120.0, 355.0)

    # ── Sense resistor R_sns (Metal1 resistor: 1kΩ, ~10μm × 0.5μm of metal)  ─
    # Approximate using a narrow metal1 strip as routing placeholder
    add_rect(top, LY['metal1'],
             12.0, -65.0,
             14.0, -20.0)
    add_label(top, LY['metal1'], 'n_isns', 12.0, -45.0)

    # ── Top-level port pins on ToMetal2 ──────────────────────────────────────
    for (name, x, y) in [
        ('outp', OUTP_X, 345.0),
        ('outn', OUTN_X, 345.0),
        ('vdd',  115.0,  360.0),
        ('gnd',  5.0,    GND_Y),
        ('vs',   VS_X,   52.0),
    ]:
        add_rect(top, LY['topmetal2'],
                 x - 4, y - 4, x + 4, y + 4)
        add_label(top, LY['topmetal2'], name, x, y)

    # ══════════════════════════════════════════════════════════════════════════
    # CAP BANK stub connections (MSB/LSB caps)
    # Each bit is a cmim cap in series with a short-circuit (all codes = 0 = no cap)
    # For cap bank instantiation, use 5 cmim cells per polarity:
    # MSB cap bank: 62fF, 124fF, 248fF, 496fF, 992fF (one side each)
    # LSB cap bank: 44fF, 88fF, 176fF, 352fF, 704fF (one side each)
    # ══════════════════════════════════════════════════════════════════════════

    print('\n--- Adding cap bank stubs ---')
    msb_caps = [62e-18, 124e-18, 248e-18, 496e-18, 992e-18]
    lsb_caps = [44e-18, 88e-18, 176e-18, 352e-18, 704e-18]
    cap_density = 1.0e-15  # 1.0 fF/μm²

    x_cap_start = 0.0
    y_cap_row   = -120.0

    for i, cap_f in enumerate(msb_caps + lsb_caps):
        area_um2 = cap_f / cap_density * 1e12  # convert F to fF, then /1fF/μm²
        side_um  = max(2.0, math.sqrt(area_um2))
        label    = f'MSB{i}' if i < 5 else f'LSB{i-5}'
        xi = x_cap_start + i * (side_um + 3.0)
        add_pcell(layout, top, 'cmim', {
            'w': f'{side_um:.3f}e-6',
            'l': f'{side_um:.3f}e-6',
            'm': 1,
        }, x_um=xi, y_um=y_cap_row)

    # ══════════════════════════════════════════════════════════════════════════
    # Write output
    # ══════════════════════════════════════════════════════════════════════════
    print(f'\n--- Writing GDS: {OUT_GDS}')
    layout.write(OUT_GDS)
    print(f'--- Writing OAS: {OUT_OAS}')
    layout.write(OUT_OAS)

    bbox = top.dbbox()
    print(f'\nLayout complete:')
    print(f'  Top cell : LC_DCO_NMOS')
    print(f'  Bounding box: {bbox.width():.1f} × {bbox.height():.1f} μm')
    print(f'  GDS: {OUT_GDS}')
    print(f'  OAS: {OUT_OAS}')


if __name__ == '__main__':
    generate()
