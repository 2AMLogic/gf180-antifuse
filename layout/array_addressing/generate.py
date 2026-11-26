# /// script
# dependencies = ["klayout==0.30.13", "klayout-tools==0.9.2"]
# ///
"""Generate the GF180 array's pass gates and level shifters from real PDK devices."""
import argparse
import getpass
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import klayout.db as db

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KLT = Path(sys.executable).with_name("klt")

# Leaf name, target model, drawn gate length and total physical width in µm.
# LDPMOS has two 4 µm fingers at minimum, versus 5 µm total in ls_hv10.spice.
DEVICES = {
    "n33": ("nfet_03v3", 0.28, 2.0),
    "p33": ("pfet_03v3", 0.28, 4.0),
    "n60": ("nfet_06v0", 0.70, 10.0),
    "p60": ("pfet_06v0", 0.55, 1.0),
    "pg60": ("nfet_06v0", 0.70, 20.0),
    "ldn20": ("nfet_10v0_asym", 0.60, 20.0),
    "ldp8": ("pfet_10v0_asym", 0.60, 8.0),
    "ldn25": ("nfet_10v0_asym", 0.60, 25.0),
}
CELLS = {
    "ls_hv06": ("n33", "p33", "n60", "n60", "p60", "p60"),
    "ls_hv10": ("n33", "p33", "ldn20", "ldn20", "ldp8", "ldp8"),
    "pg_n06": ("pg60",),
    "pg_n10": ("ldn25",),
}


def generate_devices(work):
    # The PDK reads USER while registering its external KLayout PCell library.
    env = dict(os.environ)
    env.setdefault("USER", getpass.getuser())
    for name, (model, length, width) in DEVICES.items():
        flavor = model.split("_")[0]
        if model.endswith("_asym"):
            # Request the original per-finger pull-up width. The measured PDK
            # clamp to 4 µm is recorded in the as-drawn reference.
            params = {"w": 2.5 if name == "ldp8" else width / 2, "l": length}
            args = ["gen", "--pdk", "gf180mcuA", "--pdk-pcell",
                    "gf180mcu_klayoutapi/" + model]
        else:
            params = dict(w_um=width, l_um=length, rows=1, cols=1, dummy=0,
                          flavor=flavor, gate_contact=True, add_guard_ring=True,
                          ring_gap_side="E", ring_gap_um=1.0, ring_gap_offset_um=-0.7)
            if model.endswith("_06v0"):
                params["voltage_flavor"] = "medium_voltage"
                if flavor == "pfet":
                    params["ring_padding_um"] = 1.29
            args = ["gen", "mos_array", "--pdk", "gf180mcuA"]
        args += ["--params", json.dumps(params), "--cell-name", name, "-o",
                 str(work / (name + ".gds")), "--format", "json"]
        result = subprocess.run([KLT, *args], capture_output=True, text=True, env=env)
        if result.returncode:
            raise RuntimeError(f"Could not generate {model}: {result.stderr}")
        (work / (name + ".json")).write_text(result.stdout)


def add_leaf(layout, path):
    """Copy masks without the seed's internal pin texts."""
    source = db.Layout()
    source.read(str(path))
    source.top_cell().flatten(-1, True)
    for index in source.layer_indices():
        if source.get_info(index).datatype == 10:
            source.top_cell().shapes(index).clear()
    leaf = layout.create_cell(path.stem)
    # The primitive-only PDK can emit 1 nm units while an installation with
    # technology LEF emits 0.5 nm. Copy the physical tree across these grids.
    leaf.copy_tree(source.top_cell())
    return leaf


def wire(layout, cell, metal, x, y, end_x, end_y, width=0.42):
    if x != end_x and y != end_y:
        raise ValueError("Routes must be orthogonal")
    half = width / 2
    bounds = db.DBox(min(x, end_x) - half, min(y, end_y) - half,
                     max(x, end_x) + half, max(y, end_y) + half)
    cell.shapes(layout.layer(metal, 0)).insert(bounds)


def device_terminals(kind, work, pins):
    """Metal1 contacts and the Metal2 escape x for each real terminal."""
    drain, gate, source, body = pins
    model, _, width = DEVICES[kind]
    if model.endswith("_asym"):
        gate_y = width / 4 + (1.21 if kind == "ldp8" else 0.91)
        contacts = [(source, -1.72, 0), (source, 1.72, 0), (drain, 0, 0),
                    (gate, -0.87, gate_y), (gate, 0.87, gate_y), (body, 2.48, 0)]
        if kind == "ldp8":
            # The inner N+ ring contacts DNWELL. The outer P+ guard is substrate.
            contacts.append(("VSS", 6., 0))
        return [(net, x, y, x) for net, x, y in contacts]
    ports = {p["name"]: p for p in json.loads((work / (kind + ".json")).read_text())["ports"]}
    terminals = []
    for pin, net, dx in (("U0_S", source, -0.30), ("U0_D", drain, 0.32),
                         ("U0_G", gate, 0), ("TAP_W", body, -0.55)):
        x, y = ports[pin]["x_um"], ports[pin]["y_um"]
        terminals.append((net, x, y, x + dx))
    return terminals


