# /// script
# dependencies = ["klayout==0.30.13"]
# ///
"""Compose the three physical memory bands and their 128 selection pairs."""
import argparse
import tempfile
from collections import defaultdict
from pathlib import Path

import klayout.db as db

HERE = Path(__file__).resolve().parent
LAYOUT = HERE.parent
SOURCE = LAYOUT.parent / "design/netlists/array_32x32.spice"
TOP = "array_32x32"
BANDS = ("I", "II", "III")
CONTROLS = ("ls_hv06", "ls_hv10", "pg_n06", "pg_n10")


def spice_interface(text, name):
    for line in text.splitlines():
        words = line.split()
        if len(words) >= 2 and words[:2] == [".subckt", name]:
            return [token for token in words[2:] if "=" not in token]
    raise ValueError(f"Missing interface for {name}")


def master_path(name):
    return LAYOUT / "array_addressing" / name if name in CONTROLS else LAYOUT / name


def import_master(layout, name):
    original = db.Layout()
    original.read(str(master_path(name) / (name + ".gds")))
    src = original.top_cell()
    if original.dbu != layout.dbu or src.name != name:
        raise ValueError(f"Different grid or master name in {name}")
    pins = {}
    for metal in (34, 36, 42, 46, 81):
        index = original.layer(metal, 10)
        for text in db.Texts(src.shapes(index)).each():
            if text.string in pins:
                raise ValueError(f"Duplicate {name} port {text.string}")
            pins[text.string] = (metal, text.x * original.dbu, text.y * original.dbu)
        # Replace only the top-level terminals. Internal conductor masks remain.
        src.shapes(index).clear()
    dest = layout.create_cell(name)
    dest.copy_tree(src)
    if name.startswith("array_region_"):
        # copy_tree traverses KLayout's spatial index in platform-dependent
        # order. Restore explicit row/column order before the GDS writer.
        instances = sorted(((i.cell_inst, i.prop_id) for i in dest.each_inst()),
                           key=lambda row: (row[0].trans.disp.y, row[0].trans.disp.x))
        dest.clear_insts()
        for placement, properties in instances:
            dest.insert(placement, properties)
    return dest, pins


def box_wire(layout, top, layer, x, y, end_x, end_y, width=0.5):
    if x != end_x and y != end_y:
        raise ValueError("A routing segment must be orthogonal")
    half = width / 2
    box = db.DBox(min(x, end_x) - half, min(y, end_y) - half,
                  max(x, end_x) + half, max(y, end_y) + half)
    top.shapes(layout.layer(layer, 0)).insert(box)


def selectors(source):
    calls = []
    for line in source.splitlines():
        words = line.split()
        if words and words[0].startswith(("XLC_", "XPC_", "XLR_", "XPR_")):
            call = [token for token in words if "=" not in token]
            calls.append((call[0], call[-1], call[1:-1]))
    if len(calls) != 256:
        raise ValueError(f"Expected 128 row/column selection pairs, found {len(calls)} calls")
    for first, second in zip(calls[::2], calls[1::2]):
        if (first[0].replace("XL", "XP", 1) != second[0] or
                not first[1].startswith("ls_") or not second[1].startswith("pg_")):
            raise ValueError(f"Unexpected selector pairing: {first[0]}, {second[0]}")
    return calls


