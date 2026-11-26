#!/usr/bin/env python3
"""Measure signed nonlinear capacitor C at ±1 V and 10 kHz, including the swapped control."""
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

from extraction_check import check_extraction

ROOT = Path(__file__).resolve().parents[4]


def capacitor_call(path):
    for line in path.read_text().splitlines():
        words = line.split()
        if len(words) >= 4 and words[0].lower().startswith("x") and words[3].startswith("cap_"):
            return " ".join(words[3:])
    raise ValueError(f"No capacitor subcircuit in {path}")


def measure(ngspice, lib, reference, physical, bias):
    # Both source and drain diffusion are the reference terminal. In the
    # independent negative control the physical gate and diffusion are swapped.
    deck = f"""GF180 isolated signed capacitor control
.lib "{lib}" moscap_typical
Vref ref 0 DC {bias} AC 1
Vphysical physical 0 DC {bias} AC 1
Vswapped swapped 0 DC {bias} AC 1
Xreference ref 0 {reference}
Xphysical physical 0 {physical}
Xswapped 0 swapped {physical}
.control
set numdgt=12
ac lin 1 10k 10k
let c_ref = -imag(i(vref))/(2*pi*frequency)
let c_physical = -imag(i(vphysical))/(2*pi*frequency)
let c_swapped = -imag(i(vswapped))/(2*pi*frequency)
print c_ref c_physical c_swapped
quit
.endc
.end
"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "control.spice"
        path.write_text(deck)
        run = subprocess.run([ngspice, "-n", "-b", str(path)], text=True, capture_output=True, check=True)
    values = {name: float(value) * 1e15 for name, value in
              re.findall(r"^(c_\w+)\s*=\s*([\d.eE+-]+)", run.stdout, flags=re.M)}
    if len(values) != 3:
        raise ValueError(f"missing AC measurement: {run.stderr}")
    return values


def main():
    lib = Path(os.environ["PDK_ROOT"]) / "gf180mcuD/libs.tech/ngspice/sm141064.ngspice"
    ngspice = os.environ.get("KLT_NGSPICE_BINARY", "ngspice")
    print("cell,bias_V,reference_fF,physical_fF,swapped_fF")
    for n in (1, 2, 3):
        if findings := check_extraction(ROOT, n):
            raise ValueError(f"candidate {n}: {findings}")
        d = ROOT / "layout" / f"cell_candidate{n}"
        ref = capacitor_call(d / "lvs_reference.spice")
        physical = capacitor_call(d / "pex/extracted.spice")
        for bias in (1, -1):
            result = measure(ngspice, lib, ref, physical, bias)
            expected, actual, swapped = (result[name] for name in ("c_ref", "c_physical", "c_swapped"))
            if not math.isclose(expected, actual, rel_tol=1e-6) or math.isclose(expected, swapped, rel_tol=0.05):
                raise ValueError(f"unexpected signed response for C{n} at {bias:+} V: {result}")
            print(f"C{n},{bias:+},{expected:.8f},{actual:.8f},{swapped:.8f}")


if __name__ == "__main__":
    main()
