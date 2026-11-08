# Handover: validated front-camera pilot, 2026-11-03 1000N (A6 e-tron, Galaxy S24 Ultra)

From the TrajectoryReconstruction session, for the Scenario Flywheel work: one validated
60-second piece of real driving with its ego trajectory and front-camera calibration, as the
reference that any additional (synthesised) camera views must be consistent with.

## What it is

| item | value |
|---|---|
| recording | `1000N-2026-11-03_08-08-19-android` (Sensor Logger 1.68, SM-S928B, Europe/Berlin) |
| vehicle | Audi A6 e-tron, wheelbase 2.946 m, body width 1.923 m |
| camera | phone **ultra-wide (0.6x)** lens, stabilisation off, mounted in front of the rear-view mirror |
| piece | session time **150.03 - 210.00 s**, frames **4487 - 6286** (1,800 frames, ~30.002 fps) |
| conditions | rural two-lane road, 22-26 m/s, several right-hand bends, overcast |

The source video is on Drive next to this project:
`G:\Meine Ablage\SayBouBase\raw\Projects\TrajectoryReconstruction\1000N-2026-11-03_08-08-19-android.zip`
→ `Camera/1793693299492.mp4` (3840x2160, H.264). Frame indices below refer to that file
(they are identical in the 1080p transcode used for processing).

## Files

| file | content |
|---|---|
| `trajectory.jsonl` | one record per frame: `frame`, `pts_s`, `t_session_s`, `t_utc`, `speed_ms`, `steer_wheel_deg`, and the ego trajectory over t = -3 ... +5 s at 0.1 s: `t`, `x` (forward, m), `y` (left, m), `yaw` (rad), `v` (m/s), `pos_sigma` (m) |
| `frame_index.csv` | frame → pts, session time, UTC, speed, steering (for quick joins) |
| `camera.json` | **front-camera model to stay consistent with**: intrinsics at 1080p and 4K, mount extrinsics in the vehicle frame, conventions, and the provenance of every value |
| `calibration.json` | the pipeline's own calibration record for this run |
| `report.json` | the pipeline's diagnosis and validation report |
| `verify_summary.json` | lane-line verification of the drawn trajectory |

## Conventions

* **Ego/vehicle frame**: FLU (x forward, y left, z up), origin at the **rear axle** at the frame's
  instant; the trajectory is the rear axle's path (not the phone's).
* **Time**: session seconds since the Sensor Logger epoch. For a frame,
  `t_session = 0.47 s + pts_s` (gyro-synchronised; three frequency bands agree to 35 ms).
* **Camera**: pinhole, principal point at the image centre, OpenCV axes (x right, y down, z forward).
  Camera position in the vehicle frame: (1.75, 0.0, 1.30) m. Rotation: yaw -9.6 deg (camera points
  right of the driving direction), pitch +0.33 deg (horizon row 544 at 1080p), roll 0.
  At 4K multiply fx, fy, cx, cy and the horizon row by 2.
* A ground point at forward range X and lateral offset Y from the camera projects to
  `v = v_h + f*h/X`, `u = c_x + f*Y/X` (flat road).

## How good it is (MEASURED on this piece)

* Trajectory (whole 11 min drive, GNSS hold-out, every 5th fix withheld): position RMS 1.36 m,
  speed RMS 0.27 m/s, heading p95 1.53 deg.
* Projection vs the painted lane lines (`tools/verify_overlay.py`, 29 straight frames with both
  lines): path-vs-lane angle median -0.14 deg (p10/p90 -0.96/+0.84); ribbon centre inside the lane to
  30 m on 29/29 frames, full width on 26/29; prediction vs outcome +0.01 m median at 20 and 30 m.

## Caveats: read before using

* **Camera values are measured on this window, then fixed by hand** (pipeline overrides): focal
  700 px from image rotation vs gyro, height 1.30 m from lane-dash motion, yaw and horizon from the
  lane vanishing point. They are not yet validated over the full 11 minutes.
* The lens model assumes the phone already corrected ultra-wide distortion; residual distortion
  toward the image edges is untested.
* Lateral offset 0 is assumed, longitudinal 1.75 m is estimated from the car's proportions; neither
  was measured with a tape.
* The bottom third of the image is the car's dashboard and bonnet; any generated view should mask it.
* Only 29 of 1,800 frames are straight enough for the lane metric; most of the piece is bends.
* The full 11-minute render with these settings is in progress; a package for the whole drive will follow.

Produced by `pipeline.py` (TrajectoryReconstruction repo) with:

```
--focal-px 700 --cam-yaw -9.6 --cam-roll 0 --horizon-row 544 --cam-height 1.30 --lock-height
--lateral-offset 0.0 --lock-lateral --mount-longitudinal 1.75 --vehicle-width 1.923
--render-window 150 210
```