def draw(destination):
    source = SOURCE.read_text()
    public = spice_interface(source, TOP)
    layout = db.Layout()
    layout.dbu = 0.001
    top = layout.create_cell(TOP)
    masters = {}
    terminals = {}
    references = []
    names = ["array_region_" + b.lower() for b in BANDS] + list(CONTROLS)
    for name in names:
        masters[name], terminals[name] = import_master(layout, name)
        references.append((master_path(name) / "reference.spice").read_text().strip())
    interfaces = {name: spice_interface(text, name) for name, text in zip(names, references)}
    for name, pins in interfaces.items():
        if set(pins) != set(terminals[name]):
            raise ValueError(f"{name} terminals differ from its SPICE interface")
    references.append(".subckt " + TOP + " " + " ".join(public))
    endpoints = defaultdict(list)

    def place(name, instance, x, y):
        inst = top.insert(db.DCellInstArray(masters[name].cell_index(), db.DTrans(db.DVector(x, y))))
        inst.set_property(1, instance)

    def wire(layer, x, y, ex, ey, width=0.5):
        box_wire(layout, top, layer, x, y, ex, ey, width)

    def meet_m4(metal, x, y):
        if metal == 46:
            return
        cut = {42: 40, 81: 41}[metal]
        wire(cut, x, y, x, y, 0.26)
        wire(46, x, y, x, y)

    def add_capacitor_wells(master, x, y):
        # The non-DNWELL GF180 cap_nmos PCell draws LVPWELL exactly on the
        # capacitor active island (draw_cap_mos.py, cap_mos_inst). Native LVS
        # requires its P2 plate on that layer. Preserve all imported masks.
        def polygons(number, datatype=0):
            return db.Region(master.begin_shapes_rec(layout.layer(number, datatype))).merged()

        active = polygons(22)
        gate = active & polygons(30) & polygons(166, 5)
        body = active.interacting(gate)
        if body.count() != 352 or not (body & (polygons(21) | polygons(12))).is_empty():
            raise ValueError(f"Unexpected non-DNWELL NMOS capacitor population in {master.name}")
        shift = db.Trans(round(x / layout.dbu), round(y / layout.dbu))
        # Region iterators also traverse a platform-dependent spatial tree.
        for polygon in sorted(body.each(), key=lambda p: (p.bbox().bottom, p.bbox().left)):
            top.shapes(layout.layer(204, 0)).insert(polygon.transformed(shift))

    left = 0.
    for band in BANDS:
        name = "array_region_" + band.lower()
        origin = left + 80.
        bottom = 20.
        instance = "Xregion_" + band
        place(name, instance, origin, bottom)
        if band in ("I", "II"):
            add_capacitor_wells(masters[name], origin, bottom)
        references.append(" ".join([instance, *interfaces[name], name]))
        for pin in interfaces[name]:
            metal, local_x, local_y = terminals[name][pin]
            x, y = origin + local_x, bottom + local_y
            if pin.startswith(("WL_", "PL_")):
                role, row, _ = pin.split("_")
                lane = origin - 8 - (2 * int(row) + int(role == "PL"))
                wire(metal, x, y, lane, y)
                meet_m4(metal, lane, y)
            else:
                if metal != 46:
                    raise ValueError(f"Expected a Metal4 bit line or body spine for {pin}")
                lane = x
            endpoints[pin].append((lane, y))
        left = origin + masters[name].dbbox().right + 5

    # Each 16-pair bank has a dedicated external Metal4 lane for each local
    # terminal. Pass gates and their level shifters occupy separate y strips.
    calls = selectors(source)
    for pair_index in range(len(calls) // 2):
        bank, row = divmod(pair_index, 16)
        base_x, base_y = left + 250 * bank, 20. + 80 * row
        for slot, (instance, name, pins) in enumerate(calls[2 * pair_index:2 * pair_index + 2]):
            y0 = base_y + 38 * slot
            place(name, instance, base_x, y0)
            if len(pins) != len(interfaces[name]):
                raise ValueError(f"Wrong number of terminals on {instance}")
            references.append(" ".join([instance, *pins, name]))
            for i, (formal, net) in enumerate(zip(interfaces[name], pins)):
                metal, x, y = terminals[name][formal]
                if metal != 42:
                    raise ValueError(f"Expected Metal3 at {name}.{formal}")
                y += y0
                lane = base_x + 82 + 10 * row + 6 * slot + i
                wire(42, base_x + x, y, lane, y)
                meet_m4(42, lane, y)
                endpoints[net].append((lane, y))
    if not set(public) <= endpoints.keys():
        raise ValueError("A row, column or supply terminal has no endpoint")
    # A break in a gate's long M4 escape limits the gate area exposed before
    # M5 deposition. Select a short M5 bridge clear of the imported geometry.
    existing_m5 = db.Region(top.begin_shapes_rec(layout.layer(81, 0))).merged()

    def route_gate_escape(x, start, end):
        bridge_y = start + 1.0
        while bridge_y + 2.0 < end:
            # Half-width 0.25 µm plus 0.31 µm clearance to existing top metal.
            keepout = db.DBox(x - 0.56, bridge_y - 0.56, x + 0.56, bridge_y + 2.56)
            if existing_m5.interacting(db.Region(keepout.to_itype(layout.dbu))).is_empty():
                wire(46, x, start, x, bridge_y)
                meet_m4(81, x, bridge_y)
                wire(81, x, bridge_y, x, bridge_y + 2.0)
                meet_m4(81, x, bridge_y + 2.0)
                wire(46, x, bridge_y + 2.0, x, end)
                return
            bridge_y += 1.0
        raise ValueError(f"No clear Metal5 bridge on lane {x} between {start} and {end}")

    channel_y = top.dbbox().top + 5
    for i, (net, points) in enumerate(sorted(endpoints.items())):
        y = channel_y + 1.25 * i
        xs = [x for x, _ in points]
        gate = net.startswith(("RSEL_", "CSEL_", "WL_", "CG_", "RGB_", "CGB_"))
        channel_metal = 42 if gate else 81
        for x, start in points:
            if gate and y - start > 12.0:
                route_gate_escape(x, start, y)
            else:
                wire(46, x, start, x, y)
            meet_m4(channel_metal, x, y)
        wire(channel_metal, min(xs), y, max(max(xs), min(xs) + 0.75), y)
        if gate and net in public:
            # Preserve the M5 port while keeping the long horizontal route on M3.
            meet_m4(81, min(xs), y)
            wire(81, min(xs), y, min(xs) + 0.75, y)
        if net in public:
            top.shapes(layout.layer(81, 10)).insert(db.DText(net, min(xs), y))
    references.append(".ends")
    (destination / "reference.spice").write_text("\n".join(references) + "\n")
    opts = db.SaveLayoutOptions()
    opts.gds2_write_timestamps = False
    layout.write(str(destination / (TOP + ".gds")), opts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        dest = Path(temp) if args.check else HERE
        draw(dest)
        for item in (TOP + ".gds", "reference.spice"):
            if args.check and (dest / item).read_bytes() != (HERE / item).read_bytes():
                raise SystemExit(f"Regeneration differs for {item}")


if __name__ == "__main__":
    main()
