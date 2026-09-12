"""Resolve the gf180mcu PDK install this machine actually has.

Mirrors gf180-bandgap's ``sim/harness/pdk.py`` resolution order, trimmed to
what this repo's testbenches need: ``sm141064.ngspice`` (all three cell
candidates' capacitors and Candidates 1/3's access devices),
``smbb000149.ngspice`` (Candidate 2's ``nfet_10v0_asym``), and
``design.ngspice`` (global corner-switch defaults every model file depends
on). No package other than the stdlib is used.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class PDKNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True)
class PDKPaths:
    pdk_root: Path          # the *search root* (e.g. ~/.volare)
    variant: str            # e.g. "gf180mcuD"
    variant_dir: Path       # pdk_root-resolved variant directory
    design_ngspice: Path
    sm141064: Path
    smbb000149: Path
    revision: str           # open_pdks commit hash, resolved from the
                             # variant symlink's target path when possible


def _variant_dir_from_root(root: Path, variant: str) -> Path:
    return root / variant


def _resolve_revision(variant_dir: Path) -> str:
    """Best-effort open_pdks revision string for this variant.

    volare lays out installs as
    ``<root>/volare/<family>/versions/<hash>/<variant>``, symlinked from
    ``<root>/<variant>``. Walk the resolved path looking for a
    ``versions/<hash>`` segment; fall back to "unknown" rather than
    fabricating a value if that layout is not what is on disk (e.g. a
    hand-built PDK_ROOT).
    """
    try:
        resolved = variant_dir.resolve()
    except OSError:
        return "unknown"
    parts = resolved.parts
    for i, part in enumerate(parts):
        if part == "versions" and i + 1 < len(parts):
            return parts[i + 1]
    return "unknown"


def resolve_pdk(pdk_root_override: str | None = None) -> PDKPaths:
    """Resolve the PDK, in order:

    1. ``GF180_PDK_PATH`` -- the variant directory itself.
    2. ``pdk_root_override`` (``--pdk-root`` CLI flag).
    3. ``PDK_ROOT`` (+ ``PDK``, default ``gf180mcuD``) -- the open_pdks /
       OpenLane convention.
    4. ``~/.volare`` (the built-in default this repo's other scripts, e.g.
       ``design/check-netlists.sh``, already assume).
    """
    variant = os.environ.get("PDK", "gf180mcuD")

    env_variant_path = os.environ.get("GF180_PDK_PATH")
    if env_variant_path:
        variant_dir = Path(env_variant_path).expanduser()
        pdk_root = variant_dir.parent
    else:
        root_str = pdk_root_override or os.environ.get("PDK_ROOT") or str(Path.home() / ".volare")
        pdk_root = Path(root_str).expanduser()
        variant_dir = _variant_dir_from_root(pdk_root, variant)

    ngspice_dir = variant_dir / "libs.tech" / "ngspice"
    design_ngspice = ngspice_dir / "design.ngspice"
    sm141064 = ngspice_dir / "sm141064.ngspice"
    smbb000149 = ngspice_dir / "smbb000149.ngspice"

    missing = [p for p in (design_ngspice, sm141064, smbb000149) if not p.is_file()]
    if missing:
        raise PDKNotFoundError(
            "gf180mcu PDK model files not found under "
            f"{ngspice_dir}. Missing: {', '.join(str(m) for m in missing)}. "
            "Set PDK_ROOT (or GF180_PDK_PATH) to a volare/open_pdks install, "
            "e.g. PDK_ROOT=$HOME/.volare (default) with `volare enable "
            "--pdk gf180mcu <hash>` already run. Verify what is actually "
            "installed with `klt pdk list`."
        )

    revision = _resolve_revision(variant_dir)

    return PDKPaths(
        pdk_root=pdk_root,
        variant=variant,
        variant_dir=variant_dir,
        design_ngspice=design_ngspice,
        sm141064=sm141064,
        smbb000149=smbb000149,
        revision=revision,
    )
