"""Probe the GDS connectivity without connecting equal text labels."""
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import klayout.db as db

from regions import I, III, LAYOUT
KLT = Path(sys.executable).with_name("klt")
METALS = (34, 36, 42, 46, 81)
VIAS = (35, 38, 40, 41)


def source_cells(region):
    """Use the xschem top's ordered BL/WL/PL/VB arguments for each cell."""
    result = {}
    spice = (LAYOUT.parent / "design/netlists/array_32x32.spice").read_text()
    for line in spice.splitlines():
        words = line.split()
        if words[:1] and words[0].startswith("Xc_") and words[5] == region.candidate:
            _, row, col = words[0].split("_")
            params = dict(field.split("=") for field in words[6:])
            cap_nm = round(float(params["wcap"]) * 1e9)
            drawn_access_nm = {"0.30u": 420, "0.6u": 840}[params["wacc"]]
            access_length_nm = round(float(params["lacc"].removesuffix("u")) * 1000)
            pins = dict(zip(("BL", "WL", "PL", "VB"), words[1:5]))
            result[int(row), int(col)] = (pins, (280, cap_nm, access_length_nm, drawn_access_nm))
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


def device_channels(layout, cell):
    def layer(number, datatype=0):
        return db.Region(cell.begin_shapes_rec(layout.layer(number, datatype)))

    gates = layer(30) & layer(22)  # Poly2 crossing Comp
    cap_marker = layer(166, 5)
    boxes = []
    for channel in (gates & cap_marker, gates - cap_marker):
        if channel.count() != 1 or channel.bbox().area() != channel.area():
            raise ValueError(f"Expected one rectangular device channel in {cell.name}")
        boxes.append(channel.bbox())
    return boxes


def probe(region, gds, fault=None):
    layout = db.Layout()
    layout.read(str(gds))
    top = layout.top_cell()
    graph = db.LayoutToNetlist(region.top, layout.dbu)
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
    def polygons(number):
        return db.Region(top.begin_shapes_rec(layout.layer(number, 0))).merged()

    # Active islands stop at the MOS channels. Each diffusion terminal and
    # poly gate connects to M1 only through an actual CONTACT cut.
    poly = polygons(30)
    diffusion = polygons(22) - poly
    contacts = polygons(33)
    graph.register(contacts, "contact")
    graph.connect(contacts)
    graph.connect(contacts, metals[34])
    for number, material in ((22, diffusion), (30, poly)):
        graph.register(material, f"device_{number}")
        graph.connect(material)
        graph.connect(material, contacts)
        metals[number] = material
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
    cells = source_cells(region)
    all_ports = {name for pins, _ in cells.values() for name in pins.values()}
    if set(ports) != all_ports or len(ports) != len(region.columns) + 65:
        raise ValueError("Core ports differ from the source schematic")
    aliases = {frozenset(name for name in ports if ports[name] == net) for net in ports.values()}
    aliases = {group for group in aliases if len(group) > 1}
    shorted = ("BL_3", "BL_4") if region == I else ("WL_7_III", "WL_8_III")
    expected_aliases = {frozenset(shorted)} if fault == "short" else set()
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
    if (len(xs), len(ys), len(placements)) != (len(region.columns), 32, 32 * len(region.columns)):
        raise ValueError(f"Incomplete Region {region.name} placement")
    masters = {inst.cell.name: inst.cell for inst in placements.values()}
    locations = {name: original_pins(layout, leaf) for name, leaf in masters.items()}
    channels = {name: device_channels(layout, leaf) for name, leaf in masters.items()}
    storage_nodes = set()
    disconnected = {}
    for (row, col), (expected, split) in cells.items():
        inst = placements[xs[col - region.columns.start], ys[row]]
        capacitor, access = channels[inst.cell.name]
        drawn = [round(length * layout.dbu * 1000)
                 for box in (capacitor, access) for length in (box.width(), box.height())]
        if tuple(drawn) != split:
            raise ValueError(f"Wrong drawn device geometry at ({row}, {col})")
        terminals = {}
        for pin, name in expected.items():
            local = locations[inst.cell.name][pin]
            point = inst.trans * local.to_itype(layout.dbu)
            actual = island(34, point)
            terminals[pin] = actual
            if actual != ports[name]:
                disconnected[row, col, pin] = actual
        # The PDK MOSCAP has one gate and two shorted diffusions. A symmetric
        # two-terminal reference alone cannot distinguish which plate stores
        # charge. Probe both diffusions and the gate from the drawn masks.
        def electrodes(box):
            left = db.Point(box.left - 1, box.center().y)
            right = db.Point(box.right + 1, box.center().y)
            return (island(22, inst.trans * left), island(30, inst.trans * box.center()),
                    island(22, inst.trans * right))

        plate_l, storage, plate_r = electrodes(capacitor)
        left, word, right = electrodes(access)
        bitline, internal = (right, left) if region == I else (left, right)
        if ((plate_l, plate_r, word, bitline, internal) !=
                (terminals["PL"], terminals["PL"], terminals["WL"], terminals["BL"], storage)
                or storage in storage_nodes or storage in ports.values() or storage in terminals.values()):
            raise ValueError(f"Wrong device electrodes or shared storage node at ({row}, {col})")
        storage_nodes.add(storage)
    expected_opens = set()
    if fault == "open":
        if region == I:
            expected_opens = {(r, 3, "BL") for r in range(16, 32)}
        else:
            expected_opens = {(7, col, "PL") for col in range(27, 32)}
    if set(disconnected) != expected_opens or len(set(disconnected.values())) != (1 if expected_opens else 0):
        raise ValueError(f"Unexpected disconnected cell terminals: {disconnected}")
    return Counter(i.cell.name for i in placements.values())


