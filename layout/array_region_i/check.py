# /// script
# dependencies = ["klayout==0.30.13", "klayout-tools==0.9.2"]
# ///
"""Probe the GDS connectivity without connecting equal text labels."""
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import klayout.db as db

HERE = Path(__file__).resolve().parent
LAYOUT = HERE.parent
KLT = Path(sys.executable).with_name("klt")
TOP = "array_region_i"
GDS = HERE / (TOP + ".gds")
METALS = (34, 36, 42, 46, 81)
VIAS = (35, 38, 40, 41)


def source_cells():
    """Use the xschem top's ordered BL/WL/PL/VB arguments for each cell."""
    result = {}
    spice = (LAYOUT.parent / "design/netlists/array_32x32.spice").read_text()
    for line in spice.splitlines():
        words = line.split()
        if words[:1] and words[0].startswith("Xc_") and words[5] == "cell_candidate1":
            _, row, col = words[0].split("_")
            params = dict(field.split("=") for field in words[6:])
            cap_nm = round(float(params["wcap"]) * 1e9)
            drawn_access_nm = {"0.30u": 420, "0.6u": 840}[params["wacc"]]
            pins = dict(zip(("BL", "WL", "PL", "VB"), words[1:5]))
            result[int(row), int(col)] = (pins, (280, cap_nm, 700, drawn_access_nm))
    return result


def original_pins(layout, cell):
    source = db.Layout()
    source.read(str(LAYOUT / cell.name / (cell.name + ".gds")))
    # Compare on the finer source grid so a half-nm coordinate rounded
    # during the 1 nm output conversion cannot survive the regression.
    scale = db.ICplxTrans(layout.dbu / source.dbu, 0, False, 0, 0)
    for index in source.layer_indices():
        info = source.get_info(index)
        if info.datatype == 10:
            continue
        original = db.Region(source.top_cell().begin_shapes_rec(index))
        imported = db.Region(cell.begin_shapes_rec(layout.layer(info))).transformed(scale)
        if not (original ^ imported).is_empty():
            raise ValueError(f"Imported mask differs on {cell.name} {info}")
    pins = {}
    for shape in source.top_cell().shapes(source.layer(34, 10)).each():
        if shape.is_text():
            pins[shape.text.string] = db.DPoint(shape.text.x * source.dbu, shape.text.y * source.dbu)
    if set(pins) != {"BL", "WL", "PL", "VB"}:
        raise ValueError(f"Unexpected pin labels on {cell.name}: {pins}")
    return pins


def channel_dimensions(layout, cell):
    def layer(number, datatype=0):
        return db.Region(cell.begin_shapes_rec(layout.layer(number, datatype)))

    gates = layer(30) & layer(22)  # Poly2 crossing Comp
    cap_marker = layer(166, 5)
    sizes = []
    for channel in (gates & cap_marker, gates - cap_marker):
        if channel.count() != 1 or channel.bbox().area() != channel.area():
            raise ValueError(f"Expected one rectangular device channel in {cell.name}")
        box = channel.bbox().to_dtype(layout.dbu)
        sizes.extend((round(box.width() * 1000), round(box.height() * 1000)))
    return tuple(sizes)


