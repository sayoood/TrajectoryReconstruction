#!/usr/bin/env python3
"""Does the drawn trajectory stay in the lane? Measured against the painted lines.

Runs on a finished pipeline output folder (``calibration.json``,
``trajectory.jsonl``, ``frames/``) and reports, per sampled frame:

* **path-vs-lane angle** -- both lane boundaries are fitted as whole image lines
  (top-hat + Hough, one line per side), they meet at the lane vanishing point, and
  the far half of the drawn ribbon is extended to that row. The column difference
  over ``fx`` is the angle between the drawn path and the lane. It needs no height
  and no metric scale, so it isolates the camera YAW.
* **offset from the lane centre**, as a fraction of the lane width, at camera
  ranges of 10 m and 25 m. A constant offset that is the same near and far is
  where the car was in its lane; one that grows with range is a rotation error.
* **prediction vs outcome** -- the ribbon's lane fraction at range X in frame F,
  against the ribbon's lane fraction at the near range in the later frame where
  the car has reached that patch of road. If the drawing is right the two agree
  whatever the driver did, including drifting across the lane. The difference is
  the drawing error at range X; it assumes only that the paint stays put.
* **containment** -- whether the ribbon centre stays between the two lines out to
  30 m. Real lane changes count against it, so read it with the two above.

Everything is summarised per time bin as well, because a pooled number hides a
failure that lasts a couple of seconds (``docs/CALIBRATION_RETRACTIONS.md``,
``R-2026-09-24-constantyaw``).

    python tools/verify_overlay.py --run <output>/<recording> --json verify.json
    python tools/verify_overlay.py --run ... --draw 900 1500 --draw-dir checks/

The lane fit needs two visible boundaries; frames without them are skipped and
counted, not guessed.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trajlib.attitude_track import camera_for_time, load_attitude_track  # noqa: E402
from trajlib.camera import CameraModel  # noqa: E402


def load_camera(cal: dict) -> CameraModel:
    k, e = cal["K"], cal["extrinsics"]
    return CameraModel(width=int(cal["image"]["width"]), height=int(cal["image"]["height"]),
                       fx=float(k["fx"]), fy=float(k["fy"]), cx=float(k["cx"]), cy=float(k["cy"]),
                       height_m=float(e["height_m"]), lateral_m=float(e["lateral_offset_m"]),
                       longitudinal_m=float(e["longitudinal_m"]),
                       yaw=np.deg2rad(float(e["yaw_deg"])), pitch=np.deg2rad(float(e["pitch_deg"])),
                       roll=np.deg2rad(float(e["roll_deg"])))


def ribbon_centre(cam: CameraModel, rec: dict, cam_ranges: np.ndarray):
    """Pixels of the drawn ribbon's centre line at the given CAMERA ranges (m)."""
    t = np.asarray(rec["t"], float)
    x = np.asarray(rec["x"], float)
    y = np.asarray(rec["y"], float)
    fut = t >= 0
    x, y = x[fut], y[fut]
    if x.size < 2 or x.max() - x.min() < 1.0:
        return None
    o = np.argsort(x)
    x, y = x[o], y[o]
    xv = cam_ranges + cam.longitudinal_m          # trajectory origin is the rear axle
    ok = xv <= x.max()
    if ok.sum() < 3:
        return None
    pts = np.stack([xv[ok], np.interp(xv[ok], x, y), np.zeros(ok.sum())], 1)
    uv, valid = cam.project(pts)
    keep = valid & np.isfinite(uv).all(1)
    if keep.sum() < 3:
        return None
    return cam_ranges[ok][keep], uv[keep]


