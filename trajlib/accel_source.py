"""Recover *true* longitudinal acceleration from whatever the phone exported.

Why this module exists
----------------------
Android's ``Accelerometer`` virtual sensor ("linear acceleration") is not the
raw accelerometer: it is the specific force minus a *continuously re-estimated*
gravity vector.  That estimator has a time constant of order a second, so any
acceleration sustained for longer than that leaks into the gravity estimate and
is subtracted away.  Measured on the 2025-08-11 session, integrating its forward
component over 75 s gives **-0.8 m/s** while the vehicle actually gained
**+7.8 m/s**, and its correlation with the GPS-derived acceleration is -0.06.
It carries road vibration and little else.

Feeding that to a fusion filter as the propagation input is worse than useless:
it injects noise while contributing no real longitudinal information.

Tiers, best first:

0.  ``TotalAcceleration`` (raw specific force) rotated into the *fixed* vehicle
    frame, with gravity treated as constant in that frame (road grade is left
    to the filter's bias state; a barometric correction exists but is opt-in,
    see ``grade_source``).  The phone is rigidly mounted,
    so gravity does not move in its frame except through road grade and body
    pitch -- no attitude estimate is needed, and none can leak.  MEASURED
    (2026-11-03 1000N, Galaxy S24 Ultra): this channel tracks GNSS dv/dt with
    r = 0.94 and gain 0.99 on 1 s averages, while tier 1 on the same data shows
    r = 0.27 and gain 0.12 -- the phone's ``Orientation`` tilts toward any
    sustained acceleration and, subtracted, cancels ~87 % of it.
1.  ``TotalAcceleration`` (raw specific force) with gravity removed via the
    ``Orientation`` quaternion.  The attitude comes from gyro-led fusion, so
    sustained horizontal acceleration does not corrupt it the way an
    accel-led gravity estimator is corrupted.
2.  ``TotalAcceleration`` minus the ``Gravity`` stream -- same caveat as the
    linear channel, but kept as a fallback.
3.  ``Accelerometer`` (linear) -- short-term dynamics only.
4.  Nothing usable: the input is set to zero and the process noise is raised so
    speed becomes a random walk driven entirely by GNSS.  With RTS smoothing
    over 1 Hz Doppler speed this is still a perfectly good estimate; it is
    simply honest about where the information comes from.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class AccelSource:
    a_fwd: np.ndarray        # forward acceleration on the caller's time grid (m/s^2)
    tier: int
    name: str
    quality: float           # |corr| against GPS-derived dv/dt, NaN if unavailable
    usable: bool

    def __str__(self):
        q = "n/a" if not np.isfinite(self.quality) else f"{self.quality:.3f}"
        return (f"AccelSource(tier={self.tier}, {self.name}, quality={q}, "
                f"usable={self.usable}, std={self.a_fwd.std():.3f} m/s^2)")


def quat_rotate_inv(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate world-frame ``v`` into the body frame given body->world ``q``.

    ``q`` is (n, 4) as (w, x, y, z); ``v`` is (3,) or (n, 3).
    """
    q = np.asarray(q, dtype=float)
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    v = np.broadcast_to(np.asarray(v, dtype=float), (len(q), 3))
    # body = R(q)^T world
    t = 2.0 * np.cross(np.stack([-x, -y, -z], axis=1), v)
    return v + w[:, None] * t + np.cross(np.stack([-x, -y, -z], axis=1), t)


def road_grade(session, t_grid: np.ndarray, smooth_s: float = 3.0,
               min_speed: float = 4.0, max_grade: float = 0.15) -> np.ndarray | None:
    """Road grade (rise over run, uphill positive) on ``t_grid`` from the barometer.

    grade = (dh/dt) / v with h the barometric relative altitude and v the GNSS
    speed, both low-passed over ``smooth_s``.  Below ``min_speed`` the ratio is
    ill-conditioned, so the last good value is held.  Returns None when there is
    no barometer or no GNSS speed.
    """
    if not (session.has("barometer") and session.has("gps")):
        return None
    b = session["barometer"]
    if "relativeAltitude" not in b.columns:
        return None
    tb = b["seconds_elapsed"].to_numpy(dtype=float)
    hb = b["relativeAltitude"].to_numpy(dtype=float)
    g = session["gps"]
    tv = g["seconds_elapsed"].to_numpy(dtype=float)
    vv = g["speed"].to_numpy(dtype=float) if "speed" in g.columns else None
    if vv is None:
        return None
    ok = np.isfinite(tb) & np.isfinite(hb)
    okv = np.isfinite(tv) & np.isfinite(vv)
    if ok.sum() < 20 or okv.sum() < 8:
        return None
    dt = float(np.median(np.diff(t_grid)))
    h = np.interp(t_grid, tb[ok], hb[ok])
    v = np.interp(t_grid, tv[okv], np.clip(vv[okv], 0.0, None))
    from scipy.ndimage import uniform_filter1d
    w = max(3, int(round(smooth_s / dt)))
    h = uniform_filter1d(uniform_filter1d(h, w, mode="nearest"), w, mode="nearest")
    v = uniform_filter1d(v, w, mode="nearest")
    dh = np.gradient(h, t_grid)
    grade = np.full(len(t_grid), np.nan)
    good = v >= min_speed
    grade[good] = np.clip(dh[good] / v[good], -max_grade, max_grade)
    # hold the last good value through slow stretches (and back-fill the start)
    idx = np.where(good, np.arange(len(t_grid)), -1)
    idx = np.maximum.accumulate(idx)
    first = np.argmax(good) if good.any() else 0
    idx[idx < 0] = first
    return np.nan_to_num(grade[idx]) if good.any() else np.zeros(len(t_grid))