def probe(gds, fault=None):
    layout = db.Layout()
    layout.read(str(gds))
    top = layout.top_cell()
    graph = db.LayoutToNetlist(TOP, layout.dbu)
    metals = {}
    for number in METALS:
        metal = db.Region(top.begin_shapes_rec(layout.layer(number, 0))).merged()
        graph.register(metal, f"metal_{number}")
        graph.connect(metal)
        metals[number] = metal
    for i, number in enumerate(VIAS):
        via = db.Region(top.begin_shapes_rec(layout.layer(number, 0))).merged()
        graph.register(via, f"via_{number}")
        graph.connect(via)
        graph.connect(metals[METALS[i]], via)
        graph.connect(via, metals[METALS[i + 1]])
    graph.extract_netlist()

    def island(number, point):
        net = graph.probe_net(metals[number], point)
        if net is None:
            raise ValueError(f"No physical conductor on {number}/0 at {point}")
        return net.cluster_id

    ports = {}
    for metal in METALS:
        for label in db.Texts(top.shapes(layout.layer(metal, 10))).each():
            if label.string in ports:
                raise ValueError(f"Duplicate top label {label.string}")
            ports[label.string] = island(metal, db.Point(label.x, label.y))
    cells = source_cells()
    all_ports = {name for pins, _ in cells.values() for name in pins.values()}
    if set(ports) != all_ports or len(ports) != 76:
        raise ValueError("Core ports differ from the source schematic")
    aliases = {frozenset(name for name in ports if ports[name] == net) for net in ports.values()}
    aliases = {group for group in aliases if len(group) > 1}
    expected_aliases = {frozenset(("BL_3", "BL_4"))} if fault == "short" else set()
    if aliases != expected_aliases:
        raise ValueError(f"Unexpected physical aliases: {aliases}")
    placements = {}
    for inst in top.each_inst():
        point = inst.trans.disp
        if (point.x, point.y) in placements or inst.is_regular_array():
            raise ValueError("Duplicate or arrayed placement")
        placements[point.x, point.y] = inst
    xs = sorted({x for x, _ in placements})
    ys = sorted({y for _, y in placements})
    if (len(xs), len(ys), len(placements)) != (11, 32, 352):
        raise ValueError("Incomplete Region I placement")
    masters = {inst.cell.name: inst.cell for inst in placements.values()}
    locations = {name: original_pins(layout, leaf) for name, leaf in masters.items()}
    dimensions = {name: channel_dimensions(layout, leaf) for name, leaf in masters.items()}
    disconnected = {}
    for (row, col), (expected, split) in cells.items():
        inst = placements[xs[col], ys[row]]
        if dimensions[inst.cell.name] != split:
            raise ValueError(f"Wrong drawn device geometry at ({row}, {col})")
        for pin, name in expected.items():
            local = locations[inst.cell.name][pin]
            point = inst.trans * local.to_itype(layout.dbu)
            actual = island(34, point)
            if actual != ports[name]:
                disconnected[row, col, pin] = actual
    expected_opens = {(r, 3, "BL") for r in range(16, 32)} if fault == "open" else set()
    if set(disconnected) != expected_opens or len(set(disconnected.values())) != (1 if expected_opens else 0):
        raise ValueError(f"Unexpected disconnected cell terminals: {disconnected}")
    return Counter(i.cell.name for i in placements.values())


def fault_layout(kind, dest):
    layout = db.Layout()
    layout.read(str(GDS))
    top = layout.top_cell()
    metal4 = top.shapes(layout.layer(46, 0))
    # Between rows 15 and 16, clear of all bitcell geometry and via ladders.
    x = 3 * 12 + 5.69
    y = 15 * 9 + 7
    if kind == "short":
        metal4.insert(db.DBox(x, y - 0.25, x + 12, y + 0.25))
    else:
        route = db.Region(metal4)
        cut = db.DBox(x - 0.5, y - 0.5, x + 0.5, y + 0.5).to_itype(layout.dbu)
        metal4.clear()
        metal4.insert(route - db.Region(cut))
    layout.write(str(dest))


def lvs(gds, work, intact):
    request = json.loads((HERE / "lvs_request.json").read_text())
    request["layout"]["file"] = str(gds)
    request["reference"]["netlist"] = str(HERE / "reference.spice")
    path = work / "check.json"
    path.write_text(json.dumps(request))
    run = subprocess.run([KLT, "lvs", path, "--format", "json"], capture_output=True, text=True)
    if run.returncode != (0 if intact else 3):
        raise ValueError(f"LVS exit {run.returncode}: {run.stdout[:380]} {run.stderr}")
    report = json.loads(run.stdout)
    counts = report["counts"]
    if intact:
        if report["status"] != "match" or report["error_count"] or any(
            set(counts[k].values()) != {n} for k, n in (("nets", 428), ("devices", 704), ("pins", 76))
        ):
            raise ValueError(f"Incomplete comparison: {counts}")
        public = {(p["layout"], p["reference"]) for p in report["net_correspondence"] if p["pin"]}
        if public != {(n, n) for pins, _ in source_cells().values() for n in pins.values()}:
            raise ValueError("Public port name correspondence differs from the schematic")
    else:
        expected_nets = 429 if gds.stem == "open" else 427
        if (report["status"] != "mismatch" or not report["error_count"]
                or counts["nets"]["layout"] != expected_nets or counts["nets"]["reference"] != 428):
            raise ValueError(f"LVS failed to identify the physical fault: {counts}")
    return counts


def main():
    digest = "sha256:" + hashlib.sha256(GDS.read_bytes()).hexdigest()
    for name in ("lvs_report.json", "drc_report.json", "drc_native_report.json"):
        report = json.loads((HERE / name).read_text())
        if report["provenance"]["input"]["content_hash"] != digest:
            raise ValueError(f"{name} was produced from a different GDS")
    committed = json.loads((HERE / "lvs_report.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        print("Intact Region I split populations:", dict(probe(GDS)))
        counts = lvs(GDS, work, True)
        if committed["status"] != "match" or committed["error_count"] or counts != committed["counts"]:
            raise ValueError("Committed LVS differs from the fresh comparison")
        print("Intact LVS:", counts)
        for kind in ("open", "short"):
            gds = work / f"{kind}.gds"
            fault_layout(kind, gds)
            probe(gds, kind)
            print(f"BL_3 {kind} terminals verified. LVS:", lvs(gds, work, False))


if __name__ == "__main__":
    main()
