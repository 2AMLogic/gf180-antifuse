# /// script
# requires-python = ">=3.10"
# dependencies = ["klayout==0.30.14"]
# ///
"""Apply GF180 density fill to the addressed array and verify the original masks."""

import argparse
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import urlopen

import klayout.db as db

HERE = Path(__file__).resolve().parent
FILL = "https://raw.githubusercontent.com/2AMLogic/gf180-efuse-otp/a8e9d4b05a0c3e42896e36e69d1335263221e02d/layout/fill_partitions.py"
FILL_SHA = "945cf0d3ebac6e2342eb029c3e293320e28dea642fa928d18b65f8c1916c8c17"
MASKS = {(layer, 4) for layer in (22, 30, 34, 36, 42, 46, 81)}


def publish(source, filled, scratch, output):
    layout = db.Layout()
    layout.read(str(filled))
    top = layout.top_cell()
    fill = layout.cell("density_fill")
    if top.name != "array_32x32" or fill is None:
        raise ValueError("Expected one array top and its generated density_fill cell")
    placed = [ref for ref in top.each_inst() if ref.cell == fill]
    if (
        len(placed) != 1
        or placed[0].is_regular_array()
        or placed[0].cplx_trans != db.ICplxTrans()
        or list(fill.each_inst())
    ):
        raise ValueError("Expected one untransformed, flat fill placement")
    layers = [i for i in layout.layer_indices() if fill.shapes(i).size()]
    if {
        (layout.get_info(i).layer, layout.get_info(i).datatype) for i in layers
    } != MASKS:
        raise ValueError("Fill includes unexpected masks or a required mask is empty")
    added = [(i, db.Region(fill.shapes(i))) for i in layers]
    placed[0].delete()
    layout.delete_cell(fill.cell_index())
    options = db.SaveLayoutOptions()
    options.gds2_write_timestamps = False
    # Reload the stripped stream to discard unused GDS layer-table entries.
    stripped = scratch / "stripped.gds"
    layout.write(str(stripped), options)
    restored = db.Layout()
    restored.read(str(stripped))
    original = db.Layout()
    original.read(str(source))
    if not db.LayoutDiff().compare(original, restored, 0):
        raise ValueError("Removing the fill did not recover the exact original layout")
    # Keep the addressing hierarchy and every instance property intact: the
    # top-level probe identifies each selector and memory band by its property.
    for index, region in added:
        top.shapes(index).insert(region)
    staged = scratch / "verified.gds"
    layout.write(str(staged), options)
    os.replace(staged, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE.parent / "array_32x32.gds")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--fill-script",
        type=Path,
        help="offline copy of the pinned GF180 fill generator",
    )
    args = parser.parse_args()
    source, output = args.input.resolve(), args.output.resolve()
    if output == source:
        parser.error("Write the filled view to a separate GDS path")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as td:
        scratch = Path(td)
        script = args.fill_script
        if script is None:
            script = scratch / "fill_partitions.py"
            with urlopen(FILL, timeout=30) as response:
                script.write_bytes(response.read())
        if sha256(script.read_bytes()).hexdigest() != FILL_SHA:
            raise ValueError("Unexpected GF180 fill generator")
        filled = scratch / "hierarchical.gds"
        subprocess.run(
            [
                sys.executable,
                script,
                "--input",
                source,
                "--top",
                "array_32x32",
                "--output",
                filled,
                "--report",
                scratch / "fill.json",
            ],
            check=True,
        )
        publish(source, filled, scratch, output)


if __name__ == "__main__":
    main()
