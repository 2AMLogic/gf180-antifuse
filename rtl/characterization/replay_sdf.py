#!/usr/bin/env python3
"""Regenerate the 15-corner routed SDF campaign and two same-file period controls."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STA = ROOT / "rtl/sta"
COCOTB = ROOT / "verification/cocotb"
TOP = "antifuse_digital_top"
NOMINAL = "tt_025C_1v80"
STRESS = ("ss_125C_1v62", "ff_n40C_5v50")
SDF_INPUTS = (
    "rtl/pnr/antifuse_digital_top.gds",
    "rtl/pnr/antifuse_digital_top.def",
    "rtl/pnr/antifuse_digital_top_routed.v",
    "rtl/sta/antifuse_digital_top.spef",
    "rtl/sta/antifuse_digital_top.sta.json",
    "rtl/sta/antifuse_digital_top.sdf.json",
    "verification/cocotb/request_digital_top_sdf.json",
    "verification/cocotb/test_antifuse_digital_top.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


@contextmanager
def temporary_request(directory, request):
    with tempfile.NamedTemporaryFile(mode="w", dir=directory, suffix=".json", delete=False) as handle:
        path = Path(handle.name)
        json.dump(request, handle)
    try:
        yield path
    finally:
        path.unlink()


def observed(report, corner, period, sdf):
    """Keep measured fields, discarding local paths, elapsed wall times and simulator logs."""
    env = report["environment"]
    annotation = env["sdf"]
    if (
        env["random_seed"] != 1
        or report["hdl_toplevel"] != TOP
        or report["testbench"] != "test_antifuse_digital_top"
    ):
        raise ValueError(f"{corner}: unexpected circuit, testbench or random seed")
    if not annotation["annotated"] or not annotation["partial"] or annotation["corner"] != "typ":
        raise ValueError(f"{corner}: unexpected SDF annotation scope")
    if env["env"]["ANTIFUSE_GATE_CLOCK_NS"] != str(period) or annotation["file"].split("/")[-1] != sdf.name:
        raise ValueError(f"{corner}: stimulus period or SDF filename mismatch")
    checksum = digest(sdf)
    if report["provenance"]["sdf_sha256"].removeprefix("sha256:") != checksum:
        raise ValueError(f"{corner}: annotation reports a different SDF digest")
    dropped = {key: entry["count"] for key, entry in annotation["dropped"].items()}
    warning_lines = dropped.pop("timingcheck")
    # Icarus lacks SDF timing-check support. A warning interleaved with cocotb output
    # can lose its prefix in the native transcript scanner. Count the actual sections
    # in the hash-verified OpenSTA file independently of transcript line framing.
    timing_sections = len(re.findall(rb"(?im)^[ \t]*\(TIMINGCHECK(?=[\s)])", sdf.read_bytes()))
    if not 0 < warning_lines <= timing_sections:
        raise ValueError(f"{corner}: invalid timing-check diagnostics for {timing_sections} SDF sections")
    rows = {test["name"]: test["status"] for test in report["tests"]}
    if len(rows) != report["test_count"] or len(report["tests"]) != report["test_count"]:
        raise ValueError(f"{corner}: inconsistent or duplicate test names")
    for key, status in (("passed_count", "passed"), ("failed_count", "failed"), ("skipped_count", "skipped")):
        if report[key] != list(rows.values()).count(status):
            raise ValueError(f"{corner}: wrong {key}")
    return {
        "corner": corner,
        "sequencer_period_ns": period,
        "sdf_sha256": checksum,
        "status": report["status"],
        "sources": env["sources"],
        "source_content_hash": report["provenance"]["input"]["content_hash"],
        "omitted_path_entries": dropped,
        "unsupported_timingcheck_sections": timing_sections,
        "outcomes": rows,
    }


def run_sdf(klt, pdk_root):
    def run(*args, expected=0):
        proc = subprocess.run(
            [klt, *map(str, args)],
            cwd=ROOT,
            env={**os.environ, "PDK_ROOT": str(pdk_root)},
            capture_output=True,
            text=True,
        )
        if proc.returncode != expected:
            raise RuntimeError(
                f"klt {args[0]} returned {proc.returncode}, expected {expected}: {proc.stderr[-1200:]}"
            )
        return json.loads(proc.stdout)

    corners = read(STA / f"{TOP}.sta.json")["pdk"]["corners"]
    request = read(STA / f"{TOP}.sdf.json")
    request["pdk"]["corners"] = corners
    with temporary_request(STA, request) as path:
        result = run("sta", path, "--pdk", "gf180mcuD", "--pdk-root", pdk_root, "--format", "json")
    if [row["corner"] for row in result["corners"]] != corners:
        raise ValueError("STA did not emit the requested corners in order")
    timing_files = {}
    for row in result["corners"]:
        corner = row["corner"]
        sdf = STA / ".klt" / "sta" / f"{TOP}.{corner}.sdf"
        output = row["sdf"]
        if output["path"] != str(sdf.relative_to(ROOT)) or output["content_hash"] != "sha256:" + digest(sdf):
            raise ValueError(f"{corner}: STA reports a different output path or file")
        # Only OpenSTA's changing DATE line is removed. All delay data stays untouched.
        sdf.write_bytes(
            b"".join(
                line for line in sdf.read_bytes().splitlines(keepends=True) if not line.startswith(b' (DATE "')
            )
        )
        timing_files[corner] = digest(sdf)

    def simulate(condition):
        corner, period = condition
        sdf = STA / ".klt" / "sta" / f"{TOP}.{corner}.sdf"
        spec = read(COCOTB / "request_digital_top_sdf.json")
        spec["env"]["ANTIFUSE_GATE_CLOCK_NS"] = str(period)
        spec["options"]["sdf"]["file"] = os.path.relpath(sdf, COCOTB)
        expected = 3 if period == 25 and corner == STRESS[0] else 0
        with temporary_request(COCOTB, spec) as path, tempfile.TemporaryDirectory() as scratch:
            r = run(
                "functional-verification",
                path,
                "--pdk-root",
                pdk_root,
                "-o",
                Path(scratch) / "run",
                "--format",
                "json",
                expected=expected,
            )
        return observed(r, corner, period, sdf)

    conditions = [(c, 50) for c in corners] + [(c, 25) for c in STRESS]
    with ThreadPoolExecutor(max_workers=3) as pool:
        runs = list(pool.map(simulate, conditions))
    return make_record(runs, timing_files)


def make_record(runs, timing_files):
    return {
        "source_sha256": {p: digest(ROOT / p) for p in SDF_INPUTS},
        "timing_file_sha256": dict(sorted(timing_files.items())),
        "runs": sorted(runs, key=lambda r: (-r["sequencer_period_ns"], r["corner"])),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--klt", default="klt")
    parser.add_argument("--pdk-root", required=True, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = run_sdf(args.klt, args.pdk_root.resolve())
    args.output.write_text(json.dumps(record, indent=2) + "\n")
