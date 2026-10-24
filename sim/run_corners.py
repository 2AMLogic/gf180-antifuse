#!/usr/bin/env python3
"""sim/run_corners.py -- the one cold-start entry point for every sim/
experiment in this repo.

    python3 sim/run_corners.py --list
    python3 sim/run_corners.py cell-device-characterization [-- <experiment args>]

stdlib only, no venv. Per sim/README.md, each experiment slug owns its own
`run_experiment.py` (imported here as a library; for
cell-device-characterization that is the klt campaign driver, which submits
to the batch fleet) rather than a single
generic corner-grid contract -- this dispatcher's job is discovery and a
single documented invocation, not re-implementing per-experiment logic.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parent

EXPERIMENTS = {
    "cell-device-characterization": SIM_DIR / "cell-device-characterization" / "klt" / "run_klt_campaign.py",
    "program-read-legs": SIM_DIR / "program-read-legs" / "run_experiment.py",
    "cell-breakdown-model": SIM_DIR / "cell-breakdown-model" / "run_experiment.py",
    "programming-yield": SIM_DIR / "programming-yield" / "run_experiment.py",
}


def load_experiment_main(slug: str):
    path = EXPERIMENTS[slug]
    mod_name = f"sim_experiment_{slug.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module.main


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="list known experiment slugs and exit")
    parser.add_argument("slug", nargs="?", help="experiment slug, e.g. cell-device-characterization")
    args, rest = parser.parse_known_args(argv)

    if args.list or not args.slug:
        print("Known experiments:")
        for slug in EXPERIMENTS:
            print(f"  {slug}")
        return 0 if args.list else 2

    if args.slug not in EXPERIMENTS:
        print(f"ERROR: unknown experiment slug {args.slug!r}. Known: {', '.join(EXPERIMENTS)}", file=sys.stderr)
        return 2

    experiment_main = load_experiment_main(args.slug)
    return experiment_main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
