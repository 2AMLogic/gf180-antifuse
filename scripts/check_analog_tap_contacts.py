# /// script
# dependencies = ["klayout-tools==0.9.2", "klayout==0.30.13"]
# ///
"""Exercise actual analog body contacts on copies of the committed GF180 streams."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import klayout.db as db

ROOT = Path(__file__).resolve().parents[1]
KLT = Path(sys.executable).with_name("klt")


def run_erc(gds, spec_path, top, expected_findings):
    args = [KLT, "erc", gds, spec_path, "--top", top, "--format", "json"]
    if top == "run3_top":
        args += ["--pdk", "gf180mcu", "--deck", "gf180mcu"]
    run = subprocess.run(args, capture_output=True, text=True, check=False)
    # These streams have no antenna-limit tables. Their clean ERC exits 4.
    expected_exit = 3 if expected_findings else 4
    if run.returncode != expected_exit:
        raise ValueError(f"{gds.name}: expected exit {expected_exit}, got {run.returncode}: {run.stderr}")
    report = json.loads(run.stdout)
    findings = []
    for finding in report["erc_findings"]:
        bbox = finding["bbox"]
        findings.append((finding["rule"], finding["net"], finding["layer"],
                         tuple(bbox[key] for key in ("left", "bottom", "right", "top"))))
    if sorted(findings) != sorted(expected_findings):
        raise ValueError(f"{gds.name}: expected {expected_findings}, found {findings}")
    coverage = report["erc_coverage"]
    spec = json.loads(spec_path.read_text())
    for tie in spec["ties"]:
        if f'erc.missing_tie:["{tie["name"]}"]' not in coverage["checked"]:
            raise ValueError(f"{gds.name}: coverage missing for {tie['name']}")
    islands = {net["name"]: net["matched_islands"] for net in report["nets"]}
    if top == "run3_top":
        expected_islands = {"VSS_ANALOG": 1, "VBW_C3": 1}
    elif top == "array_region_iii":
        expected_islands = {"VDDH_III": 1}
    elif top.startswith("cell_candidate3"):
        expected_islands = {}  # The Region III spec declares VB ties only.
    else:
        expected_islands = {"VB": 1}
    expected_status = "violations" if expected_findings else "clean"
    if coverage["skipped"] or report["erc_status"] != expected_status or islands != expected_islands:
        raise ValueError(f"{gds.name}: {coverage['skipped']=}, {report['erc_status']=}, {islands=}")


def check_open(gds, spec_path, tie, dest, single_well=False, expected_wells=None):
    layout = db.Layout()
    layout.read(str(gds))
    top = layout.top_cell()

    def region(layer):
        return db.Region(top.begin_shapes_rec(layout.layer(layer, 0))).merged()

    wells = region(21)
    active = region(22)
    if tie["well_layer"] is None:
        bodies = [db.DBox(*box).to_itype(layout.dbu) for box in tie["well_boxes"]]
        taps = (active & region(31)) - wells
    else:
        bodies = [polygon.bbox() for polygon in wells.each()]
        taps = active & region(32) & wells
    if expected_wells is not None and len(bodies) != expected_wells:
        raise ValueError(f"{gds.name}: expected {expected_wells} wells, found {len(bodies)}")
    if single_well:
        if len(bodies) < 2:
            raise ValueError(f"{gds.name}: single-well control requires multiple drawn wells")
        bodies = [min(bodies, key=lambda box: (box.left, box.bottom))]
        taps &= db.Region(bodies[0])
    layer = layout.layer(33, 0)
    contacts = region(33)
    opens = contacts.inside(taps)
    if not bodies or opens.is_empty():
        raise ValueError(f"{gds.name}: no body or contact for {tie['name']}")
    # Preserve hierarchy, labels and overlapping non-contact layers. Put the
    # surviving cuts at top level so repeated instance geometry is edited once.
    for cell in layout.each_cell():
        cell.shapes(layer).clear()
    top.shapes(layer).insert(contacts - opens)
    fault = dest / f"{gds.stem}-{tie['name']}-{'single' if single_well else 'all'}.gds"
    layout.write(str(fault))
    expected = [("erc.missing_tie", tie["net"], tie["name"],
                 (box.left, box.bottom, box.right, box.top)) for box in bodies]
    run_erc(fault, spec_path, gds.stem, expected)
    print(f"{fault.stem}: {opens.count()} contacts opened, {len(bodies)} missing ties")


def main():
    layout_dir = ROOT / "layout"
    directories = [layout_dir / name for name in (
        "cell_candidate1", "cell_candidate1_A2x_G2x", "cell_candidate1_A2x_Gmin",
        "cell_candidate1_Amin_G2x", "cell_candidate2", "cell_candidate3",
        "cell_candidate3_Amin_G2x", "cell_candidate3_A2x_Gmin", "cell_candidate3_A2x_G2x", "run3_top")]
    with tempfile.TemporaryDirectory() as temp:
        for directory in directories:
            report = json.loads((directory / "erc_report.json").read_text())
            gds = ROOT / report["file"]["path"]
            spec_root = ROOT if report["spec"].startswith("layout/") else directory
            spec_path = spec_root / report["spec"]
            ties = json.loads(spec_path.read_text())["ties"]
            if gds.stem == "run3_top":
                expected_ties = {"vss_psub_left_column": "VSS_ANALOG", "vbw_nwell_right_column": "VBW_C3"}
            elif gds.stem.startswith("cell_candidate3"):
                expected_ties = {"vb_nwell_region_iii": "VB"}
            else:
                expected_ties = {"vb_psub_region_i": "VB"}
            if {tie["name"]: tie["net"] for tie in ties} != expected_ties:
                raise ValueError(f"{spec_path}: expected {expected_ties}")
            run_erc(gds, spec_path, gds.stem, [])
            for tie in ties:
                check_open(gds, spec_path, tie, Path(temp))
                if gds.stem == "run3_top" and tie["well_layer"]:
                    check_open(gds, spec_path, tie, Path(temp), single_well=True)

        directory = layout_dir / "array_region_iii"
        spec_path = directory / "supplies.json"
        gds = directory / "array_region_iii.gds"
        tie, = json.loads(spec_path.read_text())["ties"]
        if tie["net"] != "VDDH_III" or tie["tap_requires"] != ["32/0", "33/0"]:
            raise ValueError("Region III requires N+ active contacts to VDDH_III")
        run_erc(gds, spec_path, gds.stem, [])
        check_open(gds, spec_path, tie, Path(temp), single_well=True, expected_wells=640)


if __name__ == "__main__":
    main()
