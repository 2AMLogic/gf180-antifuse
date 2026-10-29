"""Shared plumbing for scripts that generate tables spliced into a docs/ note.

A generated block in a note looks like

    <!-- gen:NAME -->
    ...table...
    <!-- /gen:NAME -->

Used by breakdown_oxide_model.py and breakdown_filament_model.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def table(head: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def block_re(name: str) -> re.Pattern:
    return re.compile(rf"(<!-- gen:{name} -->\n)(.*?)(\n<!-- /gen:{name} -->)", re.S)


def check(gen: dict[str, str], note: Path) -> list[str]:
    text = note.read_text()
    bad = []
    for k, v in gen.items():
        m = block_re(k).search(text)
        if not m:
            bad.append(f"{k}: block missing")
        elif m.group(2) != v:
            bad.append(f"{k}: differs from script output")
    return bad


def update(gen: dict[str, str], note: Path) -> None:
    text = note.read_text()
    for k, v in gen.items():
        text, n = block_re(k).subn(lambda m: m.group(1) + v + m.group(3), text)
        if n != 1:
            sys.exit(f"{note}: block {k} not found exactly once")
    note.write_text(text)


def main(gen: dict[str, str], note: Path, argv: list[str]) -> int:
    """Shared CLI: no flag prints every block, --check compares, --update rewrites the note."""
    if "--check" in argv:
        bad = check(gen, note)
        for b in bad:
            print("FAIL", b)
        return 1 if bad else 0
    if "--update" in argv:
        update(gen, note)
        return 0
    for k, v in gen.items():
        print(f"<!-- gen:{k} -->\n{v}\n<!-- /gen:{k} -->\n")
    return 0
