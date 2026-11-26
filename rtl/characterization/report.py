#!/usr/bin/env python3
"""Rebuild the routed digital characterization report and file-bound item-8 evidence."""

import argparse
import hashlib
import json
import math
import re
import sys

from replay_sdf import ROOT, TOP, NOMINAL, STRESS, SDF_INPUTS, digest, read

PNR = f"rtl/pnr/{TOP}.pnr.report.json"
STA = f"rtl/sta/{TOP}.sta.report.json"
FV = "verification/cocotb/report_digital_top.json"
SDF = "verification/cocotb/report_digital_top_sdf.json"
CAMPAIGN = "rtl/characterization/sdf-campaign.json"
REPORT = "rtl/characterization/REPORT.md"
ENVELOPE = "signoff/attestations/item-8-digital.json"
ROWS = {
    "Reset and idle outputs": ["reset_values_and_idle_outputs"],
    "SPI mode 0, MISO isolation and complete-frame writes": [
        "miso_enable_follows_cs",
        "bad_frame_length_sets_protocol_error",
        "truncated_and_overlong_writes_do_not_commit",
        "overlong_fire_frame_never_pulses",
    ],
    "ADDR_ROW, ADDR_COL and PULSE_WIDTH register access": [
        "row_col_pw_read_write",
        "out_of_range_row_col_rejected",
    ],
    "CTRL, STATUS, read-only and unknown register behavior": [
        "ctrl_arm_disarm_and_reserved",
        "read_only_and_unknown_addresses",
        "status_read_clears_protocol_error",
    ],
    "Arm and FIRE interlock, timeout and busy exclusion": [
        "program_full_sequence",
        "arm_timeout_expires",
        "arm_timeout_boundary",
        "fire_unarmed_rejected",
        "fire_with_other_command_bytes_never_pulses",
        "fire_while_busy_rejected",
        "read_while_armed_rejected",
    ],
    "Program pulse width, read settling and RDATA": [
        "pulse_width_cycle_counts",
        "read_settle_cycle_count_and_data",
    ],
    "One-hot row/column selects over all 32 indices": [
        "onehot_idle_while_sel_changes",
        "decoder_onehot_all_indices",
    ],
}
OMITTED_PATHS = {"iopath_cond_expression": 1070, "iopath_ifnone_edge_modpath": 144}
ASYNC = ["u_regs/_730_/D", "u_regs/_733_/D", "u_regs/_736_/D", "u_regs/_738_/D"]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def names(rows, key):
    values = [r[key] for r in rows]
    require(len(values) == len(set(values)), f"duplicate {key}")
    return values


def check_inputs(campaign):
    require(set(campaign["source_sha256"]) == set(SDF_INPUTS), "incomplete campaign input list")
    for path, expected in campaign["source_sha256"].items():
        require(digest(ROOT / path) == expected, f"campaign source hash mismatch: {path}")
    for path in (
        "rtl/sta/inputs.sha256",
        "verification/cocotb/inputs_digital_top.sha256",
        "verification/cocotb/inputs_digital_top_sdf.sha256",
    ):
        for line in (ROOT / path).read_text().splitlines():
            expected, name = line.split()
            require(digest(ROOT / name) == expected, f"source hash mismatch: {name}")