def lane_lines(img, cam: CameraModel, rib_uv, v_lo, v_hi):
    """Left and right ego-lane boundaries as whole lines ``u = a + b*v``."""
    s = img.shape[1] / 1920.0
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    kw = max(9, int(round(31 * s)) | 1)
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (kw, 1)))
    _, bw = cv2.threshold(th, 40, 255, cv2.THRESH_BINARY)
    bw[:int(v_lo)] = 0
    bw[int(v_hi):] = 0
    segs = cv2.HoughLinesP(bw, 1, np.pi / 360, 40, minLineLength=int(35 * s), maxLineGap=int(25 * s))
    if segs is None:
        return None, None
    segs = segs.reshape(-1, 4)
    o = np.argsort(rib_uv[:, 1])
    cu, cv_ = rib_uv[o, 0], rib_uv[o, 1]

    def centre_at(v):
        return float(np.interp(v, cv_, cu))

    L, R = [], []
    for u1, v1, u2, v2 in segs.astype(float):
        if abs(v2 - v1) < 8 * s:
            continue
        b = (u2 - u1) / (v2 - v1)
        side_left = 0.5 * (u1 + u2) < centre_at(0.5 * (v1 + v2))
        if side_left and b < -0.2:
            L.append((u1, v1, u2, v2))
        elif not side_left and b > 0.2:
            R.append((u1, v1, u2, v2))
    # Pick the ego lane's boundary where lines are furthest apart: in the NEAR field.
    # Judged mid-band, a kerb or shoulder edge with a shallower slope can extend to
    # a column nearer the path than the lane line itself (seen on 2026-08-08 f932).
    vr = v_hi - 0.15 * (v_hi - v_lo)

    def fit(S, left):
        if len(S) < 2:
            return None
        ref = centre_at(vr)
        ext = [(seg, seg[0] + (vr - seg[1]) * (seg[2] - seg[0]) / (seg[3] - seg[1])) for seg in S]
        ext = [(seg, u) for seg, u in ext if (u < ref if left else u > ref)]
        if not ext:
            return None
        u0 = (max if left else min)(ext, key=lambda t: t[1])[1]   # nearest line on that side
        keep = [seg for seg, u in ext if abs(u - u0) < 45 * s]
        V, U, W = [], [], []
        for u1, v1, u2, v2 in keep:
            ln = np.hypot(u2 - u1, v2 - v1)
            V += [v1, v2]
            U += [u1, u2]
            W += [ln, ln]
        w = np.sqrt(np.asarray(W))
        A = np.stack([np.ones(len(V)), V], 1) * w[:, None]
        a, b = np.linalg.lstsq(A, np.asarray(U) * w, rcond=None)[0]
        return float(a), float(b), len(keep)

    return fit(L, True), fit(R, False)


def ground_row(cam: CameraModel, cam_range: float) -> float:
    uv, ok = cam.project(np.array([[cam_range + cam.longitudinal_m, cam.lateral_m, 0.0]]))
    return float(uv[0, 1]) if ok[0] else float("nan")


def analyse_frame(img, cam, rec, args):
    ranges = np.arange(6.0, 60.5, 0.5)
    rc = ribbon_centre(cam, rec, ranges)
    if rc is None:
        return None
    rng, uv = rc
    hz = cam.horizon_v()
    v_lo = hz + 25 * img.shape[1] / 1920.0
    v_hi = min(img.shape[0] - 2, ground_row(cam, args.near_visible_m))
    if not np.isfinite(v_hi) or v_hi - v_lo < 60:
        return None
    fl, fr = lane_lines(img, cam, uv, v_lo, v_hi)
    out = dict(frame=int(rec["frame"]), t=float(rec["t_session_s"]), speed=float(rec["speed_ms"]))
    # Whole-line lane fits and the path angle only mean something on a STRAIGHT road:
    # in a bend both lane lines are curves and a line fit through them is not the lane.
    tt, xx, yaw = (np.asarray(rec[k], float) for k in ("t", "x", "yaw"))
    fut = tt >= 0
    reach = fut & (xx <= cam.longitudinal_m + args.straight_range_m)
    turn = float(np.rad2deg(np.ptp(np.unwrap(yaw[reach])))) if reach.sum() >= 2 else float("nan")
    covered = bool(fut.any() and xx[fut].max() >= cam.longitudinal_m + args.straight_range_m)
    out["heading_change_deg"] = turn
    out["straight"] = bool(covered and np.isfinite(turn) and turn < args.straight_deg)
    if not (fl and fr):
        return out
    (al, bl, _), (ar, br, _) = fl, fr
    if abs(bl - br) < 1e-6:
        return out
    v_vp = (ar - al) / (bl - br)
    u_vp = al + bl * v_vp
    out.update(lane_vp_u=u_vp, lane_vp_v=v_vp, lines=[al, bl, ar, br])
    far = rng >= 15.0
    if far.sum() >= 3:
        k = np.polyfit(uv[far, 1], uv[far, 0], 1)
        out["angle_deg"] = float(np.rad2deg(np.arctan((np.polyval(k, v_vp) - u_vp) / cam.fx)))
    # lane fraction of the ribbon centre at every sampled range (0 = lane centre, +right)
    vv, uu = uv[:, 1], uv[:, 0]
    uL, uR = al + bl * vv, ar + br * vv
    width_px = uR - uL
    inside_band = (vv >= v_lo) & (vv <= v_hi) & (width_px > 4)
    frac = np.where(inside_band, (uu - 0.5 * (uL + uR)) / np.where(width_px > 0, width_px, np.nan), np.nan)
    # metric lane width at each row from the ground-plane scale h/(v - v_h)
    lane_m = np.where(inside_band, width_px * cam.height_m / np.maximum(vv - hz, 1e-6) * cam.fy / cam.fx, np.nan)
    out["frac_by_range"] = {f"{r:.1f}": (None if not np.isfinite(f) else round(float(f), 4))
                            for r, f in zip(rng, frac)}
    for r in (10.0, 25.0):
        i = np.argmin(np.abs(rng - r))
        if abs(rng[i] - r) < 0.26 and np.isfinite(frac[i]):
            out[f"offset_frac_{int(r)}m"] = float(frac[i])
            out[f"lane_width_m_{int(r)}m"] = float(lane_m[i])
    upto = (rng <= 30.0) & np.isfinite(frac)
    if upto.sum() >= 5:
        out["centre_inside_30m"] = bool(np.all(np.abs(frac[upto]) < 0.5))
        half_w = 0.5 * args.vehicle_width / np.nanmedian(lane_m[upto]) if np.isfinite(lane_m[upto]).any() else np.nan
        out["edges_inside_30m"] = bool(np.all(np.abs(frac[upto]) + half_w < 0.5)) if np.isfinite(half_w) else None
    return out


