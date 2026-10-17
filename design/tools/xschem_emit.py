"""Shared xschem-source emission helpers for the design generators.

Used by design/gen_array.py (array / addressing stage) and
design/tools/gen_leg_schematics.py (program / read legs). Both used to carry
their own copy of this scaffolding and had started to drift (issue #110); the
PDK symbol geometry and the MOS attribute templates now live here once.

stdlib only. Importers must put this directory on sys.path explicitly:
design/regen-netlists.sh runs the generators under `python3 -I`, which does not
add the script's directory, so a plain `import xschem_emit` would fail there.

    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))   # gen_array.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))             # tools/*.py

Nothing in here is circuit content: it holds the xschem file syntax, the PDK
device-symbol pin offsets and the instance-attribute templates. What gets
instantiated, and with which nets and sizes, stays in each generator.
"""

from __future__ import annotations

import sys
from pathlib import Path

HEADER = "v {xschem version=3.4.7 file_version=1.2\n"

# Pin offsets (relative to the symbol origin, rot=0, flip=0), read out of the
# PDK symbols in libs.tech/xschem/symbols/. "n"/"p" is the device polarity;
# the pmos has D and S swapped.
MOS_PINS = {
    "n": {"D": (20, -30), "G": (-20, 0), "S": (20, 30), "B": (20, 0)},
    "p": {"S": (20, -30), "G": (-20, 0), "D": (20, 30), "B": (20, 0)},
}
RES_PINS = {"P": (0, -30), "M": (0, 30), "B": (-20, 0)}


def comment_block(lines: list[str]) -> str:
    return "\n" + "".join(f"* {ln}\n".replace("* \n", "*\n") for ln in lines)


def mos_attrs(kind: str, name: str, W: str, L: str) -> str:
    """Instance attribute block for a PDK MOS, following the symbol template
    (design/cells/*.sch do the same, substituting the W token into the area /
    perimeter expressions)."""
    if kind in ("nfet_03v3", "pfet_03v3", "nfet_06v0", "pfet_06v0"):
        return (
            f"name={name}\nL={L}\nW={W}\nnf=1\nm=1\n"
            f"ad=\"'int((nf+1)/2) * {W}/nf * 0.18u'\"\n"
            f"pd=\"'2*int((nf+1)/2) * ({W}/nf + 0.18u)'\"\n"
            f"as=\"'int((nf+2)/2) * {W}/nf * 0.18u'\"\n"
            f"ps=\"'2*int((nf+2)/2) * ({W}/nf + 0.18u)'\"\n"
            f"nrd=\"'0.18u / {W}'\" nrs=\"'0.18u / {W}'\"\n"
            f"sa=0 sb=0 sd=0\nmodel={kind}\nspiceprefix=X"
        )
    if kind == "nfet_10v0_asym":
        return (
            f"name={name}\nL={L}\nW={W}\nnf=1\nm=1\n"
            f"ad=\"'{W} * 1.48u'\"\npd=\"'2 * ({W} + 1.48u)'\"\n"
            f"as=\"'{W} * 0.48u'\"\nps=\"'2 * ({W} + 0.48u)'\"\n"
            f"nrd=0 nrs=0\nsa=0 sb=0 sd=0\nmodel={kind}\nspiceprefix=X"
        )
    if kind == "pfet_10v0_asym":
        return (
            f"name={name}\nL={L}\nW={W}\nnf=1\nm=1\n"
            f"ad=\"'{W} * 1.78u'\"\npd=\"'2 * ({W} + 1.78u)'\"\n"
            f"as=\"'{W} * 0.48u'\"\nps=\"'2 * ({W} + 0.48u)'\"\n"
            f"nrd=0 nrs=0\nsa=0 sb=0 sd=0\nmodel={kind}\nspiceprefix=X"
        )
    raise ValueError(kind)


