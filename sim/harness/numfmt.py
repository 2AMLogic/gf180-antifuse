"""Shared number parsing and formatting for the sim scripts.

One SPICE-literal parser, one netlist-text float formatter, one
placeholder-tolerant record formatter, one relative-tolerance comparator, and
one SPICE logical-line joiner, so a change to rounding, the suffix table, or
the continuation rules is a single edit.  ``sci`` keeps the rendered
placeholder per caller (parameterized, not normalized): committed ``records/``
text is write-once evidence and must re-render byte-identically.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

# SPICE scale factors, lower-cased.  "meg" must win over "m" (milli), which the
# exact-key lookup below guarantees (the whole suffix is the key, never a prefix).
SUFFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9}

_LITERAL = re.compile(r"([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)([a-z]*)")


def spice_num(token: str) -> float:
    """Parse a SPICE numeric literal with an optional scale suffix."""
    m = _LITERAL.fullmatch(token.strip().lower())
    if not m:
        raise ValueError(f"cannot parse SPICE numeric literal: {token!r}")
    mantissa, suffix = m.groups()
    value = float(mantissa)
    if suffix:
        if suffix not in SUFFIX:
            raise ValueError(f"unknown SPICE unit suffix {suffix!r} in {token!r}")
        value *= SUFFIX[suffix]
    return value


def close(a: float, b: float) -> bool:
    """Equal within a 1e-9 relative tolerance (1e-30 floor so exact zero works)."""
    return abs(a - b) <= 1e-9 * max(abs(a), abs(b), 1e-30)


def logical_lines(text: str) -> list[str]:
    """SPICE logical lines of ``text``: ``+`` continuations joined onto their
    line, blank lines and ``*`` comments dropped, everything else (including
    ``.`` directives) kept stripped."""
    out: list[str] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("*"):
            continue
        if s.startswith("+") and out:
            out[-1] += " " + s[1:].strip()
        else:
            out.append(s)
    return out


def fmt(x: float) -> str:
    """Float as written into generated netlists / requests."""
    return f"{x:.6e}"


def sci(x, placeholder: str = "n/a", digits: int = 4, nan_placeholder: bool = False) -> str:
    """``x`` in scientific notation, or ``placeholder`` for None (and NaN if asked)."""
    if x is None or (nan_placeholder and isinstance(x, float) and math.isnan(x)):
        return placeholder
    return f"{x:.{digits}e}"


def parse_defaults(text: str, raw: bool = False) -> dict:
    """``name=value`` parameter defaults off the first ``.subckt`` line of cell
    netlist ``text``: floats, or the literal tokens as written if ``raw``."""
    line = next(l for l in text.splitlines() if l.startswith(".subckt"))
    return {k: v if raw else spice_num(v)
            for k, v in re.findall(r"(\w+)=([0-9.eE+-]+[a-zA-Z]*)", line)}


def parse_scalar(text: str, name: str) -> float | None:
    """``name = <float>`` scalar off an ngspice ``.measure`` log ``text``;
    None when the line is absent or the value is not a float."""
    m = re.search(rf"^\s*{re.escape(name)}\s*=\s*([0-9eE.+-]+)\s*$", text, re.MULTILINE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def cell_defaults(netlist: Path) -> dict[str, float]:
    """``name=value`` parameter defaults off the ``.subckt`` line of a committed
    cell netlist (read, not hand-copied)."""
    return parse_defaults(Path(netlist).read_text())
