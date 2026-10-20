#!/usr/bin/env python3
"""Generate the integrated program-to-read transition bench (issue #73).

    python3 sim/integrated-transition/make_bench.py            write testbench/
    python3 sim/integrated-transition/make_bench.py --check    fail on drift

The device under test is the committed derived netlists, assembled and never
copied: a reduced array slice (design/netlists/slice_*.spice: cells, row and
column local pass-gates, level shifters) with one program leg and one read leg
(design/netlists/program_leg.spice, read_leg.spice) attached per band to that
band's global bit-line bus BLG_<band>. The legs and the array are the same
netlists the component benches use.

Per slice and process corner it writes

    testbench/tb_<slice>_<process>.spice      klt circuit body (no .control/.end)
    testbench/<slice>_<process>.request.json  klt sim request (temperature axis x point list)
    testbench/probes_<slice>.json             manifest of every stress probe (device, terminals)

The corner/point grid is *expressed* here and executed by `klt sim` (on the
dispatch workers KLT_SIM_BACKEND=batch sends it to the Spot batch fleet); no
ngspice loop is hand-rolled anywhere in this directory.

Sequence driven (all control waveforms are bench-assumed, see README.md):

    0.00-0.30 us  idle/reset: PROG_EN = READ_EN = 0, selects 0, VPP at VDD
    0.30 us       external VPP ramps from VDD to V_PK over tvr
    1.00 us       ARM: row select, then column select (+tcsl) asserted; legs stay OFF
    1.50 us       PULSE: PROG_EN of the selected band asserted
    2.50 us       COMPLETION: PROG_EN deasserted
    2.50+skew us  READ: READ_EN asserted (skew = tren - 2.5)
    6.00 us       end

Scenarios are named rows of SCENARIOS; they change the timing keys only. The
point list is not a cross product: programmed-side variants are run only on the
scenarios where the filament changes the answer (README.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TB_DIR = HERE / "testbench"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "design"))
import gen_array as G  # noqa: E402
import nlflat as N  # noqa: E402

# --- placeholders (every one is repeated in every record) --------------------
VDD = 3.3
VCLAMP = 1.8
V_PK = 5.0                   # external VPP plateau, nominal. Placeholder, NOT a programming condition.
RAILS = {"I": 5.0, "II": 5.5, "III": 5.0}   # per-band VDDH, as sim/array-slice-bench
SUPPLY_SCALES = (0.9, 1.0, 1.1)
I_REF = 1e-6
R_BLEED = 10e9               # bus bleed to VSS so a floating bus has a defined DC start
GFIL = {"prog_lo": 1.0 / 10e3, "prog_hi": 1.0 / 100e3}   # assumed R_prog (no breakdown model)
TEMPS = (-40, 27, 125)
PROCESS = {
    "typical": ("typical", "moscap_typical", "res_typical"),
    "ff": ("ff", "moscap_ff", "res_ff"),
    "ss": ("ss", "moscap_ss", "res_ss"),
    "fs": ("fs", "moscap_typical", "res_typical"),
    "sf": ("sf", "moscap_typical", "res_typical"),
}

# --- timeline (microseconds; the keys carry them as "volts") -----------------
PWR_RAMP = 0.25              # power-up ramp, us (C-infinity)
T_PWR = 0.5                  # nothing is measured before this (power-up settle), us
T_VPP0, T_ARM = 0.6, 1.2
EDGE = 100e-9                 # control edge time (C-infinity, see edge())
T_END = 6.3
T_IDLE = 0.55                # baseline sample, us
W_ARM = (0.6e-6, 1.75e-6)    # VPP ramp + armed, before the pulse
W_PULSE = (1.85e-6, 2.76e-6) # PROG_EN high
W_READ = (2.76e-6, 6.25e-6)  # completion .. end
W_ALL = (0.6e-6, 6.25e-6)
W_ARM_FLAT = (1.65e-6, 1.75e-6)   # last 100 ns of the armed state, before the pulse
W_PUL_FLAT = (2.40e-6, 2.76e-6)   # flat top of the pulse
W_RD_FLAT = (4.80e-6, 5.80e-6)    # late read
SAMPLES = (2.85, 2.90, 3.00, 3.10, 3.30, 3.55, 3.80, 4.30, 5.30, 6.20)   # us, absolute

NEVER = 99.0
SCENARIOS = {
    #            tvr   tcsl  tpe  tpf   tren  tdis
    "base":      dict(tvr=0.02, tcsl=0.00, tpe=1.8, tpf=2.8, tren=2.80, tdis=NEVER),
    "vslow":     dict(tvr=0.50, tcsl=0.00, tpe=1.8, tpf=2.8, tren=2.80, tdis=NEVER),
    "rd_ovl":    dict(tvr=0.02, tcsl=0.00, tpe=1.8, tpf=2.8, tren=2.78, tdis=NEVER),
    "rd_gap":    dict(tvr=0.02, tcsl=0.00, tpe=1.8, tpf=2.8, tren=3.00, tdis=NEVER),
    "csel_late": dict(tvr=0.02, tcsl=0.10, tpe=1.8, tpf=2.8, tren=2.80, tdis=NEVER),
    "timeout":   dict(tvr=0.02, tcsl=0.00, tpe=NEVER, tpf=NEVER, tren=2.80, tdis=2.8),
}
# filament variants: conductance across the SELECTED cell's capacitor (siemens)
VARIANTS = {"unprog": 0.0, "prog_lo": GFIL["prog_lo"], "prog_hi": GFIL["prog_hi"]}

# The matrix is two tiers, because a fleet unit costs about 12 s (ngspice-46, 5 ns step) and a full product would be
# thousands of units (README.md "Cost and the two tiers"):
#   A: the full 45-corner PVT grid (5 process x 3 temperature x 3 supply scale) for the base case
#      (immediate read after the pulse), every selected cell (all four capacitor x access sub-combinations of each region),
#      unprogrammed and with the assumed 10 kohm filament;
#   B: the remaining scenarios (VPP ramp, interlock overlap, read gap, late column select, arm timeout, the
#      100 kohm filament) on the two opposite sub-combinations of each region, at 7 PVT corners chosen as the
#      slow/cold/low-supply and fast/hot/high-supply extremes plus the two skewed process corners at typical.
TIER_POINTS = {
    "A": (("base", "unprog"), ("base", "prog_lo")),
    "B": (("vslow", "unprog"), ("rd_ovl", "unprog"), ("rd_gap", "unprog"), ("csel_late", "unprog"),
          ("timeout", "unprog"), ("rd_ovl", "prog_lo"), ("rd_gap", "prog_lo"), ("base", "prog_hi")),
}
# tier B corners: process -> (temperatures, supply scales)
TIER_B_CORNERS = {
    "typical": ((27,), (1.0,)),
    "ss": ((-40, 125), (0.9,)),
    "ff": ((-40, 125), (1.1,)),
    "fs": ((27,), (1.0,)),
    "sf": ((27,), (1.0,)),
}
UNITS_PER_HOST = 16          # fleet shard size: ~4 min of simulation per job, far below the 3600 s whole-job ceiling

# slice -> selected cells (one per access/capacitor level pair where the slice has it)
# Rows 0-3 of one column per band give all four capacitor x access sub-combinations (design/gen_array.py
# level_indices: capacitor level alternates with the row, access level every second row). The columns are
# the ones adjacent to the region boundaries (I|II: 10, 11; II|III: 22); Region II is covered by slice_i_ii only.
SLICE_CELLS = {
    "slice_i_ii": [(r, c) for c in (10, 11) for r in range(4)],
    "slice_ii_iii": [(r, 22) for r in range(4)],
}
# tier B: rows 0 and 3 of the same columns are opposite on both the capacitor and the access level
TIER_B_ROWS = (0, 3)
NETLIST_FILES = ["cell_candidate1", "cell_candidate2", "cell_candidate3", "ls_hv06", "ls_hv10", "pg_n06",
                 "pg_n10", "leg_interlock", "program_leg", "read_leg"]


def window(sl):
    r0, r1, c0, c1 = G.SLICES[sl]
    return list(range(r0, r1 + 1)), list(range(c0, c1 + 1))


def bands_in(cols):
    return [b[0] for b in G.BANDS if any(b[1] <= c <= b[2] for c in cols)]


def tier_cells(sl, tier):
    return [c for c in SLICE_CELLS[sl] if tier == "A" or c[0] in TIER_B_ROWS]


def tier_scales(proc, tier):
    return SUPPLY_SCALES if tier == "A" else TIER_B_CORNERS[proc][1]


def tier_temps(proc, tier):
    return TEMPS if tier == "A" else TIER_B_CORNERS[proc][0]


def points(sl, proc, tier="A"):
    """Ordered operating points of one request (index = klt supply_v index)."""
    pts = []
    for cell in tier_cells(sl, tier):
        for sc in tier_scales(proc, tier):
            for scen, var in TIER_POINTS[tier]:
                pts.append({"cell": cell, "scale": sc, "scen": scen, "var": var})
    return pts


def ramp(x: str) -> str:
    """Unit step with C-infinity edge over x in [0, 1] (af_edge, defined in the deck)."""
    return f"af_edge({x})"


def us(name: str) -> str:
    return f"v({name})*1u"


# ---------------------------------------------------------------------------
# Probe roster (derived from the committed netlists)
# ---------------------------------------------------------------------------

# HV-exposed devices only. The 3.3 V interlock, the sense inverters, the program leg's 3.3 V ponb inverter
# and the level shifters' own 3.3 V input inverter see nothing but VDD/VSS by construction: not probed.
LOW_V_LEAF = ("xmn5", "xmp5", "xmn6", "xmp6", "xmn7", "xmp7")


def skip_leaf(path: str) -> bool:
    last = path.split(".")[-1]
    if ".xil." in path or last in LOW_V_LEAF:
        return True
    return (".xlc_" in path or ".xlr_" in path) and last in ("xm1", "xm2")


def region_of(path: str):
    """(region label, role) of a flattened leaf path."""
    import re
    m = re.search(r"\.xc_(\d+)_(\d+)\.", path)
    if m:
        return G.band_of_col(int(m.group(2)))[0], "cell"
    m = re.search(r"\.xpc_(\d+)$", path) or re.search(r"\.xpc_(\d+)\.", path)
    if m:
        return G.band_of_col(int(m.group(1)))[0], "colpg"
    m = re.search(r"\.xpr_\d+_(\w+?)(\.|$)", path)
    if m:
        return m.group(1).upper(), "rowpg"
    m = re.search(r"\.xlc_(\d+)\.", path)
    if m:
        return G.band_of_col(int(m.group(1)))[0], "colls"
    m = re.search(r"\.xlr_\d+_(\w+?)\.", path)
    if m:
        return m.group(1).upper(), "rowls"
    m = re.match(r"xpg_(\w+?)\.", path)
    if m:
        return m.group(1).upper(), "progleg"
    m = re.match(r"xrd_(\w+?)\.", path)
    if m:
        return m.group(1).upper(), "readleg"
    raise ValueError(path)


def slice_nets(subs, sl):
    """Testbench nets on the slice ports, in port order (VSS is ground, VDDL is the VDD rail)."""
    return ["0" if p == "vss" else "vdd" if p == "vddl" else p for p in subs[sl]["ports"]]


def roster(sl):
    """Leaf devices to probe: (leaf, region, role)."""
    subs = N.parse(NETLIST_FILES + [sl])
    rows, cols = window(sl)
    bands = bands_in(cols)
    leaves = N.flatten(subs, sl, "x_dut", slice_nets(subs, sl))
    for b in bands:
        bl = b.lower()
        leaves += N.flatten(subs, "program_leg", f"xpg_{bl}", [f"pen_{bl}", f"ren_{bl}", "vdd", "0", f"blp_{bl}", "vpp"])
        leaves += N.flatten(subs, "read_leg", f"xrd_{bl}", [f"pen_{bl}", f"ren_{bl}", "vclamp", f"iref_{bl}", "vdd",
                                                          "0", f"blr_{bl}", f"sense_{bl}", f"rdata_{bl}"])
    out = []
    for lf in leaves:
        k = N.kind(lf.model)
        if k == "other":
            continue
        if skip_leaf(lf.path):
            continue
        reg, role = region_of(lf.path)
        out.append((lf, reg, role))
    return out


def pairs(lf):
    """Terminal pairs probed for a leaf: MOS (d g s b) -> gs gd ds; cap/res -> its two terminals."""
    k = N.kind(lf.model)
    if k == "mos":
        d, g, s, _b = lf.nodes
        return [("gs", g, s), ("gd", g, d), ("ds", d, s)]
    a, b = lf.nodes[0], lf.nodes[1]
    return [("t12", a, b)]


# ---------------------------------------------------------------------------
# Deck
# ---------------------------------------------------------------------------


def netlist(sl: str, proc: str) -> str:
    rows, cols = window(sl)
    bands = bands_in(cols)
    # slice port order comes from the committed netlist
    subs = N.parse(NETLIST_FILES + [sl])
    ports = [p.upper() if p.lower() not in ("vss", "vddl") else n for p, n in zip(subs[sl]["ports"], slice_nets(subs, sl))]
    L = [
        f"* gf180-antifuse sim/integrated-transition: {sl}, process corner {proc} (GENERATED by make_bench.py - do not edit)",
        "* Circuit body for `klt sim`. The MOS and moscap sections come from the request's corner bundle;",
        "* design.ngspice (global switches) and the 10 V LDMOS library's matching section are resolved from",
        "* $PDK_ROOT on whichever host runs the corner. See README.md for the sequence and the assumptions.",
        ".include $PDK_ROOT/gf180mcuD/libs.tech/ngspice/design.ngspice",
        f'.lib "$PDK_ROOT/gf180mcuD/libs.tech/ngspice/smbb000149.ngspice" {PROCESS[proc][0]}',
        "* derived netlists of the design under test (design/netlists/, never copied)",
    ]
    for nl in NETLIST_FILES + [sl]:
        L.append(f".include ../../../design/netlists/{nl}.spice")
    L += ["", f"X_dut {' '.join(ports)} {sl}", ""]

    L += ["* ---- supplies. Sweep keys are the V* elements (element name == klt supply_v key) and hold the",
          "* final level; each rail reaches it through a C-infinity power-up ramp (B element), because under",
          "* `uic` every node starts at 0 V and a step would be an unphysical power-up. Nothing is measured",
          f"* before {T_PWR} us. VPP and the bit-line buses are NOT ramped separately: VPP follows VDD up, then",
          "* ramps to Vpk as a scenario event.",
          f"Vdd vddk 0 DC {VDD}", f"Vclamp vclampk 0 DC {VCLAMP}", f"Vpk vpk 0 DC {V_PK}",
          f"Bdd vdd 0 V='v(vddk)*af_edge((time+20n)/{PWR_RAMP}u)'",
          f"Bclamp vclamp 0 V='v(vclampk)*af_edge((time+20n)/{PWR_RAMP}u)'"]
    for b in bands:
        L.append(f"Vddh_{b} VDDHK_{b} 0 DC {RAILS[b]}")
        L.append(f"Bddh_{b} VDDH_{b} 0 V='v(VDDHK_{b})*af_edge((time+20n)/{PWR_RAMP}u)'")
        L.append(f"Vplg_{b} PLG_{b} 0 DC 0")
    L += ["", "* ---- scenario keys: times in microseconds (value in 'volts'), enables are 0/1 ----"]
    for t in ("tvr", "tcsl", "tpe", "tpf", "tren", "tdis"):
        L.append(f"V{t} {t} 0 DC {SCENARIOS['base'][t]}")
    for r in rows:
        L.append(f"Ven_r{r} en_r{r} 0 DC 0")
    for c in cols:
        L.append(f"Ven_c{c} en_c{c} 0 DC 0")
    for b in bands:
        L.append(f"Vbsel_{b} bsel_{b} 0 DC 0")
    L.append("Vgfil gfil 0 DC 0")

    L += ["", "* ---- control waveforms (behavioural; logic highs track VDD like the legs bench) ----",
          "* C-infinity edge f(u)/(f(u)+f(1-u)), f(u)=exp(-1/u): the stock moscap macro stalls on slope",
          "* discontinuities (sim/cell-breakdown-model/README.md, 'Transient convergence (#74)')",
          ".func af_fe(u) {exp(-1/max(u,1e-6))}",
          ".func af_edge(x) {af_fe(min(max(x,0),1))/(af_fe(min(max(x,0),1))+af_fe(1-min(max(x,0),1)))}",
          f"* external VPP: idle at VDD, ramps to Vpk starting {T_VPP0} us over tvr (>= 20 ns)",
          f"Bvpp vpp 0 V='v(vdd)+(v(vpk)-v(vdd))*{ramp(f'(time-{T_VPP0}u)/max({us('tvr')},20n)')}'"]
    for r in rows:
        L.append(f"Brsel{r} RSEL_{r} 0 V='v(vdd)*v(en_r{r})*({ramp(f'(time-{T_ARM}u)/{EDGE:g}')}-{ramp(f'(time-{us('tdis')})/{EDGE:g}')})'")
    for c in cols:
        L.append(f"Bcsel{c} CSEL_{c} 0 V='v(vdd)*v(en_c{c})*({ramp(f'(time-{T_ARM}u-{us('tcsl')})/{EDGE:g}')}-{ramp(f'(time-{us('tdis')})/{EDGE:g}')})'")
    for b in bands:
        bl = b.lower()
        L.append(f"Bpen_{bl} pen_{bl} 0 V='v(vdd)*v(bsel_{b})*({ramp(f'(time-{us('tpe')})/{EDGE:g}')}-{ramp(f'(time-{us('tpf')})/{EDGE:g}')})'")
        L.append(f"Bren_{bl} ren_{bl} 0 V='v(vdd)*v(bsel_{b})*{ramp(f'(time-{us('tren')})/{EDGE:g}')}'")

    L += ["", "* ---- legs on each band's global bit-line bus; ammeters read the leg currents ----",
          "* i(vamp_<b>) > 0: program leg drives the bus.  i(vamr_<b>) < 0: bus sinks into the read leg."]
    for b in bands:
        bl = b.lower()
        L += [f"Vamp_{bl} blp_{bl} BLG_{b} DC 0",
              f"Vamr_{bl} blr_{bl} BLG_{b} DC 0",
              f"Xpg_{bl} pen_{bl} ren_{bl} vdd 0 blp_{bl} vpp program_leg",
              f"Xrd_{bl} pen_{bl} ren_{bl} vclamp iref_{bl} vdd 0 blr_{bl} sense_{bl} rdata_{bl} read_leg",
              f"Iref_{bl} 0 iref_{bl} DC {I_REF:g}",
              f"Rbleed_{bl} BLG_{b} 0 {R_BLEED:g}",
              f"* both-legs-on detector: min(PON, RON) (volts); 0 means never both ON",
              f"Bboth_{bl} both_{bl} 0 V='min(v(xpg_{bl}.pon),v(xrd_{bl}.ron))'"]

    L += ["", "* ---- assumed programmed-cell filament across the SELECTED cell's capacitor only ----",
          "* (conductance = v(gfil); 0 = unprogrammed). Not a breakdown model."]
    for r in rows:
        for c in cols:
            lab, _ = G.band_of_col(c)
            cn, pl = f"x_dut.xc_{r}_{c}.cn", f"x_dut.pl_{r}_{lab}"
            L.append(f"Bfil_{r}_{c} {cn} {pl} I='v({cn},{pl})*v(gfil)*v(en_r{r})*v(en_c{c})'")
    L += ["", "* ---- stress probes: |V(a)-V(b)| of every terminal pair of every HV-exposed device ----",
          "* (ngspice allows at most 99 par() calls and no v(a,b) in .meas, so each pair is a B source)"]
    for k, (lf, _reg, _role) in enumerate(roster(sl)):
        for pn, a, b in pairs(lf):
            L.append(f"Bsp_st{k}{pn} sp_st{k}{pn} 0 V='abs(v({a})-v({b}))'")
    return "\n".join(L) + "\n"


def meas(name: str, card: str, unit: str) -> dict:
    return {"name": name, "spice": f".meas tran {name} {card}", "unit": unit}


def win(w):
    return f"FROM={w[0]:g} TO={w[1]:g}"


def measurements(sl: str):
    rows, cols = window(sl)
    bands = bands_in(cols)
    m = []
    for b in bands:
        bl = b.lower()
        sense, rdata, blg = f"v(sense_{bl})", f"v(rdata_{bl})", f"v(BLG_{b})"
        m.append(meas(f"sense_idle_{bl}", f"FIND {sense} AT={T_IDLE}u", "V"))
        m.append(meas(f"blg_idle_{bl}", f"FIND {blg} AT={T_IDLE}u", "V"))
        for wn, w in (("arm", W_ARM), ("pul", W_PULSE), ("rd", W_READ)):
            for fn in ("MAX", "MIN"):
                m.append(meas(f"sense_{fn.lower()}_{wn}_{bl}", f"{fn} {sense} {win(w)}", "V"))
                m.append(meas(f"blg_{fn.lower()}_{wn}_{bl}", f"{fn} {blg} {win(w)}", "V"))
            for fn in ("MAX", "MIN"):
                m.append(meas(f"rdata_{fn.lower()}_{wn}_{bl}", f"{fn} {rdata} {win(w)}", "V"))
            m.append(meas(f"pon_max_{wn}_{bl}", f"MAX v(xpg_{bl}.pon) {win(w)}", "V"))
            m.append(meas(f"ron_max_{wn}_{bl}", f"MAX v(xrd_{bl}.ron) {win(w)}", "V"))
        m.append(meas(f"rdata_idle_{bl}", f"FIND {rdata} AT={T_IDLE}u", "V"))
        m.append(meas(f"both_max_{bl}", f"MAX v(both_{bl}) {win(W_ALL)}", "V"))
        for i, ts in enumerate(SAMPLES):
            m.append(meas(f"sense_s{i}_{bl}", f"FIND {sense} AT={ts:g}u", "V"))
            m.append(meas(f"rdata_s{i}_{bl}", f"FIND {rdata} AT={ts:g}u", "V"))
            m.append(meas(f"blg_s{i}_{bl}", f"FIND {blg} AT={ts:g}u", "V"))
        # Leg currents are WINDOW AVERAGES, never instantaneous values or peaks: the trapezoidal integrator rings
        # at the time-step rate (alternating +-1.6 uA on a floating bus after a select edge, seen in a local probe),
        # which an instantaneous or MAX/MIN current measurement would read as a real current. Gear integration
        # (`.options method=gear`) was tried and fails to converge on this deck.
        for wn, w in (("arm", W_ARM_FLAT), ("pul", W_PUL_FLAT), ("rd", W_RD_FLAT)):
            m.append(meas(f"ipg_{wn}avg_{bl}", f"AVG i(vamp_{bl}) {win(w)}", "A"))
            m.append(meas(f"ird_{wn}avg_{bl}", f"AVG i(vamr_{bl}) {win(w)}", "A"))
    m.append(meas("vdd_t", f"FIND v(vdd) AT={T_IDLE}u", "V"))
    m.append(meas("vpp_end", "FIND v(vpp) AT=1.15u", "V"))

    # unselected-line bias: every word line, plate line, column-gate, bit line, over the whole run
    lines = []
    for b in bands:
        bl = b.lower()
        for r in rows:
            lines += [f"x_dut.wl_{r}_{bl}", f"x_dut.pl_{r}_{bl}"]
            if G.ACTIVE_LOW_WL[dict((x[0], x[3]) for x in G.BANDS)[b]]:
                lines.append(f"x_dut.rg_{r}_{bl}")
    lines += [f"x_dut.cg_{c}" for c in cols] + [f"x_dut.bl_{c}" for c in cols]
    for n in lines:
        tag = n.replace("x_dut.", "")
        for fn in ("MAX", "MIN"):
            m.append(meas(f"ln_{fn.lower()}_{tag}", f"{fn} v({n}) {win(W_ALL)}", "V"))
    for c in cols:
        for r in rows:
            m.append(meas(f"cnmax_{r}_{c}", f"MAX v(x_dut.xc_{r}_{c}.cn) {win(W_ALL)}", "V"))
            m.append(meas(f"cnmin_{r}_{c}", f"MIN v(x_dut.xc_{r}_{c}.cn) {win(W_ALL)}", "V"))
    for k, (lf, reg, role) in enumerate(roster(sl)):
        for pn, a, b in pairs(lf):
            m.append(meas(f"st{k}{pn}", f"MAX v(sp_st{k}{pn}) {win(W_ALL)}", "V"))
    return m


def probe_manifest(sl: str):
    out = {}
    for k, (lf, reg, role) in enumerate(roster(sl)):
        for pn, a, b in pairs(lf):
            out[f"st{k}{pn}"] = {"device": lf.path, "model": lf.model, "pair": pn, "a": a, "b": b,
                                 "region": reg, "role": role}
    return out


def request(sl: str, proc: str, tier: str = "A") -> dict:
    rows, cols = window(sl)
    bands = bands_in(cols)
    pts = points(sl, proc, tier)
    keys = {k: [] for k in ["vdd", "vclamp", "vpk", *[f"vddh_{b.lower()}" for b in bands], "vtvr", "vtcsl", "vtpe",
                            "vtpf", "vtren", "vtdis", "vgfil", *[f"ven_r{r}" for r in rows],
                            *[f"ven_c{c}" for c in cols], *[f"vbsel_{b.lower()}" for b in bands]]}
    for p in pts:
        sc, (sr, scol) = p["scale"], p["cell"]
        sb = G.band_of_col(scol)[0]
        sce = SCENARIOS[p["scen"]]
        keys["vdd"].append(round(VDD * sc, 6))
        keys["vclamp"].append(round(VCLAMP * sc, 6))
        keys["vpk"].append(round(V_PK * sc, 6))
        for b in bands:
            keys[f"vddh_{b.lower()}"].append(round(RAILS[b] * sc, 6))
            keys[f"vbsel_{b.lower()}"].append(1.0 if b == sb else 0.0)
        for t in ("tvr", "tcsl", "tpe", "tpf", "tren", "tdis"):
            keys[f"v{t}"].append(sce[t])
        keys["vgfil"].append(VARIANTS[p["var"]])
        for r in rows:
            keys[f"ven_r{r}"].append(1.0 if r == sr else 0.0)
        for c in cols:
            keys[f"ven_c{c}"].append(1.0 if c == scol else 0.0)
    assert len({len(v) for v in keys.values()}) == 1
    return {
        "netlist": f"tb_{sl}_{proc}.spice",
        "engine": "ngspice",
        "models": {"pdk": "gf180mcuD", "lib": "libs.tech/ngspice/sm141064.ngspice"},
        "corners": {
            "process": [{"name": proc, "sections": list(PROCESS[proc])}],
            "supply_v": keys,
            "temperature_c": list(tier_temps(proc, tier)),
        },
        "analysis": {"kind": "tran", "args": f"5n {T_END:g}u uic"},
        "measurements": measurements(sl),
        "options": {"timeout_s": 300, "keep_artifacts": False},
        # shard across fleet hosts (the whole-job ceiling is 3600 s)
        "remote": {"hosts": max(1, -(-len(pts) * len(tier_temps(proc, tier)) // UNITS_PER_HOST))},
    }


def request_name(sl, proc, tier):
    return f"{sl}_{proc}.request.json" if tier == "A" else f"{sl}_{proc}_x.request.json"


def outputs():
    out = {}
    for sl in SLICE_CELLS:
        out[TB_DIR / f"probes_{sl}.json"] = json.dumps(probe_manifest(sl), indent=1) + "\n"
        for proc in PROCESS:
            out[TB_DIR / f"tb_{sl}_{proc}.spice"] = netlist(sl, proc)
            for tier in TIER_POINTS:
                out[TB_DIR / request_name(sl, proc, tier)] = json.dumps(request(sl, proc, tier)) + "\n"
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    rc = 0
    for p, t in outputs().items():
        if a.check:
            if not p.exists() or p.read_text() != t:
                print(f"DRIFT: {p.relative_to(REPO)}", file=sys.stderr)
                rc = 1
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(t)
            print(f"wrote: {p.relative_to(REPO)}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
