"""modload -- load a Python script as a module from a file path.

The experiment scripts and tests import each other by path (their directory
names contain hyphens, so they are not importable packages). The module is
registered in ``sys.modules`` under ``name`` before it executes, which some
importers rely on (dataclasses, pickling, later ``sys.modules[name]`` lookups).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_module(path: str | Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name!r} from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
