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


def facade_hooks(namespace: dict, *sources: ModuleType):
    """Build the module ``__getattr__`` / ``__dir__`` pair for a facade runner.

    ``namespace`` is the runner's own ``globals()`` (live, so names defined
    after the call are seen by ``dir()`` and the reported module name is the
    caller's). ``sources`` are searched in order (model first, renderer
    second) on every lookup -- never snapshotted -- so state the library
    mutates in place stays visible through the facade. ``dir()`` does not
    consult ``__getattr__``, hence the pair: it advertises the runner's local
    names plus the public names of every source.

    Usage in a runner: ``__getattr__, __dir__ = facade_hooks(globals(), M, RENDER)``
    """

    def __getattr__(name: str):
        for src in sources:
            try:
                return getattr(src, name)
            except AttributeError:
                continue
        raise AttributeError(f"module {namespace['__name__']!r} has no attribute {name!r}")

    def __dir__() -> list[str]:
        public = {n for src in sources for n in dir(src) if not n.startswith("_")}
        return sorted(set(namespace) | public)

    return __getattr__, __dir__