def measure(pnr, sta, request, zero, annotated, campaign):
    corners = request["pdk"]["corners"]
    require(len(corners) == len(set(corners)) == 15, "expected 15 distinct requested corners")
    require(set(names(pnr["corners"], "name")) == set(corners), "P&R corner set differs")
    require(set(names(sta["corners"], "corner")) == set(corners), "STA corner set differs")
    require(
        pnr["status"] == "ok"
        and pnr["stage_reached"] == "route"
        and sta["status"] == "ok"
        and sta["geometry_source"] == "routed",
        "missing completed routed implementation or STA",
    )
    require(
        pnr["provenance"]["input"]["content_hash"] == "sha256:" + digest(ROOT / pnr["netlist"]["path"]),
        "P&R netlist source mismatch",
    )
    require(
        sta["provenance"]["input"]["content_hash"] == "sha256:" + digest(ROOT / sta["def_path"]["path"]),
        "STA route input mismatch",
    )
    require(
        request["constraints"] == {"clock_port": "clk", "clock_period_ns": 50, "output_delay_ns": 0},
        "unexpected implementation timing constraints",
    )
    require(
        all(math.isfinite(pnr[k]) and pnr[k] > 0 for k in ("core_area_um2", "die_area_um2")), "invalid routed area"
    )
    for c in sta["corners"]:
        for metric in ("worst_slack_ns", "worst_hold_slack_ns", "estimated_power_mw", "fmax_mhz"):
            require(
                type(c[metric]) in (float, int) and math.isfinite(c[metric]), f"{c['corner']}: invalid {metric}"
            )
        require(c["estimated_power_mw"] > 0 and c["fmax_mhz"] > 0, f"{c['corner']}: missing PPA measurement")
        require(
            c["timing_status"] == "constrained"
            and c["setup_violation_count"] == c["hold_violation_count"] == 0
            and min(c["worst_slack_ns"], c["worst_hold_slack_ns"]) >= 0,
            f"{c['corner']}: timing failed",
        )
        require(
            c["power_basis"]["activity_source"] == "engine_default"
            and c["power_basis"]["parasitics"] == "spef_annotated",
            f"{c['corner']}: power basis changed",
        )
        annotation = c["spef_annotation"]
        require(
            annotation["annotation_complete"]
            and annotation["design_nets_annotated"] == annotation["design_nets_total"] == 550
            and annotation["floating_driver_count"] == annotation["unannotated_driver_count"] == 7
            and annotation["partially_unannotated_driver_count"] == 0,
            f"{c['corner']}: SPEF coverage changed",
        )
        endpoints = c["constraint_completeness"]["unconstrained_endpoints"]
        require(
            endpoints["count"] == 4 and sorted(endpoints["sample"]) == ASYNC,
            f"{c['corner']}: CDC exceptions changed",
        )

    tests = {t for group in ROWS.values() for t in group}
    for report in (zero, annotated):
        require(
            report["status"] == "pass"
            and set(names(report["tests"], "name")) == tests
            and report["test_count"] == report["passed_count"] == len(tests)
            and report["failed_count"] == report["skipped_count"] == 0
            and all(t["status"] == "passed" for t in report["tests"]),
            "nominal functional envelope has a missing, skipped or failed required test",
        )
    require(
        not zero["environment"]["sdf"] and annotated["environment"]["sdf"]["annotated"],
        "functional check modes differ",
    )
    nominal_digest = annotated["provenance"]["sdf_sha256"].removeprefix("sha256:")
    require(
        {k: v["count"] for k, v in annotated["environment"]["sdf"]["dropped"].items()}
        == {**OMITTED_PATHS, "timingcheck": 95},
        "nominal SDF scope changed",
    )
    require(
        annotated["environment"]["sdf"]["partial"]
        and annotated["environment"]["env"]["ANTIFUSE_GATE_CLOCK_NS"] == "50",
        "nominal timing annotation or cadence changed",
    )
    runs = {}
    for r in campaign["runs"]:
        key = r["corner"], r["sequencer_period_ns"]
        require(key not in runs, f"duplicate functional condition: {key}")
        runs[key] = r
        require(
            re.fullmatch(r"[0-9a-f]{64}", r["sdf_sha256"])
            and r["omitted_path_entries"] == OMITTED_PATHS
            and r["unsupported_timingcheck_sections"] == 96,
            f"{key}: invalid SDF record",
        )
        require(
            r["sources"] == annotated["environment"]["sources"]
            and r["source_content_hash"] == annotated["provenance"]["input"]["content_hash"],
            f"{key}: functional source mismatch",
        )
        require(set(r["outcomes"]) == tests, f"{key}: missing or unexpected test")
        if key == (STRESS[0], 25):
            require(
                r["status"] == "fail"
                and list(r["outcomes"].values()).count("failed") == 18
                and list(r["outcomes"].values()).count("passed") == 3,
                "slow 25 ns timing control changed",
            )
        else:
            require(
                r["status"] == "pass" and all(v == "passed" for v in r["outcomes"].values()),
                f"{key}: failed required test",
            )
    require(
        set(runs) == {(c, 50) for c in corners} | {(c, 25) for c in STRESS},
        "missing or unexpected functional corner",
    )
    require(len({runs[c, 50]["sdf_sha256"] for c in corners}) == 15, "corners share a delay file")
    require(runs[NOMINAL, 50]["sdf_sha256"] == nominal_digest, "nominal SDF digest mismatch")
    require(set(campaign["timing_file_sha256"]) == set(corners), "STA delay-file inventory is incomplete")
    for c in corners:
        require(
            campaign["timing_file_sha256"][c] == runs[c, 50]["sdf_sha256"],
            f"{c}: simulator loaded the wrong STA file",
        )
    for c in STRESS:
        require(runs[c, 25]["sdf_sha256"] == runs[c, 50]["sdf_sha256"], f"{c}: stress did not reuse the 50 ns SDF")
    return runs