def score_against_gnss(a: np.ndarray, t_grid: np.ndarray, tv: np.ndarray, vv: np.ndarray):
    """(signed r, gain) of ``a`` against GNSS speed differences.

    The comparison is made on the *mean* of ``a`` over each GNSS interval against
    (v[k+1]-v[k])/dt: both sides then describe the same thing.  Point-sampling a
    100 Hz accelerometer at 1 Hz instants instead compares road vibration with a
    finite difference and understates a good sensor.  Gain is the least-squares
    slope of the interval mean on dv/dt (1.0 = full scale).
    """
    ca = np.concatenate([[0.0], np.cumsum(0.5 * (a[1:] + a[:-1]) * np.diff(t_grid))])
    inside = (tv >= t_grid[0]) & (tv <= t_grid[-1])
    tv, vv = tv[inside], vv[inside]
    if len(tv) < 10:
        return np.nan, np.nan
    dtv = np.diff(tv)
    m = (dtv > 0.5) & (dtv < 2.0)
    if m.sum() < 8:
        return np.nan, np.nan
    am = (np.diff(np.interp(tv, t_grid, ca)) / np.where(dtv > 0, dtv, 1.0))[m]
    ref = (np.diff(vv) / np.where(dtv > 0, dtv, 1.0))[m]
    am = am - np.median(am)
    if np.std(am) < 1e-6 or np.std(ref) < 1e-6:
        return np.nan, np.nan
    # GNSS speed glitches (a 1 s jump of several m/s) are not acceleration, and a
    # handful of them decide a correlation.  MEASURED (St2392, night, receiver
    # speedAccuracy 0.81 m/s): 4 of 491 intervals took r from 0.77 to 0.57.
    # Reject on the residual of the joint fit (MAD), iterated.
    keep = np.ones(len(am), dtype=bool)
    for _ in range(3):
        if keep.sum() < 8:
            return np.nan, np.nan
        k = np.polyfit(ref[keep], am[keep], 1)[0]
        res = am - k * ref
        mad = 1.4826 * np.median(np.abs(res[keep] - np.median(res[keep]))) + 1e-9
        keep = np.abs(res - np.median(res[keep])) < 4.0 * mad
    am, ref = am[keep], ref[keep]
    r = float(np.corrcoef(am, ref)[0, 1])
    # Both sides are noisy (GNSS Doppler noise in ref, vibration residue in am),
    # so either one-sided slope is biased toward zero/infinity.  The geometric
    # mean of slope(am|ref) and 1/slope(ref|am) is the symmetric estimate.
    s1 = np.polyfit(ref, am, 1)[0]
    s2 = np.polyfit(am, ref, 1)[0]
    gain = float(np.sign(s1) * np.sqrt(abs(s1 / s2))) if s1 * s2 > 0 else float(s1)
    return r, gain


