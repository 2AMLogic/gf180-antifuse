# /// script
# dependencies = ["klayout==0.30.13"]
# ///
"""Probe the addressed array using only physical metal, vias and original pin sites."""
from collections import defaultdict
from pathlib import Path
import tempfile

import klayout.db as db

HERE = Path(__file__).resolve().parent
LAYOUT = HERE.parent
SOURCE = LAYOUT.parent / "design/netlists/array_32x32.spice"
METAL = (34, 36, 42, 46, 81)
VIA = (35, 38, 40, 41)


def source_wiring():
    calls = {}
    for line in SOURCE.read_text().splitlines():
        words = line.split()
        if words[:2] == [".subckt", "array_32x32"]:
            public = set(words[2:])
        if words and words[0].startswith(("XLC_", "XPC_", "XLR_", "XPR_")):
            fields = [v for v in words if "=" not in v]
            calls[fields[0]] = (fields[-1], fields[1:-1])
    if len(calls) != 256 or len(public) != 75:
        raise ValueError("Incomplete addressing schematic")
    return calls, public


def original_pins(layout, cell, master, pins):
    source = db.Layout()
    source.read(str(master / (master.name + ".gds")))
    if source.dbu != layout.dbu:
        raise ValueError(f"Different database unit for {master.name}")
    original = source.top_cell()
    infos = {source.get_info(n).to_s() for n in source.layer_indices()}
    infos.update(layout.get_info(n).to_s() for n in layout.layer_indices())
    for key in infos:
        info = db.LayerInfo.from_string(key)
        if info.datatype == 10:
            continue
        left = db.Region(original.begin_shapes_rec(source.layer(info)))
        right = db.Region(cell.begin_shapes_rec(layout.layer(info)))
        if not (left ^ right).is_empty():
            raise ValueError(f"Imported masks differ on {cell.name} {info}")
    sites = {}
    for number in METAL:
        for text in db.Texts(original.shapes(source.layer(number, 10))).each():
            if text.string in sites:
                raise ValueError(f"Duplicate source terminal on {cell.name}: {text.string}")
            sites[text.string] = (number, db.Point(text.x, text.y))
    if sites.keys() != pins:
        raise ValueError(f"Source terminal set differs for {cell.name}")
    return sites


def probe(path, fault=None):
    layout = db.Layout()
    layout.read(str(path))
    top = layout.top_cell()
    for inst in top.each_inst():
        placements = inst.cell_inst.size()
        if placements != 1:
            raise ValueError(f"Expected one physical placement for {inst.property(1)}, found {placements}")
    graph = db.LayoutToNetlist(top.name, layout.dbu)
    conductors = {}
    for number in METAL:
        layer = db.Region(top.begin_shapes_rec(layout.layer(number, 0))).merged()
        graph.register(layer, f"metal_{number}")
        graph.connect(layer)
        conductors[number] = layer
    for i, number in enumerate(VIA):
        layer = db.Region(top.begin_shapes_rec(layout.layer(number, 0))).merged()
        graph.register(layer, f"via_{number}")
        graph.connect(layer)
        graph.connect(conductors[METAL[i]], layer)
        graph.connect(layer, conductors[METAL[i+1]])
    graph.extract_netlist()

    def island(number, point):
        net = graph.probe_net(conductors[number], point)
        if net is None:
            raise ValueError(f"Missing conductor at {point} on {number}")
        return net.cluster_id

    selectors, public = source_wiring()
    connections = defaultdict(set)
    public_sites = {}
    for text in db.Texts(top.shapes(layout.layer(81, 10))).each():
        if text.string in public_sites:
            raise ValueError("Duplicate top-level terminal")
        point = db.Point(text.x, text.y)
        public_sites[text.string] = point
        connections[text.string].add(island(81, point))
    if public_sites.keys() != public:
        raise ValueError("Public 75-port array interface differs from the schematic")
    sites = {}
    seen = set()
    expected_instances = set(selectors) | {"Xregion_I", "Xregion_II", "Xregion_III"}
    for inst in top.each_inst():
        ident = inst.property(1)
        if ident not in expected_instances or ident in seen:
            raise ValueError(f"Unknown or duplicate address instance {ident}")
        seen.add(ident)
        cell = inst.cell
        name = cell.name
        if ident.startswith("Xregion_"):
            band = ident.removeprefix("Xregion_")
            master = LAYOUT / ("array_region_" + band.lower())
            leaf_calls = [line.split() for line in SOURCE.read_text().splitlines()
                          if line.startswith("Xc_") and line.split()[2].endswith("_" + band)]
            if len(leaf_calls) != (320 if band == "III" else 352):
                raise ValueError(f"Unexpected cell population in Region {band}")
            formal = sorted({net for fields in leaf_calls for net in fields[1:5]})
            nets = formal
        else:
            kind, nets = selectors[ident]
            master = LAYOUT / "array_addressing" / kind
            lines = (SOURCE.parent / (kind + ".spice")).read_text().splitlines()
            words = next(line for line in lines if line.startswith(".subckt ")).split()
            formal = [word for word in words[2:] if "=" not in word]
        if name != master.name:
            raise ValueError(f"Wrong master on {ident}: {name}")
        if name not in sites:
            sites[name] = original_pins(layout, cell, master, set(formal))
        for pin, net_name in zip(formal, nets, strict=True):
            number, local = sites[name][pin]
            connections[net_name].add(island(number, inst.trans * local))
    if seen != expected_instances:
        raise ValueError("Incomplete set of selector and array instances")
    opens = {net for net, values in connections.items() if len(values) != 1}
    if opens != ({"CSEL_7"} if fault == "open" else set()):
        raise ValueError(f"Unexpected disconnected address/supply nets: {sorted(opens)}")
    by_island = defaultdict(set)
    for name, islands in connections.items():
        for i in islands:
            by_island[i].add(name)
    shorts = {tuple(sorted(nets)) for nets in by_island.values() if len(nets) > 1}
    if shorts != ({("RSEL_0", "RSEL_1")} if fault == "short" else set()):
        raise ValueError(f"Unexpected aliases: {sorted(shorts)}")
    return public_sites, len(connections)


