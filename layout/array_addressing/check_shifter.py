"""Compare the 5/8 µm schematic pull-ups with the native extracted 10 V shifter."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import itertools
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / "design/netlists/ls_hv10.spice"
VARIANTS = ("schematic5", "schematic8", "extracted8")
MEAS = ("rise_ns", "fall_ns", "out_on", "outb_on", "out_off", "outb_off")


def extracted_subckt(path):
    """Wrap native D/G/S/B, W/L, diffusion areas/perimeters in PDK subcircuits."""
    lines = []
    for line in path.read_text().splitlines():
        if line.startswith("+"):
            lines[-1] += " " + line[1:].strip()
        elif line and not line.startswith("*"):
            lines.append(line)
    converted = []
    for line in lines:
        if line.startswith("M$"):
            words = line.split()
            name = "X" + words[0][2:]
            # Native combine has summed the two physical asymmetric fingers.
            fingers = 2 if words[5].endswith("_asym") else 1
            fields = [name, *(word.replace(r"\$", "nprivate") for word in words[1:])]
            converted.append(" ".join(fields) + f" nf={fingers}")
        else:
            converted.append(line.replace("ls_hv10", "extracted8"))
    interface = converted[0].upper().split()
    if interface != [".SUBCKT", "EXTRACTED8", "IN", "OUT", "OUTB", "VDDH", "VDDL", "VSS"]:
        raise ValueError(f"Unexpected native interface or terminal order: {interface}")
    if sum(line.startswith("X") for line in converted) != 6:
        raise ValueError("Expected six native combined MOS devices")
    return "\n".join(converted)


def simulate(point, model, extracted, engine, work):
    corner, scale, temp, load = point
    vddl, vddh = 3.3 * scale, 5.5 * scale
    bench = [f"10 V level shifter at {point}",
             f'.include "{model}/design.ngspice"',
             f'.lib "{model}/sm141064.ngspice" {corner}',
             f'.lib "{model}/smbb000149.ngspice" {corner}',
             f'.include "{SOURCE}"', extracted,
             f".temp {temp}", f"VDD_L vddl 0 {vddl}", f"VDD_H vddh 0 {vddh}",
             f"VIN in 0 PULSE(0 {vddl} 100n 4n 4n 150n 600n)"]
    for name in VARIANTS:
        out, inv = "o_" + name, "ob_" + name
        if name == "extracted8":
            bench.append(f"X_{name} in {out} {inv} vddh vddl 0 extracted8")
        else:
            width = 5 if name == "schematic5" else 8
            bench.append(f"X_{name} in vddl 0 {out} {inv} vddh ls_hv10 wpup={width}u")
        bench += [f"C_a_{name} {out} 0 {load}f", f"C_b_{name} {inv} 0 {load}f"]
        for slope, key in (("RISE", "rise_ns"), ("FALL", "fall_ns")):
            bench.append(f".meas tran {name}_{key} TRIG v(in) VAL={vddl/2} {slope}=1 "
                         f"TARG v({out}) VAL={vddh/2} {slope}=1")
        for key, node, when in (("out_on", out, 220), ("outb_on", inv, 220),
                                ("out_off", out, 420), ("outb_off", inv, 420)):
            bench.append(f".meas tran {name}_{key} FIND v({node}) AT={when}n")
    bench += [".tran 0.5n 450n", ".end"]
    path = work / ("_".join(map(str, point)) + ".spice")
    path.write_text("\n".join(bench) + "\n")
    log = subprocess.run([engine, "-b", str(path)], capture_output=True, text=True)
    path.with_suffix(".log").write_text(log.stdout + log.stderr)
    values = dict(re.findall(r"(?m)^(\w+)\s*=\s*([+\-0-9.eE]+)", log.stdout))
    rows = []
    for name in VARIANTS:
        row = dict(process=corner, supply_scale=scale, temperature_C=temp,
                   output_load_fF=load, variant=name)
        for key in MEAS:
            value = float(values[name + "_" + key])
            if key.endswith("_ns"):
                value *= 1e9
            row[key] = round(value, 8)
        row["switched"] = (min(row["out_on"], row["outb_off"]) >= 0.9 * vddh and
                           max(row["out_off"], row["outb_on"]) <= 0.1 * vddh and
                           min(row["rise_ns"], row["fall_ns"]) > 0)
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-cir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ngspice", default="ngspice")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    model = Path(os.environ["PDK_ROOT"]).resolve() / "gf180mcuD/libs.tech/ngspice"
    netlist = extracted_subckt(args.native_cir)
    points = (("typical", 1., 27, 100),) if args.smoke else itertools.product(
        ("typical", "ff", "ss", "fs", "sf"), (0.9, 1.0, 1.1), (-40, 27, 125), (100, 500))
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=4) as pool:
        work = Path(tmp)
        groups = pool.map(lambda point: simulate(point, model, netlist, args.ngspice, work), points)
        rows = [r for group in groups for r in group]
    with args.output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    success = sum(r["switched"] for r in rows)
    print(f"{success}/{len(rows)} cases switched both ways")
    if success != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
