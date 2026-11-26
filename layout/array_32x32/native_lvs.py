# /// script
# dependencies = ["klayout==0.30.13", "docopt==0.6.2"]
# ///
"""Run the installed GF180D native deck and read the actual cross-reference database."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import klayout.db as db

from check import fault_copy, probe

HERE = Path(__file__).resolve().parent
SHIFT = HERE.parent / "array_addressing" / "ls_hv10"
CASES = ("array", "select_open", "row_short", "missing_pwell",
         "shifter", "body_open", "schematic_pullup")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_reference(source, original_pullup=False):
    """Translate the repository's GF180 subcircuit primitives to native CDL."""
    lines = []
    for line in source.read_text().splitlines():
        fields = line.split()
        if fields and fields[0].startswith("XM"):
            # The native deck combines physical fingers. W is the total drawn width.
            if fields[-1] != "m=1" or fields[-2] not in {"nf=1", "nf=2"}:
                raise ValueError(f"Unrecognized transistor multiplicity: {line}")
            fields = [fields[0][1:], *fields[1:-2]]
            if original_pullup and fields[5] == "pfet_10v0_asym":
                if fields[-1] != "W=8u":
                    raise ValueError("Unexpected drawn 10 V pull-up size")
                fields[-1] = "W=5u"
            line = " ".join(fields)
        elif fields and fields[0].startswith("XC1") and fields[3].startswith("cap_"):
            line = line[1:].replace("c_width=", "w=").replace("c_length=", "l=")
        lines.append(line)
    return "\n".join(lines) + "\n"


def physical_fault(source, kind, dest):
    if kind in ("select_open", "row_short"):
        sites, _ = probe(source)
        fault_copy(source, "open" if kind == "select_open" else "short", sites, dest)
        return
    layout = db.Layout()
    layout.read(str(source))
    top = layout.top_cell()
    if kind == "missing_pwell":
        shapes = top.shapes(layout.layer(204, 0))
        first = min(shapes.each(), key=lambda s: (s.bbox().left, s.bbox().bottom))
        first.delete()
        if shapes.size() != 703:
            raise ValueError("Expected exactly one open NMOS capacitor recognition well")
    elif kind == "body_open":
        # Physically open every contact on ONE inner N+ ring in DNWELL.
        device = min((i for i in top.each_inst() if i.cell.name == "ldp8"),
                     key=lambda i: i.trans.disp.x)
        def shapes(number):
            return db.Region(device.cell.begin_shapes_rec(layout.layer(number, 0)))
        ring = (shapes(22) & shapes(32) & shapes(12)).transformed(device.trans)
        top.flatten(-1, True)
        contacts = top.shapes(layout.layer(33, 0))
        all_cuts = db.Region(contacts)
        broken = all_cuts.inside(ring)
        if broken.count() != 52:
            raise ValueError(f"Unexpected inner-ring contact count: {broken.count()}")
        contacts.clear()
        contacts.insert(all_cuts - broken)
    else:
        raise ValueError(f"Unrecognized physical control {kind}")
    options = db.SaveLayoutOptions()
    options.gds2_write_timestamps = False
    layout.write(str(dest), options)


def read_xref(path):
    database = db.LayoutVsSchematic()
    database.read(str(path))
    xref = database.xref()
    pairs = list(xref.each_circuit_pair())
    if len(pairs) != 1:
        raise ValueError("Expected exactly one flattened circuit pair")
    circuit = pairs[0]
    counts = {}
    devices = Counter()
    for category in ("device", "net", "pin"):
        statuses = Counter()
        for pair in getattr(xref, "each_" + category + "_pair")(circuit):
            status = str(pair.status())
            statuses[status] += 1
            if category == "device" and pair.first():
                devices[pair.first().device_class().name] += 1
        counts[category] = dict(sorted(statuses.items()))
    missing = []
    for pair in xref.each_pin_pair(circuit):
        left = pair.first().name() if pair.first() else None
        right = pair.second().name() if pair.second() else None
        if left != right:
            missing.append([left, right])
    return {"circuit": str(circuit.status()), "pin_name_differences": missing,
            "strict_match": str(circuit.status()) == "Match" and not missing, "pairs": counts,
            "layout_devices": dict(sorted(devices.items()))}


def run(case, out, native, array_layout):
    folder = HERE if case in CASES[:4] else SHIFT
    source = array_layout if folder == HERE else folder / (folder.name + ".gds")
    ref = folder / "reference.spice"
    work = out / case
    work.mkdir(exist_ok=True, parents=True)
    layout = source
    if case in ("select_open", "row_short", "missing_pwell", "body_open"):
        layout = work / "fault.gds"
        physical_fault(source, case, layout)
    cdl = work / "reference.cdl"
    cdl.write_text(native_reference(ref, original_pullup=case == "schematic_pullup"))
    argv = [sys.executable, str(native / "run_lvs.py"), "--layout=" + str(layout),
            "--netlist=" + str(cdl), "--variant=D", "--topcell=" + folder.name,
            "--run_dir=" + str(work), "--run_mode=flat", "--top_lvl_pins",
            "--combine", "--purge", "--purge_nets"]
    with (work / "run.log").open("w") as log:
        subprocess.run(argv, cwd=work, stdout=log, stderr=subprocess.STDOUT, check=True)
    result = read_xref(work / (layout.stem + ".lvsdb"))
    expected = case in ("array", "shifter")
    if result["strict_match"] != expected:
        raise ValueError(f"{case} expected {expected}, found {result}")
    result.update(source_gds_sha256=digest(source), tested_gds_sha256=digest(layout),
                  source_reference_sha256=digest(ref), tested_cdl_sha256=digest(cdl),
                  deck_sha256=digest(native / "gf180mcu.lvs"))
    (work / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(case, json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=CASES, action="append")
    parser.add_argument("--array-layout", type=Path, default=HERE / "array_32x32.gds")
    args = parser.parse_args()
    native = Path(os.environ["PDK_ROOT"]).resolve() / "gf180mcuD/libs.tech/klayout/tech/lvs"
    for case in args.case or CASES:
        run(case, args.output.resolve(), native, args.array_layout.resolve())


if __name__ == "__main__":
    main()
