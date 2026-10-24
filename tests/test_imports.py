"""Every ``trajlib`` import in this repository must name a module that exists.

The modules import each other as ``from trajlib import timesync`` and
``from trajlib.camera import calibrate_camera``. A name that resolves to nothing is
not a style issue: the pipeline fails at startup. This check reads the import
statements instead of importing, so it needs neither OpenCV nor ffmpeg and runs
anywhere.

(Ported from TanitAD's ``test_trajrecon_imports.py``. There the package lives
under another name and needs a ``trajlib`` alias; here ``trajlib/`` is the real
package, so the alias tests are gone and only the resolution check is kept.)
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = ROOT / "trajlib"
SOURCES = sorted([*PKG.glob("*.py"), *ROOT.glob("*.py")])


def _trajlib_imports(path: pathlib.Path) -> set[str]:
    """Every submodule name this file pulls out of ``trajlib``, absolute or relative."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    in_pkg = path.parent == PKG
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level == 1 and in_pkg:            # from .camera import ...
                if mod:
                    found.add(mod.split(".")[0])
                else:                                 # from . import camera
                    found.update(a.name for a in node.names)
            elif mod == "trajlib":
                found.update(a.name for a in node.names)
            elif mod.startswith("trajlib."):
                found.add(mod.split(".")[1])
        elif isinstance(node, ast.Import):
            for a in node.names:
                parts = a.name.split(".")
                if parts[0] == "trajlib" and len(parts) > 1:
                    found.add(parts[1])
    return found


def test_the_sources_really_do_import_trajlib():
    """Guard the guard: if nothing imports ``trajlib``, every check below is vacuous."""
    total = set()
    for p in SOURCES:
        total |= _trajlib_imports(p)
    assert {"camera", "timesync", "attitude_track"} <= total


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_every_trajlib_import_names_a_module_that_exists(path: pathlib.Path):
    for name in sorted(_trajlib_imports(path)):
        assert (PKG / f"{name}.py").is_file(), (
            f"{path.relative_to(ROOT)} imports trajlib.{name}, "
            f"but trajlib/{name}.py does not exist")
