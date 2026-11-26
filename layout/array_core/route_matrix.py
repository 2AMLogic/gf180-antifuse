"""Route a cell matrix from the 32 x 32 schematic's cell calls."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import klayout.db as db

from regions import I, II, III, LAYOUT

ROOT = LAYOUT.parent
sys.path.insert(0, str(LAYOUT))
sys.path.insert(0, str(LAYOUT / "run3_top"))
from assemble_run3_top import PIN_OFFSET_UM
from candidate1_points import POINTS as C1_POINTS
from candidate2_points import POINTS as C2_POINTS
from candidate3_points import POINTS as C3_POINTS

# Region III wide-access cells sit outside the representative Run 3 assembly.
# Their plate landing shares the existing diffusion strap, and each body
# landing stays on the north metal strap joining the two N-well rings.
C2_LANDINGS = {**PIN_OFFSET_UM["cell_candidate2"], "VB": (3.65, 2.99)}
LANDINGS = {
    **PIN_OFFSET_UM,
    "cell_candidate2": C2_LANDINGS,
    "cell_candidate2_Amin_G2x": C2_LANDINGS,
    "cell_candidate2_A2x_Gmin": {**C2_LANDINGS, "WL": (0.0, 4.91)},
    "cell_candidate2_A2x_G2x": {**C2_LANDINGS, "WL": (0.0, 4.91)},
    "cell_candidate3_A2x_Gmin": {"BL": (0.21, 0.42), "WL": (0.775, 1.80),
                                "PL": (5.8, 0.36), "VB": (2.655, 3.595)},
    "cell_candidate3_A2x_G2x": {"BL": (0.21, 0.42), "WL": (0.775, 1.80),
                               "PL": (5.8, 0.36), "VB": (3.50, 4.385)},
}
SOURCE = ROOT / "design/netlists/array_32x32.spice"
METALS = (34, 36, 42, 46, 81)
VIAS = (35, 38, 40, 41)
# Translate each band's simulated width levels to its split names. The
# separate geometry-basis record tracks the corresponding drawn widths.
CAP_LEVELS = {"1e-6": "Gmin", "2e-6": "G2x"}
ACCESS_LEVELS = {I: {"0.30u": "Amin", "0.6u": "A2x"},
                 II: {"25u": "Amin", "50u": "A2x"},
                 III: {"0.30u": "Amin", "0.6u": "A2x"}}


def cell_calls(region):
    points = {I: C1_POINTS, II: C2_POINTS, III: C3_POINTS}[region]
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
            access = ACCESS_LEVELS[region][params["wacc"]]
            cap = CAP_LEVELS[params["wcap"]]
            name = points[f"{access}_{cap}"][0]
            calls[row, col] = (name, fields[:5])
    if set(calls) != {(row, col) for row in range(32) for col in region.columns}:
        raise ValueError(f"Missing or unexpected coordinates in Region {region.name}")
    return calls


def draw(region, dest):
    pitch_x, pitch_y = region.pitch
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

    if region == II:
        # The P-substrate has no drawn boundary. Require one contact-qualified
        # tie in each of the two explicit ring windows per original cell.
        spec = json.loads((LAYOUT / "erc/supplies_c2.json").read_text())
        local_boxes = {}
        for name in leaves:
            source = LAYOUT / ("erc/supplies_c2.json" if name == region.candidate else name + "/supplies.json")
            local_boxes[name] = json.loads(source.read_text())["ties"][0]["well_boxes"]
        boxes = []
        for (row, col), (name, _) in sorted(calls.items()):
            x, y = (col - region.columns.start) * pitch_x, row * pitch_y
            boxes.extend([[round(x + l, 3), round(y + b, 3), round(x + r, 3), round(y + t, 3)]
                          for l, b, r, t in local_boxes[name]])
        for layer in spec["stackup"]:
            if layer["name"] in ("metal1", "metal2"):
                layer.pop("label_layer", None)
        spec["nets"][0]["name"] = region.body
        spec["ties"][0].update(name="vss_psub_region_ii", net=region.body, well_boxes=boxes)
        (dest / "supplies.json").write_text(json.dumps(spec, separators=(",", ":")) + "\n")

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
        x, y = (col - region.columns.start) * pitch_x, row * pitch_y
        top.insert(db.DCellInstArray(leaves[name].cell_index(), db.DTrans(db.DVector(x, y))))
        reference.append(" ".join(fields + [name]))
        for pin, end_layer in (("BL", 4), ("WL", 3), ("PL", 5), ("VB", 2)):
            px, py = LANDINGS[name][pin]
            ladder(x + px, y + py, 1, end_layer)
            if pin == "WL":
                wire(42, x + px, y + py, x + px, y + region.word_y)
            if pin == "VB":
                wire(34, x + px, y + py, x + px, y + py)  # Enclose via1 on the tap ring.
                wire(36, x + px, y + py, x + px, y + region.body_y)

    last_x = (len(region.columns) - 1) * pitch_x
    # BL, WL, and PL share one x coordinate across each band's four variants.
    # The body track reaches the rightmost variant's tap in every row.
    common = LANDINGS[region.candidate]
    body_x = max(LANDINGS[name]["VB"][0] for name in leaves)
    for row in range(32):
        y = row * pitch_y
        for pin, metal, dy in (("WL", 42, region.word_y), ("PL", 81, common["PL"][1])):
            x = common[pin][0]
            wire(metal, x, y + dy, last_x + x, y + dy)
            label(f"{pin}_{row}_{region.name}", metal, x, y + dy)
        wire(36, region.spine_x, y + region.body_y, last_x + body_x, y + region.body_y)
        ladder(region.spine_x, y + region.body_y, 2, 4)
    for col in region.columns:
        x = (col - region.columns.start) * pitch_x + common["BL"][0]
        wire(46, x, common["BL"][1], x, 31 * pitch_y + 0.42)
        label(f"BL_{col}", 46, x, common["BL"][1])
    wire(46, region.spine_x, region.body_y, region.spine_x, 31 * pitch_y + region.body_y)
    label(region.body, 46, region.spine_x, region.body_y)
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
        names = [region.top + ".gds", "reference.spice"]
        if region == II:
            names.append("supplies.json")
        for name in names:
            if args.check and (dest / name).read_bytes() != (region.directory / name).read_bytes():
                raise SystemExit(f"Stale generated file: {name}")
