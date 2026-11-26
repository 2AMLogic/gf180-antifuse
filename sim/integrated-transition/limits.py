"""Supported stress limits with provenance, for sim/integrated-transition.

Only limits that a committed record or the installed PDK states are listed. A
(device, terminal pair) with no entry here is UNCHECKED: its measured peak is
reported, never compared, and no pass/fail is derived.

What the sources do and do not say (do not extend this table without a source):

* ``spec/cell-candidates.md`` ("Verified access/isolation (series-device)
  candidates" table, and the capacitor table above it) gives one *rating* per
  device family: 3.3 V for ``nfet_03v3``/``pfet_03v3`` and the thin capacitors,
  6.0 V for ``nfet_06v0``/``pfet_06v0`` and the thick capacitor, 10 V for
  ``nfet_10v0_asym``/``pfet_10v0_asym``. It does not name a terminal pair. Its
  wording ties the rating to the *gate* ("rated to gate that voltage safely as
  a series access element"; "gate oxide ... operating well below its own stress
  point"). This table therefore applies the rating to the gate-referenced pairs
  (gate-source, gate-drain) only. Drain-source, bulk and junction limits are not
  stated anywhere in the repo or in the installed PDK model files, so they stay
  unchecked.
* ``spec/leg-design-record.md`` section 3: the voltage rating of
  ``ppolyf_u_2k_6p0`` is OPEN ("the rating question stays OPEN"). Unchecked.
* A capacitor's rating is a rating *as a capacitor within its rated voltage*
  (``spec/cell-candidates.md``: the model "valid for the device operated as a
  capacitor within its rated voltage"). It is compared only for UNSELECTED
  cells; the selected cell is meant to exceed it, and no breakdown model is
  used here, so nothing about the selected cell's oxide is concluded.
"""

from __future__ import annotations

SRC_DEVICES = "spec/cell-candidates.md (access/isolation device table; 'rated to gate that voltage safely')"
SRC_CAPS = "spec/cell-candidates.md (capacitor table; 'valid ... within its rated voltage')"
SRC_PPOLY = "spec/leg-design-record.md section 3 (rating OPEN)"

# model -> (limit in V, pairs it applies to, source)
_RATED = {
    "nfet_03v3": (3.3, ("gs", "gd")), "pfet_03v3": (3.3, ("gs", "gd")),
    "nfet_06v0": (6.0, ("gs", "gd")), "pfet_06v0": (6.0, ("gs", "gd")),
    "nfet_10v0_asym": (10.0, ("gs", "gd")), "pfet_10v0_asym": (10.0, ("gs", "gd")),
}
_CAPS = {"cap_nmos_03v3": 3.3, "cap_pmos_03v3": 3.3, "cap_nmos_06v0": 6.0, "cap_pmos_06v0": 6.0}


def limit_for(model: str, pair: str, role: str, selected: bool):
    """(limit_V, source) if a supported limit applies, else (None, reason it is unchecked)."""
    if model in _RATED:
        lim, prs = _RATED[model]
        if pair in prs:
            return lim, SRC_DEVICES
        return None, f"no supported {pair} limit stated for {model} (rating names no terminal pair; applied to gs/gd only)"
    if model in _CAPS:
        if role == "cell" and selected:
            return None, "selected cell's capacitor is meant to exceed its rating; no breakdown model, nothing concluded"
        return _CAPS[model], SRC_CAPS
    if model.startswith("ppolyf_"):
        return None, SRC_PPOLY
    return None, f"no limit source for {model}"