def fault_copy(source, kind, sites, dest):
    layout = db.Layout()
    layout.read(str(source))
    top = layout.top_cell()
    if kind == "open":
        port = sites["CSEL_7"]
        x, y = port.x, port.y - round(2 / layout.dbu)
        shapes = top.shapes(layout.layer(46, 0))
        original = db.Region(shapes)
        cut = db.Box(x - 400, y - 400, x + 400, y + 400)
        shapes.clear()
        shapes.insert(original - db.Region(cut))
    elif kind in ("XPC_11", "Xregion_III"):
        inst, = [entry for entry in top.each_inst() if entry.property(1) == kind]
        offset = db.Vector(0, round(3000 / layout.dbu))
        inst.cell_inst = db.CellInstArray(inst.cell_index, inst.trans, offset, db.Vector(), 2, 1)
    elif kind == "short":
        a, b = sites["RSEL_0"], sites["RSEL_1"]
        x = max(a.x, b.x) + round(5 / layout.dbu)
        top.shapes(layout.layer(81, 0)).insert(db.Box(x-250, min(a.y,b.y), x+250, max(a.y,b.y)))
    else:
        raise ValueError(f"Unknown physical control {kind}")
    options = db.SaveLayoutOptions()
    options.gds2_write_timestamps = False
    layout.write(str(dest), options)


def main():
    source = HERE / "array_32x32.gds"
    sites, count = probe(source)
    print(f"75 pins, 256 selector macros, three complete memory regions, {count} distinct interface nets")
    with tempfile.TemporaryDirectory() as tmp:
        for kind in ("open", "short"):
            fault = Path(tmp) / (kind + ".gds")
            fault_copy(source, kind, sites, fault)
            probe(fault, kind)
            print(f"Physical {kind} control detected")
        for ident in ("XPC_11", "Xregion_III"):
            duplicate = Path(tmp) / (ident + ".gds")
            fault_copy(source, ident, sites, duplicate)
            try:
                probe(duplicate)
            except ValueError as exc:
                if str(exc) != f"Expected one physical placement for {ident}, found 2":
                    raise
            else:
                raise AssertionError(f"An extra physical placement escaped the probe: {ident}")
            print(f"Duplicate placement of {ident} detected")


if __name__ == "__main__":
    main()