def render():
    pnr, sta, zero, annotated, campaign = [read(ROOT / p) for p in (PNR, STA, FV, SDF, CAMPAIGN)]
    request = read(ROOT / f"rtl/sta/{TOP}.sta.json")
    check_inputs(campaign)
    runs = measure(pnr, sta, request, zero, annotated, campaign)
    lines = [
        "# Routed antifuse digital characterization",
        "",
        "The N=32 SPI register and row/column decoder macro passed all 21 port-level cases at each of 15 PVT corners at the 50 ns implementation clock. Area, Fmax and power are reported measurements or estimates with no ratified product limits. Power uses engine-default switching activity with routed SPEF parasitics.",
        "",
        f"The core occupies {pnr['core_area_um2']:,.1f} µm² inside a {pnr['die_area_um2']:,.1f} µm² die. SPEF annotation covered 550/550 design nets. Seven floating clock loads have no sinks. Four first-stage asynchronous endpoints are unconstrained: {', '.join(ASYNC)}. Setup and hold each had zero violations on constrained paths. The committed STA uses the {sta['clock_mode']} clock model.",
        "",
        "## Performance at the routed corners",
        "",
        "| Liberty corner | Fmax (MHz) | Power (mW) | Setup slack (ns) | Hold slack (ns) | Tests at 50 ns |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for c in sta["corners"]:
        passed = list(runs[c["corner"], 50]["outcomes"].values()).count("passed")
        lines.append(
            f"| {c['corner']} | {c['fmax_mhz']} | {c['estimated_power_mw']} | {c['worst_slack_ns']} | {c['worst_hold_slack_ns']} | {passed}/21 |"
        )
    lines += [
        "",
        "## Functional requirements",
        "",
        "The following named checks passed in the committed zero-delay and nominal SDF reports and in every 50 ns corner run. Their scope is the implemented digital port behavior in [architecture §5](../../spec/architecture.md#5-spi-slave-register-map) and its [implementation decision](../../spec/spi-register-implementation-decision.md).",
        "",
        "| Requirement | Port-level tests |",
        "|---|---|",
    ]
    lines += [f"| {label} | " + ", ".join(f"`{name}`" for name in group) + " |" for label, group in ROWS.items()]
    lines += [
        "",
        "## Timing coverage and controls",
        "",
        "Each PVT run used seed 1 and its own normalized SDF, including interconnect. Icarus applied partial typical-entry annotation and omitted 1,070 conditional IOPATH expressions, 144 IFNONE edge modifier paths and all 96 TIMINGCHECK sections present in each hashed SDF. The archived nominal envelope records 95 recognized timing-check warning lines. When cocotb and Icarus write to the transcript together, one warning can be split before the parser recognizes its prefix. The campaign counts the source-file sections independently. Functional results cover the represented arcs. At 25 ns with identical delay files, SS/+125 °C/1.62 V passed 3/21 and FF/−40 °C/5.50 V passed 21/21. Each passed 21/21 at 50 ns. The 25 ns trial is a timing sensitivity control.",
        "",
        "The [campaign](sdf-campaign.json) records every named test outcome, SDF digest, simulation source and route-source digest. [Implementation](../pnr/antifuse_digital_top.pnr.report.json), [STA](../sta/antifuse_digital_top.sta.report.json), [zero-delay](../../verification/cocotb/report_digital_top.json) and [nominal SDF](../../verification/cocotb/report_digital_top_sdf.json) are the original KLT reports.",
        "",
    ]
    lines += ["## Evidence inputs", "", "| Input | SHA-256 |", "|---|---|"]
    for path in sorted(
        set(SDF_INPUTS)
        | {
            FV,
            SDF,
            CAMPAIGN,
            PNR,
            STA,
            f"rtl/pnr/{TOP}.pnr.json",
            "spec/architecture.md",
            "spec/spi-register-implementation-decision.md",
        }
    ):
        lines.append(f"| `{path}` | `{digest(ROOT / path)}` |")
    lines += [
        "",
        "## Reproduction",
        "",
        "From the repository root:",
        "",
        "```sh",
        "python3 rtl/characterization/report.py",
        "./signoff/verify.sh",
        "```",
        "",
        "The second command uses klayout-tools 0.8.0. The full timing replay uses the toolchain described in [the routed RTL instructions](../README.md#post-route-simulation-with-sdf-timing), including KLT commit `6bd18bbc8637f6d767b3c24e77bd5db7a39e4bbe`, OpenROAD, Icarus 13.0, cocotb 2.0.1 and GF180D open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`. Run it in a checkout where the generated STA directory may be updated.",
        "",
        "```sh",
        'python3 rtl/characterization/replay_sdf.py --klt "$SDF_KLT" --pdk-root "$PDK_ROOT" --output /tmp/antifuse-sdf-campaign.json',
        "cmp rtl/characterization/sdf-campaign.json /tmp/antifuse-sdf-campaign.json",
        "```",
        "",
    ]
    markdown = "\n".join(lines)
    envelope = {
        "schema_version": 1,
        "kind": "generic",
        "t1_item": 8,
        "status": "pass",
        "summary": "Routed digital characterization across 15 PVT corners, including Fmax, area, power and SPI functional outcomes.",
        "source": REPORT,
        "provenance": {
            "input": {
                "path": {"path": REPORT, "scope": "repo"},
                "content_hash": "sha256:" + hashlib.sha256(markdown.encode()).hexdigest(),
            }
        },
    }
    return {REPORT: markdown, ENVELOPE: json.dumps(envelope, indent=2) + "\n"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for p, output in render().items():
        if args.write:
            (ROOT / p).write_text(output)
        else:
            require(
                (ROOT / p).read_text() == output,
                f"stale {p}; rerun with --write after verifying the source evidence",
            )
    print("Routed digital characterization verified: 15 PVT corners, 315/315 tests and paired 25 ns controls.")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, TypeError, ValueError) as error:
        sys.exit(str(error))
