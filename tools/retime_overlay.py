#!/usr/bin/env python3
"""Make an already-rendered overlay play in real time.

Renders made before ``realtime_repeats`` wrote one output frame per source frame at
a fixed rate, so a variable-frame-rate recording plays fast wherever the camera
stretched its frames (2026-11-21 St2392: up to 5.8 s ahead of real time). This
re-encodes such a clip at the nominal rate, repeating each frame for as long as it
really lasted. The frame timestamps come from the run's ``trajectory.jsonl``; the
clip's frame count must match it exactly, otherwise nothing is written.

    python tools/retime_overlay.py --run <output>/<recording> [--out overlay_rt.mp4]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from trajlib.frames import realtime_repeats  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, type=pathlib.Path)
    ap.add_argument("--video", default="overlay.mp4")
    ap.add_argument("--out", default="overlay_realtime.mp4")
    ap.add_argument("--t0", type=float, default=None, help="session time of the clip's first frame "
                    "(only for clips rendered with --render-window)")
    ap.add_argument("--t1", type=float, default=None)
    ap.add_argument("--crf", type=int, default=22)   # pipeline default
    args = ap.parse_args()
    import cv2

    recs = [json.loads(l) for l in open(args.run / "trajectory.jsonl")]
    t = np.array([r["pts_s"] for r in recs], dtype=float)
    ts = np.array([r["t_session_s"] for r in recs], dtype=float)
    if args.t0 is not None:
        t = t[(ts >= args.t0) & (ts <= (args.t1 if args.t1 is not None else np.inf))]
    src = str(args.run / args.video)
    n_clip = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0",
                                 "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", src],
                                capture_output=True, text=True, check=True).stdout.strip())
    if n_clip != len(t):
        raise SystemExit(f"clip has {n_clip} frames, trajectory.jsonl lists {len(t)}: not retiming")
    d = np.diff(t)
    fps = 1.0 / float(np.median(d[d > 0]))
    reps = realtime_repeats(t, fps)
    cap = cv2.VideoCapture(src)
    proc = None
    out = str(args.run / args.out)
    for k in range(n_clip):
        ok, img = cap.read()
        if not ok:
            raise SystemExit(f"decode failed at frame {k}")
        if proc is None:
            h, w = img.shape[:2]
            proc = subprocess.Popen([shutil.which("ffmpeg"), "-y", "-v", "error", "-f", "rawvideo",
                                     "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps:.6f}",
                                     "-i", "-", "-c:v", "libx264", "-preset", "medium",
                                     "-crf", str(args.crf), "-pix_fmt", "yuv420p",
                                     "-movflags", "+faststart", out], stdin=subprocess.PIPE)
        b = img.tobytes()
        for _ in range(int(reps[k])):
            proc.stdin.write(b)
    proc.stdin.close()
    proc.wait()
    print(f"{n_clip} frames -> {int(reps.sum())} at {fps:.3f} fps "
          f"({reps.sum() / fps:.1f} s; the fixed-rate clip lasted {n_clip / fps:.1f} s) -> {out}")


if __name__ == "__main__":
    main()
