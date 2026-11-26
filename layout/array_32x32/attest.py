# /// script
# dependencies = ["klayout==0.30.13"]
# ///
"""Bind T1 analog item 2 to a fresh rebuild of the full addressed array."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

import klayout.db as db

from generate import draw, HERE, TOP


def attest():
    with tempfile.TemporaryDirectory() as temporary:
        destination = Path(temporary)
        draw(destination)
        rebuilt = (destination / (TOP + ".gds")).read_bytes()
        reference = (destination / "reference.spice").read_bytes()
    if reference != (HERE / "reference.spice").read_bytes():
        raise ValueError("Regenerated array connectivity reference differs")
    gds = HERE / (TOP + ".gds")
    if rebuilt != gds.read_bytes():
        raise ValueError("Regenerated array GDS differs")
    fingerprint = "sha256:" + hashlib.sha256(rebuilt).hexdigest()
    path = gds.relative_to(HERE.parents[1]).as_posix()
    return {
        "schema_version": 1, "kind": "generic", "t1_item": 2, "status": "pass",
        "source": "layout/array_32x32/generate.py",
        "summary": "The 1,024-cell, 75-port analog array, including all 128 row/column "
                   "selector pairs, reproduces the committed GDS byte for byte.",
        "provenance": {
            "klayout_version": db.__version__,
            "input": {"path": {"path": path, "scope": "repo"},
                      "content_hash": fingerprint, "role": "layout"},
            "regeneration": {"generator": "uv run --no-project --script "
                             "layout/array_32x32/generate.py --check",
                             "regenerated_hash": fingerprint},
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = json.dumps(attest(), indent=2) + "\n"
    dest = HERE / "layout.attest.json"
    if args.check:
        if dest.read_text() != result:
            raise SystemExit("The committed item-2 envelope differs from a fresh rebuild")
    else:
        dest.write_text(result)


if __name__ == "__main__":
    main()
