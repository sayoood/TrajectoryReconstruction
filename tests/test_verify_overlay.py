"""verify_overlay must read a KNOWN yaw error and a KNOWN lane position back.

Synthetic frames: two painted lines 3.5 m apart drawn with a true camera, then
analysed with a camera that is (a) identical, (b) rotated by a known yaw, and a
trajectory that is (c) offset by a known amount inside the lane. A metric that
cannot recover what was put in is not evidence about a real recording.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from trajlib.camera import CameraModel

_T = pathlib.Path(__file__).resolve().parents[1] / "tools" / "verify_overlay.py"
_spec = importlib.util.spec_from_file_location("_verify_overlay", _T)
VO = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = VO
_spec.loader.exec_module(VO)

LANE = 3.5
ARGS = SimpleNamespace(near_visible_m=7.0, vehicle_width=1.9, straight_range_m=40.0, straight_deg=1.5)


def _cam(yaw_deg=0.0):
    f = 1300.0
    return CameraModel(width=1920, height=1080, fx=f, fy=f, cx=960.0, cy=540.0,
                       height_m=1.40, lateral_m=0.0, longitudinal_m=1.8,
                       yaw=np.deg2rad(yaw_deg), pitch=np.arctan2(470.0 - 540.0, f))


def _frame(cam_true):
    img = np.full((1080, 1920, 3), 90, np.uint8)
    xs = np.arange(cam_true.longitudinal_m + 6.0, 140.0, 0.25)
    for y in (LANE / 2, -LANE / 2):
        pts = np.stack([xs, np.full_like(xs, y), np.zeros_like(xs)], 1)
        uv, ok = cam_true.project(pts)
        uv = uv[ok & (uv[:, 1] < 1079)]
        cv2.polylines(img, [uv.astype(np.int32)], False, (235, 235, 235), 6, cv2.LINE_AA)
    return img


def _rec(y_offset=0.0):
    t = np.arange(-3.0, 5.01, 0.1)
    x = 20.0 * t
    return dict(frame=0, t_session_s=10.0, speed_ms=20.0, t=t.tolist(), x=x.tolist(),
                y=np.full_like(x, y_offset).tolist(), yaw=np.zeros_like(x).tolist())


def test_a_correct_drawing_reads_parallel_and_centred():
    cam = _cam()
    r = VO.analyse_frame(_frame(cam), cam, _rec(), ARGS)
    assert r["angle_deg"] == pytest.approx(0.0, abs=0.15)
    assert r["offset_frac_10m"] == pytest.approx(0.0, abs=0.02)
    assert r["offset_frac_25m"] == pytest.approx(0.0, abs=0.02)
    assert r["lane_width_m_10m"] == pytest.approx(LANE, rel=0.05)
    assert r["centre_inside_30m"] and r["edges_inside_30m"]


@pytest.mark.parametrize("err", [1.0, -1.5])
def test_a_yaw_error_reads_as_that_angle(err):
    img = _frame(_cam())
    r = VO.analyse_frame(img, _cam(err), _rec(), ARGS)
    # a drawing camera yawed by `err` reads as a path-vs-lane angle of `err`
    assert r["angle_deg"] == pytest.approx(err, abs=0.2)
    # and the offset GROWS with range: a rotation, not a position
    assert abs(r["offset_frac_25m"]) > abs(r["offset_frac_10m"])


def test_a_car_off_centre_reads_as_a_constant_offset():
    cam = _cam()
    r = VO.analyse_frame(_frame(cam), cam, _rec(y_offset=0.5), ARGS)   # 0.5 m LEFT
    want = -0.5 / LANE                                                   # + is right
    assert r["offset_frac_10m"] == pytest.approx(want, abs=0.02)
    assert r["offset_frac_25m"] == pytest.approx(want, abs=0.02)
    assert r["angle_deg"] == pytest.approx(0.0, abs=0.15)


def test_no_paint_is_skipped_not_guessed():
    cam = _cam()
    r = VO.analyse_frame(np.full((1080, 1920, 3), 90, np.uint8), cam, _rec(), ARGS)
    assert "angle_deg" not in r


def test_a_bend_is_flagged_not_scored():
    cam = _cam()
    rec = _rec()
    t = np.asarray(rec["t"])
    rec["yaw"] = np.where(t > 0, 0.02 * t, 0.0).tolist()      # ~5 deg over 2 s ahead
    r = VO.analyse_frame(_frame(cam), cam, rec, ARGS)
    assert r["straight"] is False


def test_a_half_size_frame_reads_like_the_full_one():
    cam = _cam()
    img = cv2.resize(_frame(cam), (960, 540), interpolation=cv2.INTER_AREA)
    r = VO.analyse_frame(img, VO.scaled_camera(cam, 0.5), _rec(y_offset=0.5), ARGS)
    assert r["offset_frac_10m"] == pytest.approx(-0.5 / LANE, abs=0.03)
    assert r["angle_deg"] == pytest.approx(0.0, abs=0.3)
