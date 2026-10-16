"""Flatten the committed derived netlists (design/netlists/*.spice) to leaf devices.

stdlib only. The integrated bench probes device terminals by their flattened
ngspice node names, so the probe list is DERIVED from the committed netlists
instead of being typed out: a design change that renames or adds a device
changes the probe list with it.

ngspice flattening convention reproduced here (lower-case throughout):
  * a subcircuit instance ``Xa`` inside instance path ``x_dut`` has the path
    ``x_dut.xa``;
  * a subcircuit port resolves to the net the parent connected to it;
  * any other (internal) node ``n`` of an instance at path ``p`` is ``p.n``;
  * node ``0`` is global ground and stays ``0``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

NETLISTS = Path(__file__).resolve().parents[2] / "design" / "netlists"


@dataclass(frozen=True)
class Leaf:
    path: str          # flattened instance path, e.g. x_dut.xc_0_9.xm1
    model: str         # e.g. nfet_06v0, cap_nmos_03v3, ppolyf_u_2k_6p0
    nodes: tuple       # resolved node names, in the netlist's terminal order


def parse(files: list[str]) -> dict:
    """name -> {"ports": [...], "insts": [(inst, nodes, model)]} for every .subckt in the files."""
    subs: dict = {}
    for f in files:
        cur = None
        for raw in (NETLISTS / f"{f}.spice").read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("*"):
                continue
            tok = line.split()
            if tok[0].lower() == ".subckt":
                ports = [t.lower() for t in tok[2:] if "=" not in t]
                cur = subs.setdefault(tok[1].lower(), {"ports": ports, "insts": []})
            elif tok[0].lower() == ".ends":
                cur = None
            elif cur is not None and tok[0][0].lower() == "x":
                head = [t for t in tok[1:] if "=" not in t]   # nodes..., model
                # parameters start at the first token with '='; everything before it is nodes + model
                cut = next((i for i, t in enumerate(tok[1:]) if "=" in t), len(tok) - 1)
                head = tok[1:1 + cut]
                cur["insts"].append((tok[0].lower(), [h.lower() for h in head[:-1]], head[-1].lower()))
    return subs


def flatten(subs: dict, top: str, path: str, port_nets: list[str]) -> list[Leaf]:
    """Leaf devices of subcircuit `top` instantiated at `path` with `port_nets` on its ports."""
    sub = subs[top]
    netmap = dict(zip(sub["ports"], port_nets))

    def net(n: str) -> str:
        if n == "0":
            return "0"
        return netmap.get(n, f"{path}.{n}")

    out: list[Leaf] = []
    for inst, nodes, model in sub["insts"]:
        res = [net(n) for n in nodes]
        if model in subs:
            out += flatten(subs, model, f"{path}.{inst}", res)
        else:
            out.append(Leaf(f"{path}.{inst}", model, tuple(res)))
    return out


MOS = re.compile(r"^[np]fet_")
CAP = re.compile(r"^cap_[np]mos_")
RES = re.compile(r"^ppolyf_")


def kind(model: str) -> str:
    return "mos" if MOS.match(model) else "cap" if CAP.match(model) else "res" if RES.match(model) else "other"
