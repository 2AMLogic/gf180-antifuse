#!/usr/bin/env python3
"""Scrub host paths out of a klt report before it is committed.

Keep the committed report free of host paths: repo-relative, or ~ for the PDK.
rtl/pnr/run_pnr.sh and rtl/sta/run_sta.sh carried two identical copies of this
until issue #285; one implementation means the next case - a new tool emitting
an absolute path, a cache directory that needs collapsing - lands once.

Usage: rtl/scrub_report_paths.py <src> [dst]   (run from the repo root, as
run_pnr.sh and run_sta.sh do; dst defaults to src, i.e. rewrite in place)
"""
import json
import os
import sys

root, home = os.getcwd() + "/", os.path.expanduser("~") + "/"


def clean(v):
    if isinstance(v, str):
        return v.replace(root, "").replace(home, "~/")
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    return v


src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 else src
with open(src) as f:
    report = json.load(f)
with open(dst, "w") as f:
    json.dump(clean(report), f, indent=2)
    f.write("\n")