class Sch:
    """Accumulates the body of one xschem schematic.

    flip_right_labels: flip a pin's net label when the pin sits to the right of
    the symbol origin, so the label text extends away from the symbol. The
    array generator leaves its labels unflipped.
    """

    def __init__(self, comment: list[str], flip_right_labels: bool = False):
        self.comment = comment
        self.flip_right_labels = flip_right_labels
        self.body: list[str] = []
        self.n = 0

    def _id(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}{self.n}"

    def lab(self, net: str, x: float, y: float, flip: bool = False) -> None:
        self.body.append(
            f"C {{devices/lab_pin.sym}} {x:g} {y:g} 0 {int(flip)} "
            f"{{name={self._id('l')} sig_type=std_logic lab={net}}}"
        )

    def port(self, kind: str, net: str, x: float, y: float) -> None:
        """kind: ipin / opin / iopin; rot 0 = pin text to the right of the point."""
        self.body.append(f"C {{devices/{kind}.sym}} {x:g} {y:g} 0 0 {{name={self._id('p')} lab={net}}}")

    def inst(self, sym: str, x: float, y: float, attrs: str) -> None:
        self.body.append(f"C {{{sym}}} {x:g} {y:g} 0 0 {{{attrs}}}")

    def text(self, s: str, x: float, y: float, size: float = 0.3) -> None:
        self.body.append(f"T {{{s}}} {x:g} {y:g} 0 0 {size} {size} {{}}")

    def pin_labels(self, x: float, y: float, pins: dict[str, tuple[float, float]],
                   nets: dict[str, str]) -> None:
        """A net label on each pin in `nets` (pin name -> net); `pins` maps pin
        name -> (dx, dy) offset from the symbol origin (x, y)."""
        for pin, net in nets.items():
            px, py = pins[pin]
            self.lab(net, x + px, y + py, flip=self.flip_right_labels and px > 0)

    def mos(self, kind: str, name: str, x: float, y: float, W: str, L: str,
            d: str, g: str, src: str, b: str) -> None:
        """Place a PDK MOS and a net label on each of its four pins."""
        self.inst(f"symbols/{kind}.sym", x, y, mos_attrs(kind, name, W, L))
        self.pin_labels(x, y, MOS_PINS["p" if kind.startswith("pfet") else "n"],
                        {"D": d, "G": g, "S": src, "B": b})

    def res(self, kind: str, name: str, x: float, y: float, W: str, L: str,
            p: str, m: str, b: str) -> None:
        """Place a PDK resistor and a net label on each of its pins."""
        self.inst(f"symbols/{kind}.sym", x, y,
                  f"name={name}\nW={W}\nL={L}\nmodel={kind}\nspiceprefix=X\nm=1")
        self.pin_labels(x, y, RES_PINS, {"P": p, "M": m, "B": b})

    def render(self) -> str:
        return (
            HEADER
            + comment_block(self.comment)
            + "}\nG {}\nK {}\nV {}\nS {}\nE {}\n"
            + "\n".join(self.body)
            + "\n"
        )


def sym_pin_offsets(pins_left: list[tuple[str, str]], pins_right: list[tuple[str, str]],
                    width: int = 160, pitch: int = 20) -> dict[str, tuple[float, float]]:
    """Pin name -> (x, y) offset of each pin of the rectangular symbol that
    sym_text() draws with the same arguments."""
    half_w = width // 2
    offs = {}
    for side, pins in ((-1, pins_left), (1, pins_right)):
        top = -((len(pins) - 1) * pitch) // 2
        for i, (nm, _dr) in enumerate(pins):
            offs[nm] = (side * half_w, top + i * pitch)
    return offs


def sym_text(pins_left: list[tuple[str, str]], pins_right: list[tuple[str, str]],
             fmt: str, template: str, comment: list[str], label: str,
             width: int = 160, pitch: int = 20) -> str:
    """Rectangular subcircuit symbol. Pins are (name, dir)."""
    rows = max(len(pins_left), len(pins_right))
    half_h = (rows * pitch) // 2 + 20
    half_w = width // 2
    offs = sym_pin_offsets(pins_left, pins_right, width, pitch)
    out = [HEADER + comment_block(comment) + "}", "G {}",
           f"K {{type=subcircuit\nformat=\"{fmt}\"\ntemplate=\"{template}\"\n}}",
           "V {}", "S {}", "E {}"]
    out.append(f"L 4 {-half_w + 20} {-half_h} {half_w - 20} {-half_h} {{}}")
    out.append(f"L 4 {-half_w + 20} {half_h} {half_w - 20} {half_h} {{}}")
    out.append(f"L 4 {-half_w + 20} {-half_h} {-half_w + 20} {half_h} {{}}")
    out.append(f"L 4 {half_w - 20} {-half_h} {half_w - 20} {half_h} {{}}")
    for side, pins in ((-1, pins_left), (1, pins_right)):
        for nm, dr in pins:
            x, y = offs[nm]
            out.append(f"L 4 {x} {y} {side * (half_w - 20)} {y} {{}}")
            out.append(f"B 5 {x - 2.5:g} {y - 2.5:g} {x + 2.5:g} {y + 2.5:g} {{name={nm} dir={dr}}}")
            tx = x + 4 if side < 0 else x - 4 - 7 * len(nm)
            out.append(f"T {{{nm}}} {tx:g} {y - 6:g} 0 0 0.2 0.2 {{}}")
    out.append(f"T {{@symname}} {-half_w + 28} {-half_h + 4} 0 0 0.3 0.3 {{}}")
    out.append(f"T {{@name}} {-half_w + 20} {-half_h - 14} 0 0 0.25 0.25 {{}}")
    out.append(f"T {{{label}}} {-half_w + 28} {half_h - 14} 0 0 0.2 0.2 {{}}")
    return "\n".join(out) + "\n"


def write_or_check(outputs: dict[Path, str], repo_root: Path, check: bool, regen_hint: str) -> int:
    """Write every generated file, or (check=True) diff against the committed
    copies without writing. Returns the process exit status."""
    rc = 0
    for path, text in sorted(outputs.items()):
        rel = path.relative_to(repo_root)
        if check:
            if not path.exists():
                print(f"DRIFT: {rel} is missing", file=sys.stderr)
                rc = 1
            elif path.read_text() != text:
                print(f"DRIFT: {rel} differs from a fresh generation", file=sys.stderr)
                rc = 1
            else:
                print(f"ok: {rel} reproduces exactly")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(f"wrote: {rel}")
    if check and rc:
        print(f"\nGenerated sources are out of date. Run {regen_hint}.", file=sys.stderr)
    return rc