def fault_layout(region, source, kind, dest):
    layout = db.Layout()
    layout.read(str(source))
    top = layout.top_cell()
    if region == I:
        # Metal4 bitline between rows 15 and 16.
        layer, x, y = 46, 3 * 12 + 5.69, 15 * 9 + 7
        bridge = db.DBox(x, y - 0.25, x + 12, y + 0.25)
    elif kind == "open":
        # Row 7's Metal5 plate between columns 26 and 27.
        layer, x, y = 81, 4 * 12 + 5.8 + 6, 7 * 9 + 0.36
    else:
        # Join the Metal3 word lines of rows 7 and 8 between two cells.
        layer, x, y = 42, 4 * 12 + 9, 7 * 9 + 1.8
        bridge = db.DBox(x - 0.25, y, x + 0.25, y + 9)
    shapes = top.shapes(layout.layer(layer, 0))
    if kind == "short":
        shapes.insert(bridge)
    else:
        route = db.Region(shapes)
        cut = db.DBox(x - 0.5, y - 0.5, x + 0.5, y + 0.5).to_itype(layout.dbu)
        shapes.clear()
        shapes.insert(route - db.Region(cut))
    layout.write(str(dest))


def lvs(region, gds, work, intact):
    request = json.loads((region.directory / "lvs_request.json").read_text())
    request["layout"]["file"] = str(gds)
    request["reference"]["netlist"] = str(region.directory / "reference.spice")
    path = work / "check.json"
    path.write_text(json.dumps(request))
    run = subprocess.run([KLT, "lvs", path, "--format", "json"], capture_output=True, text=True)
    if run.returncode != (0 if intact else 3):
        raise ValueError(f"LVS exit {run.returncode}: {run.stdout[:380]} {run.stderr}")
    report = json.loads(run.stdout)
    counts = report["counts"]
    placements = 32 * len(region.columns)
    ports = len(region.columns) + 65
    nets = placements + ports
    if intact:
        if report["status"] != "match" or report["error_count"] or any(
            set(counts[k].values()) != {n} for k, n in (("nets", nets), ("devices", 2 * placements), ("pins", ports))
        ):
            raise ValueError(f"Incomplete comparison: {counts}")
        public = {(p["layout"], p["reference"]) for p in report["net_correspondence"] if p["pin"]}
        if public != {(n, n) for pins, _ in source_cells(region).values() for n in pins.values()}:
            raise ValueError("Public port name correspondence differs from the schematic")
    else:
        expected_nets = nets + 1 if gds.stem == "open" else nets - 1
        if (report["status"] != "mismatch" or not report["error_count"]
                or counts["nets"]["layout"] != expected_nets or counts["nets"]["reference"] != nets):
            raise ValueError(f"LVS failed to identify the physical fault: {counts}")
    return counts


def main(region):
    gds = region.directory / (region.top + ".gds")
    digest = "sha256:" + hashlib.sha256(gds.read_bytes()).hexdigest()
    reports = ["lvs_report.json", "drc_report.json", "drc_native_report.json"]
    if region == III:
        reports.append("erc_report.json")
    for name in reports:
        report = json.loads((region.directory / name).read_text())
        if report["provenance"]["input"]["content_hash"] != digest:
            raise ValueError(f"{name} was produced from a different GDS")
    committed = json.loads((region.directory / "lvs_report.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        print(f"Intact Region {region.name} split populations:", dict(probe(region, gds)))
        counts = lvs(region, gds, work, True)
        if committed["status"] != "match" or committed["error_count"] or counts != committed["counts"]:
            raise ValueError("Committed LVS differs from the fresh comparison")
        print("Intact LVS:", counts)
        for kind in ("open", "short"):
            fault = work / f"{kind}.gds"
            fault_layout(region, gds, kind, fault)
            probe(region, fault, kind)
            print(f"Physical {kind} terminals verified. LVS:", lvs(region, fault, work, False))