def longitudinal_acceleration(session, vframe, t_grid: np.ndarray,
                              g0: float = 9.80665,
                              min_quality: float = 0.15,
                              mode: str = "auto",
                              min_gain: float = 0.6, max_gain: float = 1.6,
                              grade_source: str = "none") -> AccelSource:
    """Best available forward acceleration, resampled onto ``t_grid``.

    ``mode``: ``"auto"`` (all tiers, interval-mean scoring with a gain check),
    ``"legacy"`` (tiers 1-3 with the original point-sampled scoring, the
    behaviour before tier 0 existed), ``"none"`` (always tier 4).
    """
    if mode == "none":
        return AccelSource(np.zeros(len(t_grid)), 4, "none (disabled by config)", np.nan, False)

    def resamp(df, cols):
        t = df["seconds_elapsed"].to_numpy(dtype=float)
        return np.stack([np.interp(t_grid, t, df[c].to_numpy(dtype=float)) for c in cols], axis=1)

    candidates = []

    if mode == "auto" and session.has("total_accel"):
        F = vframe.to_vehicle(resamp(session["total_accel"], "xyz"))
        fx = F[:, 0]
        # Barometric grade is OFF by default.  MEASURED (1000N, 8 x 10 s GNSS
        # outages): with it the channel's r against GNSS dv/dt fell from 0.94 to
        # 0.76 and one outage diverged to 153 m (speed driven to zero); without it
        # every outage stayed within 2.9 m.  Cabin pressure moves with speed and
        # ventilation, so dh/dt from the phone's barometer is not road climb.
        # Slow grade is left to the filter's accel-bias state.
        grade = road_grade(session, t_grid) if grade_source == "baro" else None
        name = "total_accel, rigid mount"
        if grade is not None:
            # specific force forward = a + g*sin(grade): uphill reads as forward accel
            fx = fx - g0 * np.sin(np.arctan(grade))
            name += " - g*grade(baro)"
        # The constant left is g*sin(residual mount pitch) plus the session's mean
        # acceleration (~0 over a drive).  Remove the median; the filter's b_a
        # state tracks what remains.
        fx = fx - np.median(fx)
        candidates.append((0, name, fx))

    if session.has("total_accel") and session.has("orientation"):
        F = resamp(session["total_accel"], "xyz")
        ori = session["orientation"]
        to = ori["seconds_elapsed"].to_numpy(dtype=float)
        Q = np.stack([np.interp(t_grid, to, ori[c].to_numpy(dtype=float))
                      for c in ("qw", "qx", "qy", "qz")], axis=1)
        Q /= np.linalg.norm(Q, axis=1, keepdims=True) + 1e-12
        g_body = quat_rotate_inv(Q, np.array([0.0, 0.0, g0]))   # world Z is up (ENU)
        candidates.append((1, "total_accel - R(q)^T*g", F - g_body))

    if session.has("total_accel") and session.has("gravity"):
        F = resamp(session["total_accel"], "xyz")
        G = resamp(session["gravity"], "xyz")
        candidates.append((2, "total_accel - gravity", F - G))

    if session.has("accel"):
        candidates.append((3, "accel (android linear)", resamp(session["accel"], "xyz")))

    # reference for scoring: GPS-derived longitudinal acceleration
    ref_t = ref_a = None
    if session.has("gps"):
        gps = session["gps"]
        tv = gps["seconds_elapsed"].to_numpy(dtype=float)
        vv = gps["speed"].to_numpy(dtype=float)
        fin = np.isfinite(tv) & np.isfinite(vv)
        if fin.sum() > 8 and (np.max(vv[fin]) - np.min(vv[fin])) > 1.0:
            tv, vv = tv[fin], vv[fin]
            ref_t, ref_a = tv, np.gradient(vv, tv)
            gps_v = vv

    best = None
    for tier, name, A in candidates:
        a_f = A if A.ndim == 1 else vframe.to_vehicle(A)[:, 0]
        qual, signed, gain = np.nan, np.nan, np.nan
        if ref_t is not None and mode == "auto":
            signed, gain = score_against_gnss(a_f, t_grid, ref_t, gps_v)
            qual = abs(signed) if np.isfinite(signed) else np.nan
            name = f"{name} [r={signed:+.2f}, gain={gain:.2f}]"
            # A strongly correlated channel at the wrong scale is not usable as a
            # propagation input: it would bias speed through every manoeuvre.
            if np.isfinite(gain) and signed > 0 and not (min_gain <= gain <= max_gain):
                qual = min(qual, min_quality - 1e-3)
        elif ref_t is not None:
            a_at = np.interp(ref_t, t_grid, a_f)
            if np.std(a_at) > 1e-6 and np.std(ref_a) > 1e-6:
                signed = float(np.corrcoef(a_at, ref_a)[0, 1])
                qual = abs(signed)
        # A *negative* correlation means the forward axis points backwards, so
        # the signal is good and the frame is wrong -- integrating it makes the
        # speed run the wrong way.  Reject rather than rectify: the frame should
        # be fixed upstream, and silently negating here would hide that.
        if np.isfinite(signed) and signed < -min_quality:
            name = f"{name} REVERSED (r={signed:+.2f}) - vehicle frame is wrong"
            qual = float(qual)
            cand = AccelSource(a_fwd=a_f, tier=tier, name=name, quality=qual, usable=False)
        else:
            # Unknown quality is *not* a licence to trust the stream.  Defaulting
            # unverifiable to usable is how a reversed accelerometer reached the
            # filter and turned a 3 m trajectory into a 77 m one.
            cand = AccelSource(a_fwd=a_f, tier=tier, name=name, quality=qual,
                               usable=bool(np.isfinite(qual) and qual >= min_quality))
        if best is None:
            best = cand
        # prefer a lower tier, but only if it is not demonstrably worse
        if np.isfinite(qual) and np.isfinite(best.quality) and qual > best.quality + 0.05:
            best = cand

    if best is None:
        return AccelSource(np.zeros(len(t_grid)), 4, "none", np.nan, False)

    if not best.usable:
        # Do not propagate on a signal that carries no longitudinal information.
        q = "unverifiable" if not np.isfinite(best.quality) else f"quality={best.quality:.2f}"
        return AccelSource(np.zeros(len(t_grid)), 4,
                           f"disabled ({best.name}, {q})", best.quality, False)
    return best
