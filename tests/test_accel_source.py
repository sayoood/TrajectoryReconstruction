"""Longitudinal accel source: tier 0 (rigid mount, fixed gravity, baro grade) must recover the
acceleration that an accel-led orientation estimate cancels, and the scoring must not be fooled
by vibration or by a correlated-but-attenuated channel."""
import numpy as np
import pandas as pd

from trajlib.accel_source import (longitudinal_acceleration, quat_rotate_inv, road_grade,
                                  score_against_gnss)
from trajlib.io_sensorlogger import Session


class IdentityFrame:
    """Phone axes == vehicle FLU axes."""
    def to_vehicle(self, v):
        return np.asarray(v, dtype=float)


def _quat_pitch(theta):
    # body->world rotation about the left (y) axis by theta; (w, x, y, z)
    return np.stack([np.cos(theta / 2), 0 * theta, np.sin(theta / 2), 0 * theta], axis=1)


def _session(grade=0.0, leak=0.87, seed=0):
    """Synthetic drive: accelerate/brake cycles, rigid mount, optional constant grade.

    The phone's Orientation tilts toward sustained acceleration by ``leak`` (an
    accel-led attitude filter), which is what cancels tier 1.
    """
    rng = np.random.default_rng(seed)
    g = 9.80665
    t = np.arange(0.0, 300.0, 0.01)
    a = 1.2 * np.sin(2 * np.pi * t / 20.0) + 0.6 * np.sin(2 * np.pi * t / 7.0)
    v = 15.0 + np.cumsum(a) * 0.01
    th = np.arctan(grade)
    # specific force in the vehicle frame (x fwd, z up): a + g*sin(grade) forward
    fx = a + g * np.sin(th) + rng.normal(0, 0.8, len(t))          # road vibration
    fz = g * np.cos(th) + rng.normal(0, 0.8, len(t))
    F = np.stack([fx, np.zeros_like(t), fz], axis=1)
    # accel-led attitude: apparent pitch absorbs `leak` of the forward accel
    q = _quat_pitch(-np.arctan(leak * a / g) - th)
    h = np.cumsum(v * np.sin(th)) * 0.01
    tg = np.arange(0.0, 300.0, 1.0)
    vg = np.interp(tg, t, v) + rng.normal(0, 0.05, len(tg))
    sensors = {
        "total_accel": pd.DataFrame({"seconds_elapsed": t, "x": F[:, 0], "y": F[:, 1], "z": F[:, 2]}),
        "orientation": pd.DataFrame({"seconds_elapsed": t, "qw": q[:, 0], "qx": q[:, 1],
                                     "qy": q[:, 2], "qz": q[:, 3]}),
        "gps": pd.DataFrame({"seconds_elapsed": tg, "speed": vg}),
        "barometer": pd.DataFrame({"seconds_elapsed": t[::4], "relativeAltitude": h[::4]}),
    }
    return Session(path="synthetic", epoch_ms=0, device="test", timezone_name="UTC",
                   sensors=sensors), t, a


def test_tier0_recovers_full_scale_acceleration():
    s, t, a = _session()
    src = longitudinal_acceleration(s, IdentityFrame(), t)
    assert src.tier == 0 and src.usable
    r, gain = score_against_gnss(src.a_fwd, t, s["gps"]["seconds_elapsed"].to_numpy(),
                                 s["gps"]["speed"].to_numpy())
    assert r > 0.9 and 0.85 < gain < 1.15


def test_legacy_mode_reproduces_the_cancellation():
    s, t, a = _session()
    src = longitudinal_acceleration(s, IdentityFrame(), t, mode="legacy")
    assert src.tier == 4 or src.quality < 0.5
    # the tier-1 channel itself: raw force minus orientation-based gravity
    F = s["total_accel"][["x", "y", "z"]].to_numpy()
    Q = s["orientation"][["qw", "qx", "qy", "qz"]].to_numpy()
    tier1 = (F - quat_rotate_inv(Q, np.array([0.0, 0.0, 9.80665])))[:, 0]
    r, gain = score_against_gnss(tier1, t, s["gps"]["seconds_elapsed"].to_numpy(),
                                 s["gps"]["speed"].to_numpy())
    assert gain < 0.3          # the orientation absorbed ~87 % of the acceleration


def test_grade_is_removed_from_the_forward_specific_force():
    s, t, a = _session(grade=0.06)
    gr = road_grade(s, t)
    assert abs(np.median(gr) - 0.06) < 0.01
    src = longitudinal_acceleration(s, IdentityFrame(), t, grade_source="baro")
    assert src.tier == 0
    # after grade removal and median-centring the input carries no constant offset
    assert abs(np.mean(src.a_fwd) - np.mean(a)) < 0.1


def test_attenuated_channel_is_rejected_on_gain():
    s, t, a = _session()
    s.sensors["total_accel"] = s["total_accel"].assign(x=s["total_accel"]["x"] * 0.3)
    src = longitudinal_acceleration(s, IdentityFrame(), t)
    assert not (src.tier == 0 and src.usable)


def test_interval_scoring_beats_point_sampling_on_vibration():
    s, t, a = _session()
    tg = s["gps"]["seconds_elapsed"].to_numpy(); vg = s["gps"]["speed"].to_numpy()
    noisy = a + np.random.default_rng(1).normal(0, 1.5, len(t))
    r_int, _ = score_against_gnss(noisy, t, tg, vg)
    r_pt = np.corrcoef(np.interp(tg, t, noisy), np.gradient(vg, tg))[0, 1]
    assert r_int > 0.9 > r_pt