def draw(name, work, destination):
    lines = (ROOT / "design/netlists" / (name + ".spice")).read_text().splitlines()
    interface = next(line for line in lines if line.startswith(".subckt")).split()[2:]
    ports = [token for token in interface if "=" not in token]
    calls = [line.split() for line in lines if line.startswith("XM")]
    nets = ports + (["INB"] if name.startswith("ls_") else [])
    layout = db.Layout()
    layout.dbu = 0.0005
    top = layout.create_cell(name)
    reference = [".subckt " + name + " " + " ".join(ports)]
    right = 0.
    endpoints = []

    def via(upper, cut, x, y):
        wire(layout, top, cut, x, y, x, y, 0.26)
        wire(layout, top, upper, x, y, x, y)

    for call, kind in zip(calls, CELLS[name], strict=True):
        model, length, width = DEVICES[kind]
        if model != call[5]:
            raise ValueError(f"Unexpected schematic model for {name}: {call}")
        cell = layout.cell(kind) or add_leaf(layout, work / (kind + ".gds"))
        bounds = cell.dbbox()
        x, y = right - bounds.left + 1.2, 1.0 - bounds.bottom
        right = x + bounds.right + 1.2
        top.insert(db.DCellInstArray(cell.cell_index(), db.DTrans(db.DVector(x, y))))
        for net, px, py, lane in device_terminals(kind, work, call[1:5]):
            via(36, 35, px + x, py + y)
            wire(layout, top, 36, px + x, py + y, lane + x, py + y)
            endpoints.append((net, lane + x, py + y))
        fingers = 2 if model.endswith("_asym") else 1
        reference.append(f"{' '.join(call[:6])} L={length:g}u W={width:g}u nf={fingers} m=1")
    buses = {net: round(top.dbbox().top + 2 + 1.25 * i, 3) for i, net in enumerate(nets)}
    for net, x, y in endpoints:
        wire(layout, top, 36, x, y, x, buses[net])
        via(42, 38, x, buses[net])
    for net, y in buses.items():
        left = min(x for n, x, _ in endpoints if n == net)
        wire(layout, top, 42, left, y, right + 1, y)
        if net in ports:
            top.shapes(layout.layer(42, 10)).insert(db.DText(net, right + 1, y))
    dest = destination / name
    dest.mkdir(exist_ok=True)
    (dest / "reference.spice").write_text("\n".join(reference + [".ends"]) + "\n")
    options = db.SaveLayoutOptions()
    options.dbu = 0.001
    options.gds2_write_timestamps = False
    layout.write(str(dest / (name + ".gds")), options)


def check_stream(expected, generated):
    if expected.read_bytes() == generated.read_bytes():
        return
    # External PCell backends may emit identical shapes in a different GDS
    # record order. Compare the full hierarchy including properties and pin
    # texts with zero coordinate tolerance before accepting a reordered stream.
    first, second = db.Layout(), db.Layout()
    first.read(str(expected))
    second.read(str(generated))
    differ = db.LayoutDiff()
    if first.dbu == second.dbu and differ.compare(
            first, second, db.LayoutDiff.WithMetaInfo, 0):
        print(f"{expected.name}: identical hierarchy, masks and pin text in different record order")
        return
    for leaf in first.each_cell():
        other = second.cell(leaf.name)
        if other is None:
            raise ValueError(f"{expected.name}: missing physical master {leaf.name}")
        for index in first.layer_indices():
            mask = first.get_info(index)
            left = db.Region(leaf.begin_shapes_rec(index))
            right = db.Region(other.begin_shapes_rec(second.layer(mask)))
            delta = left ^ right
            if not delta.is_empty():
                raise ValueError(f"{expected.name}: {leaf.name} mask {mask} differs at {delta.bbox()} "
                                 f"with XOR area {delta.area()} square database units")
    raise ValueError(f"{expected.name}: hierarchy, shape properties or text differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        generate_devices(work)
        destination = work if args.check else HERE
        for name in CELLS:
            draw(name, work, destination)
            if args.check:
                check_stream(HERE / name / (name + ".gds"), destination / name / (name + ".gds"))
                if (destination / name / "reference.spice").read_bytes() != (HERE / name / "reference.spice").read_bytes():
                    raise SystemExit(f"Regeneration differs for {name}/reference.spice")


if __name__ == "__main__":
    main()