def draw(img, cam, rec, res, path):
    vis = img.copy()
    rc = ribbon_centre(cam, rec, np.arange(6.0, 60.5, 0.5))
    if rc is not None:
        cv2.polylines(vis, [rc[1].astype(np.int32)], False, (0, 140, 255), 3, cv2.LINE_AA)
    if res and "lines" in res:
        al, bl, ar, br = res["lines"]
        for a, b in ((al, bl), (ar, br)):
            v0, v1 = res["lane_vp_v"], img.shape[0] * 0.95
            cv2.line(vis, (int(a + b * v1), int(v1)), (int(a + b * v0), int(v0)), (255, 0, 255), 3, cv2.LINE_AA)
    cv2.rectangle(vis, (0, 0), (vis.shape[1], 70), (0, 0, 0), -1)
    txt = (f"frame {rec['frame']}  t={rec['t_session_s']:.2f}s  angle "
           f"{(res or {}).get('angle_deg', float('nan')):+.2f} deg  offset@10m "
           f"{(res or {}).get('offset_frac_10m', float('nan')):+.3f}  @25m "
           f"{(res or {}).get('offset_frac_25m', float('nan')):+.3f} lane widths")
    cv2.putText(vis, txt, (15, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.imwrite(str(path), vis)


def predict_vs_outcome(results, recs_by_frame, x_near, ranges):
    """Drawing error at range X: prediction in frame F vs outcome where the car got to."""
    rows = [r for r in results if r and "frac_by_range" in r]
    if len(rows) < 10:
        return {}
    frames = np.array([r["frame"] for r in rows])
    allf = sorted(recs_by_frame)
    t = np.array([recs_by_frame[f]["t_session_s"] for f in allf])
    v = np.array([recs_by_frame[f]["speed_ms"] for f in allf])
    s = np.concatenate([[0.0], np.cumsum(0.5 * (v[1:] + v[:-1]) * np.diff(t))])
    s_of = dict(zip(allf, s))
    sf = np.array([s_of[f] for f in frames])
    out = {}
    for X in ranges:
        errs, times = [], []
        for i, r in enumerate(rows):
            if not r.get("straight") or not (2.5 <= (r.get("lane_width_m_10m") or 0) <= 4.5):
                continue
            p = r["frac_by_range"].get(f"{X:.1f}")
            if p is None:
                continue
            target = sf[i] + (X - x_near)
            j = int(np.argmin(np.abs(sf - target)))
            if j <= i:
                continue
            xn = X - (sf[j] - sf[i])                  # same patch of road, exactly
            xn = round(xn * 2) / 2
            if not (x_near - 1.5 <= xn <= x_near + 1.5):
                continue
            q = rows[j]["frac_by_range"].get(f"{xn:.1f}")
            w = r.get("lane_width_m_10m")
            if q is None or w is None or not np.isfinite(w):
                continue
            errs.append((p - q) * w)
            times.append(r["t"])
        if errs:
            e = np.asarray(errs)
            out[f"{X:.0f}m"] = dict(n=len(e), median_m=float(np.median(e)),
                                    p10_m=float(np.percentile(e, 10)), p90_m=float(np.percentile(e, 90)),
                                    t=times, err_m=[round(float(x), 3) for x in e])
    return out


def summarise(results, pvo, bin_s):
    def plausible(r):   # a wrong line pick shows up first as an impossible lane width
        w = r.get("lane_width_m_10m")
        return w is not None and 2.5 <= w <= 4.5
    ok = [r for r in results if r and "angle_deg" in r and r.get("straight") and plausible(r)]
    summ_curved = sum(1 for r in results if r and not r.get("straight"))
    summ = dict(frames_sampled=len(results), frames_straight_with_lane=len(ok),
                frames_curved_or_slow=summ_curved)
    if not ok:
        return summ
    a = np.array([r["angle_deg"] for r in ok])
    summ["angle_deg"] = dict(median=float(np.median(a)), p10=float(np.percentile(a, 10)),
                             p90=float(np.percentile(a, 90)))
    for k in ("offset_frac_10m", "offset_frac_25m"):
        x = np.array([r[k] for r in ok if k in r])
        if x.size:
            summ[k] = dict(median=float(np.median(x)), p10=float(np.percentile(x, 10)),
                           p90=float(np.percentile(x, 90)))
    for k in ("centre_inside_30m", "edges_inside_30m"):
        x = [r[k] for r in ok if r.get(k) is not None]
        if x:
            summ[k] = dict(rate=float(np.mean(x)), n=len(x))
    bins = {}
    for r in ok:
        b = int(r["t"] // bin_s) * bin_s
        bins.setdefault(b, []).append(r)
    summ["bins"] = []
    for b in sorted(bins):
        rs = bins[b]
        e = dict(t0=b, n=len(rs), angle_deg=float(np.median([r["angle_deg"] for r in rs])))
        for k in ("offset_frac_10m", "offset_frac_25m"):
            x = [r[k] for r in rs if k in r]
            if x:
                e[k] = float(np.median(x))
        for X, d in pvo.items():
            x = [err for tt, err in zip(d["t"], d["err_m"]) if b <= tt < b + bin_s]
            if x:
                e[f"pvo_{X}_median_m"] = float(np.median(x))
        summ["bins"].append(e)
    summ["predict_vs_outcome"] = {k: {kk: vv for kk, vv in d.items() if kk not in ("t", "err_m")}
                                  for k, d in pvo.items()}
    return summ


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", type=pathlib.Path, required=True,
                    help="pipeline output folder of one recording")
    ap.add_argument("--attitude-track", default=None)
    ap.add_argument("--every", type=int, default=3, help="analyse every Nth frame")
    ap.add_argument("--near-visible-m", type=float, default=7.0,
                    help="nearest camera range not hidden by the bonnet")
    ap.add_argument("--vehicle-width", type=float, default=1.9)
    ap.add_argument("--x-near", type=float, default=8.0)
    ap.add_argument("--straight-range-m", type=float, default=40.0)
    ap.add_argument("--straight-deg", type=float, default=1.5,
                    help="max heading change over the next straight-range-m to count as straight")
    ap.add_argument("--pvo-ranges", type=float, nargs="+", default=[20.0, 30.0])
    ap.add_argument("--bin-s", type=float, default=5.0)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    ap.add_argument("--draw", type=int, nargs="*", default=[])
    ap.add_argument("--draw-dir", type=pathlib.Path, default=pathlib.Path("."))
    args = ap.parse_args()

    cal = json.loads((args.run / "calibration.json").read_text())
    cam0 = load_camera(cal)
    track = load_attitude_track(args.attitude_track) if args.attitude_track else None
    recs = [json.loads(ln) for ln in (args.run / "trajectory.jsonl").read_text().splitlines() if ln.strip()]
    by_frame = {int(r["frame"]): r for r in recs}
    todo = sorted(set(sorted(by_frame)[::args.every]) | set(args.draw))
    results = []
    for f in todo:
        rec = by_frame.get(f)
        img = cv2.imread(str(args.run / "frames" / f"{f:06d}.jpg"), cv2.IMREAD_COLOR)
        if rec is None or img is None:
            continue
        cam = camera_for_time(cam0, track, float(rec["t_session_s"]))
        res = analyse_frame(img, cam, rec, args)
        results.append(res)
        if f in args.draw:
            args.draw_dir.mkdir(parents=True, exist_ok=True)
            draw(img, cam, rec, res, args.draw_dir / f"verify_{f:06d}.jpg")
    pvo = predict_vs_outcome(results, by_frame, args.x_near, args.pvo_ranges)
    summ = summarise(results, pvo, args.bin_s)
    print(json.dumps({k: v for k, v in summ.items() if k != "bins"}, indent=1))
    print(f"{'t0':>5} {'n':>4} {'angle':>7} {'off10':>7} {'off25':>7}  pvo")
    for b in summ.get("bins", []):
        pv = "  ".join(f"{k[4:-9]}={v:+.2f}" for k, v in b.items() if k.startswith("pvo_"))
        print(f"{b['t0']:5.0f} {b['n']:4d} {b['angle_deg']:+7.2f} "
              f"{b.get('offset_frac_10m', float('nan')):+7.3f} {b.get('offset_frac_25m', float('nan')):+7.3f}  {pv}")
    if args.json:
        args.json.write_text(json.dumps(dict(summary=summ, frames=results), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
