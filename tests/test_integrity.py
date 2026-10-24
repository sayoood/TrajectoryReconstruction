"""Source-integrity guard: no control bytes, valid UTF-8.

Why: during the 2026-08-08 copy into TanitAD, ``trajlib/vp_calib.py`` arrived with
a run of binary noise (``\\x02\\x8fOOOOO...``) of the SAME LENGTH as the text it
replaced. The byte count still matched, so a size check passed. A check for control
bytes and invalid UTF-8 is what catches that failure mode. It is not a checksum
against the originals -- the first commit of this repository is the reference for
that.

(Ported from TanitAD's ``test_trajrecon_integrity.py``; the checks tied to that
repo's lazy package import are left out.)
"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = ROOT / "trajlib"

# Tab, LF, CR are the only control bytes legitimately present in these sources.
_ALLOWED_CONTROL = {0x09, 0x0A, 0x0D}

SOURCES = sorted([*PKG.glob("*.py"), *ROOT.glob("*.py"), *ROOT.glob("*.md")])


def test_sources_are_populated() -> None:
    """Guard the guard: an empty glob would make every check below vacuous."""
    assert len(list(PKG.glob("*.py"))) >= 20


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_source_has_no_control_bytes(path: pathlib.Path) -> None:
    raw = path.read_bytes()
    bad = {b for b in raw if b < 0x20 and b not in _ALLOWED_CONTROL} | {b for b in raw if b == 0x7F}
    assert not bad, (
        f"{path.name} contains control bytes {sorted(hex(b) for b in bad)} -- the "
        f"corruption signature that a byte count misses")


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_source_is_valid_utf8(path: pathlib.Path) -> None:
    path.read_bytes().decode("utf-8")   # raises UnicodeDecodeError on binary noise


def test_geodetic_transform_is_numerically_sane() -> None:
    """A behavioural check on copied code, not just a syntactic one.

    0.0008993 deg of latitude is ~100 m north; the ENU 'up' component must show
    the small negative earth-curvature term rather than zero or a large value.
    """
    from trajlib.geo import LocalENU, wrap_pi

    enu = LocalENU(48.8566, 2.3522, 0.0)
    e, n, u = enu.forward(48.8566 + 0.0008993, 2.3522)[0]

    assert abs(e) < 0.01, e
    assert 99.0 < n < 101.0, n
    assert -0.01 < u < 0.0, f"expected a small negative curvature term, got {u}"

    # wrap_pi maps to [-pi, pi) (wrap_pi(pi) == -pi), although geo.py's docstring
    # says (-pi, pi]; both are the same angle, so assert on magnitude.
    pi = 3.141592653589793
    assert abs(abs(float(wrap_pi(3.0 * pi))) - pi) < 1e-9
    assert abs(float(wrap_pi(0.5)) - 0.5) < 1e-12
