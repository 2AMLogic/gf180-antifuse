"""Route a cell matrix from the 32 x 32 schematic's cell calls."""
import argparse
import sys
import tempfile
from pathlib import Path

import klayout.db as db

from regions import I, III, LAYOUT

ROOT = LAYOUT.parent
sys.path.insert(0, str(LAYOUT))
sys.path.insert(0, str(LAYOUT / "run3_top"))
from assemble_run3_top import PIN_OFFSET_UM
from candidate1_points import POINTS as C1_POINTS
from candidate3_points import POINTS as C3_POINTS

# Region III wide-access cells sit outside the representative Run 3 assembly.
# Their plate landing shares the existing diffusion strap, and each body
# landing stays on the north metal strap joining the two N-well rings.
LANDINGS = {
    **PIN_OFFSET_UM,
    "cell_candidate3_A2x_Gmin": {"BL": (0.21, 0.42), "WL": (0.775, 1.80),
                                "PL": (5.8, 0.36), "VB": (2.655, 3.595)},
    "cell_candidate3_A2x_G2x": {"BL": (0.21, 0.42), "WL": (0.775, 1.80),
                               "PL": (5.8, 0.36), "VB": (3.50, 4.385)},
}
SOURCE = ROOT / "design/netlists/array_32x32.spice"
PITCH_X, PITCH_Y = 12, 9  # um; separate the drawn cells and their tap buses.
METALS = (34, 36, 42, 46, 81)
VIAS = (35, 38, 40, 41)
# Schematic split levels, not drawn widths. geometry-basis.json records the mapping.
VARIANTS = {("1e-6", "0.30u"): "Amin_Gmin", ("2e-6", "0.30u"): "Amin_G2x",
            ("1e-6", "0.6u"): "A2x_Gmin", ("2e-6", "0.6u"): "A2x_G2x"}


def cell_calls(region):
    points = {I: C1_POINTS, III: C3_POINTS}[region]
    calls = {}
    for line in SOURCE.read_text().splitlines():
        fields = line.split()
        if fields[:1] and fields[0].startswith("Xc_") and fields[5] == region.candidate:
            _, row, col = fields[0].split("_")
            row, col = int(row), int(col)
            pins = fields[1:5]
            if pins != [f"BL_{col}", f"WL_{row}_{region.name}", f"PL_{row}_{region.name}", region.body] or (row, col) in calls:
                raise ValueError(f"Unexpected Region {region.name} connectivity: {line}")
            params = dict(field.split("=") for field in fields[6:])
            if (params["lcap"], params["lacc"], params["m"]) != ("1e-6", region.access_length, "1"):
                raise ValueError(f"Recheck the drawn/simulated geometry basis: {line}")
            name = points[VARIANTS[params["wcap"], params["wacc"]]][0]
            calls[row, col] = (name, fields[:5])
    if set(calls) != {(row, col) for row in range(32) for col in region.columns}:
        raise ValueError(f"Missing or unexpected coordinates in Region {region.name}")
    return calls


def draw(region, dest):
    layout = db.Layout()
    layout.dbu = 0.0005
    top = layout.create_cell(region.top)
    calls = cell_calls(region)
    leaves = {}
    reference = []
    for name in sorted({name for name, _ in calls.values()}):
        cell_dir = LAYOUT / name
        source = db.Layout()
        source.read(str(cell_dir / (name + ".gds")))
        leaf = layout.create_cell(name)
        # Four streams can reuse subcell names for distinct geometry. Flatten
        # each isolated leaf before import, keeping the four variants separate.
        source.top_cell().flatten(-1, True)
        for layer in source.layer_indices():
            info = source.get_info(layer)
            if info.datatype != 10:  # Replace the leaf labels with the array nets.
                leaf.shapes(layout.layer(info)).insert(source.top_cell().shapes(layer))
        leaves[name] = leaf
        reference.append((cell_dir / "lvs_reference.spice").read_text().strip())

    def wire(layer, x1, y1, x2, y2, width=0.50):
        h = width / 2
        box = db.DBox(min(x1, x2) - h, min(y1, y2) - h, max(x1, x2) + h, max(y1, y2) + h)
        top.shapes(layout.layer(layer, 0)).insert(box)

    def ladder(x, y, lower, upper):
        for i in range(lower - 1, upper - 1):
            wire(VIAS[i], x, y, x, y, 0.26)
            wire(METALS[i + 1], x, y, x, y)

    def label(name, metal, x, y):
        top.shapes(layout.layer(metal, 10)).insert(db.DText(name, x, y))

    ports = ([f"BL_{col}" for col in region.columns] + [f"WL_{row}_{region.name}" for row in range(32)]
             + [f"PL_{row}_{region.name}" for row in range(32)] + [region.body])
    reference.append(".subckt " + region.top + " " + " ".join(ports))
    for (row, col), (name, fields) in sorted(calls.items()):
        x, y = (col - region.columns.start) * PITCH_X, row * PITCH_Y
        top.insert(db.DCellInstArray(leaves[name].cell_index(), db.DTrans(db.DVector(x, y))))
        reference.append(" ".join(fields + [name]))
        for pin, end_layer in (("BL", 4), ("WL", 3), ("PL", 5), ("VB", 2)):
            px, py = LANDINGS[name][pin]
            ladder(x + px, y + py, 1, end_layer)
            if pin == "WL":
                wire(42, x + px, y + py, x + px, y + 1.8)
            if pin == "VB":
                wire(34, x + px, y + py, x + px, y + py)  # Enclose via1 on the tap ring.
                wire(36, x + px, y + py, x + px, y + 6)

    last_x = (len(region.columns) - 1) * PITCH_X
    # BL, WL, and PL share one x coordinate across each band's four variants.
    # The body track reaches the rightmost variant's tap in every row.
    common = LANDINGS[region.candidate]
    body_x = max(LANDINGS[name]["VB"][0] for name in leaves)
    for row in range(32):
        y = row * PITCH_Y
        for pin, metal, dy in (("WL", 42, 1.8), ("PL", 81, 0.36)):
            x = common[pin][0]
            wire(metal, x, y + dy, last_x + x, y + dy)
            label(f"{pin}_{row}_{region.name}", metal, x, y + dy)
        wire(36, -3, y + 6, last_x + body_x, y + 6)
        ladder(-3, y + 6, 2, 4)
    for col in region.columns:
        x = (col - region.columns.start) * PITCH_X + common["BL"][0]
        wire(46, x, 0.21, x, 31 * PITCH_Y + 0.42)
        label(f"BL_{col}", 46, x, 0.21)
    wire(46, -3, 6, -3, 31 * PITCH_Y + 6)
    label(region.body, 46, -3, 6)
    reference.append(".ends")
    (dest / "reference.spice").write_text("\n".join(reference) + "\n")
    options = db.SaveLayoutOptions()
    options.gds2_write_timestamps = False
    options.dbu = 0.001  # Native GF180 runset grid; source GDS uses 0.0005.
    layout.write(str(dest / (region.top + ".gds")), options)


def main(region):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) if args.check else region.directory
        draw(region, dest)
        for name in (region.top + ".gds", "reference.spice"):
            if args.check and (dest / name).read_bytes() != (region.directory / name).read_bytes():
                raise SystemExit(f"Stale generated file: {name}")
