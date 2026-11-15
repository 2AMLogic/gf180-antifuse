#!/usr/bin/env python3
"""Scrub host paths out of a klt report before it is committed.

Keep the committed report free of host paths: repo-relative, or ~ for the PDK.
rtl/pnr/run_pnr.sh and rtl/sta/run_sta.sh carried two identical copies of this
until issue #285; one implementation means the next case - a new tool emitting
an absolute path, a cache directory that needs collapsing - lands once.

Usage: rtl/scrub_report_paths.py <src> [dst]   (run from the repo root, as
run_pnr.sh and run_sta.sh do; dst defaults to src, i.e. rewrite in place)

Collapses three prefixes, longest-first: the repo root (repo-relative), $HOME
(~), and $PDK_ROOT (~/<basename>, the form the committed reports already use
for the ciel/volare search roots). A PDK resolved via $PDK_ROOT outside $HOME
has no ~-under-HOME shape for the plain home collapse to catch; the $PDK_ROOT
rule canonicalizes it to the same portable form. Anything that still survives
is an absolute path the scrubber has no rule for - the flow scripts run
`klt env-provenance lint-envelope` right after this helper (issue #316), and
that lint stops the run instead of letting the path into the committed report.
"""
import json
import os
import sys

root, home = os.getcwd() + "/", os.path.expanduser("~") + "/"
pdk_root = os.environ.get("PDK_ROOT", "").rstrip("/")
if pdk_root.startswith("/") and pdk_root != "/":
    pdk_form = "~/" + os.path.basename(pdk_root)
else:
    pdk_root, pdk_form = "", None


def clean(v):
    if isinstance(v, str):
        s = v.replace(root, "").replace(home, "~/")
        if pdk_form:
            s = s.replace(pdk_root + "/", pdk_form + "/").replace(pdk_root, pdk_form)
        return s
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
