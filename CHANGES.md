# Changes since the Google Drive original

The first commit of this repository is the original Google Drive project, byte for byte.
Everything after it is work done while the pipeline lived inside the TanitAD repository
(`stack/tanitad/data/trajrecon/`, 2026-08-08 → 2026-09-24), brought back here.

All of it was driven by one recording: `2026-08-08_14-19-54-android`, Samsung SM-G990B
on a VW Caddy V Maxi, France, with **electronic image stabilisation (EIS) on**. The
measurements behind each change are in `studies/` and in `docs/CALIBRATION_RETRACTIONS.md`.

## Modules

| file | status | what changed and why |
|---|---|---|
| `trajlib/camera.py` | changed | The focus-of-expansion rotation gate reads the **gyro** instead of `timesync.image_angular_rate` (a timing instrument whose yaw amplitude grows with speed). At 70–84 km/h the old gate passed 0.4 % of frames and the FOE returned `None`; with the gyro the same clip gives 425,093 flow vectors at 86 % inliers. The nominal-focal fallback is now labelled as the uncropped lens: with EIS on, the recorded video is a crop, so the real focal is larger (1.19× on the 2026-08-08 phone). |
| `trajlib/viz.py` | changed | The drawn corridor fades out between 30 m and 55 m (`--fade-start-m`, `--fade-end-m`). `near_clip_m` is now measured from the camera: it is a camera range but was compared against distances from the rear axle, which started the ribbon 2.1 m too close, drawn over the bonnet. |
| `trajlib/ground_calib.py` | changed | Track correspondences that do not move like the road are rejected before the fit. |
| `trajlib/lane_calib.py` | changed | The ridge operator's width is sized from the camera geometry for 18 cm paint at each row (`paint_width_schedule`), instead of a fixed 2 → 28 px ramp that was too narrow in the far field, where the lane's angle is measured. |
| `trajlib/flow_calib.py` | **new** | Measures `f*h` **and** the horizon from ground flow against the odometer: the one paint-free scale estimate. On by default (`--flow-calib`, `--no-flow-calib`). |
| `trajlib/horizon_calib.py` | **new** | Horizon row in closed form from the fact that a lane does not change width with range: pixel width is linear in row and hits zero at the horizon. Needs no known lane width. |
| `trajlib/attitude_track.py` | **new** | A time-varying camera yaw (and optionally horizon row), interpolated per rendered frame. Needed because EIS moves the crop window, so the effective camera yaw drifts by about 3° through the 2026-08-08 clip and no constant yaw keeps the overlay in the lane. It changes only what the overlay is drawn with; the trajectory does not depend on it. |
| `pipeline.py` | changed | `self_calibrate` passes `max_yaw_correction_deg` to `lane_calib.estimate` explicitly: with no FOE the old default gated the lane yaw against a nominal 0.0 and threw away a measured −7.01°. New flags below. |

`trajlib/__init__.py` stays empty as in the original. TanitAD's version only aliased the
package as `trajlib`; here `trajlib/` is the real package. TanitAD's `contract.py`
(conversion to TanitAD's episode format) is not included, since it depends on TanitAD.

## New `pipeline.py` flags

The calibration overrides are recorded in `calibration.json` as operator values, not measurements.

| flag | purpose |
|---|---|
| `--cam-yaw`, `--cam-pitch`, `--cam-roll` | set the mount angles (degrees) |
| `--focal-px` | set the focal length; applied before `--horizon-row` |
| `--horizon-row` | set pitch through the row the lane converges to: `pitch = atan2(row − cy, fy)` |
| `--lock-height`, `--lock-lateral` | stop the estimators from replacing `--cam-height` / `--lateral-offset` |
| `--attitude-track` | JSON `{t_session_s, yaw_deg[, horizon_row]}` applied per frame when drawing |
| `--near-clip-m`, `--fade-start-m`, `--fade-end-m` | where the drawn corridor starts and fades |
| `--vehicle-name` | label shown in the overlay |
| `--flow-calib` / `--no-flow-calib` | turn the `flow_calib` estimator on or off |

## The 2026-08-08 render (v12)

The final render of that recording used:

```bash
python pipeline.py --input-dir <folder with the zip> --output-dir <out> \
    --focal-px 1533 --cam-yaw -6.10 --cam-roll 0 --horizon-row 463.0 \
    --cam-height 1.586 --lock-height --lateral-offset -0.260 --lock-lateral \
    --vehicle-width 1.855 --wheelbase 3.105 --near-clip-m 6.5 \
    --fade-start-m 30 --fade-end-m 55 --vehicle-name "VW Caddy V Maxi" \
    --attitude-track studies/2026-09-13-bev-semantic-calib/attitude/attitude_track_v12.json
```

`attitude_track_v12.json` fuses the windscreen/bonnet edge (cowl) tracked frame to frame,
for fast changes, with a low-passed correction from checking where the car actually went
against where the ribbon pointed, for the absolute level. At the frame the PI flagged
(t = 34.43 s) the angle between the drawn path and the lane went from −1.75° with a
constant yaw to −0.16° (`studies/2026-09-13-bev-semantic-calib/BEV_SEMANTIC_CALIB.md`
§158). It is validated mainly on 5–40 s; after about 40 s there are almost no checks
available, and it falls back to the cowl track plus a constant.

**For new recordings, turn stabilisation off and use a rigid mount.** That removes the
need for a per-frame track.

## 4K recordings (Galaxy S24 Ultra, 2026-11-03)

The calibration steps are tuned in 1080p pixels (for example `flow_calib` searches for
the horizon in rows 380-580), so a 3840x2160 video fails calibration. Until the code
is resolution-independent, scale the video to 1920x1080 and repack the zip with the
original sensor files. **The frame timestamps must survive the re-encode**: with
`-fps_mode passthrough` alone, ffmpeg 6.1 still snapped them to an exact 30.000 fps
grid, off by up to 16.7 ms from the phone's ~30.002 fps (0.4 m at 25 m/s). Adding
`-enc_time_base:v demux` keeps them exact (checked: 20,176 frames, max difference 0.0 ms).

```bash
ffmpeg -i Camera/<id>.mp4 -map 0:v:0 -map_metadata 0 -copyts -fps_mode passthrough \
  -enc_time_base:v demux -vf scale=1920:1080:flags=area -c:v libx264 -preset veryfast \
  -crf 17 -pix_fmt yuv420p -video_track_timescale 90000 -movflags +faststart out.mp4
```

`--render-window T0 T1` limits the per-frame outputs (trajectory.jsonl, frames, video)
to a stretch of the drive for a quick check; calibration still uses the whole recording.

## 2026-11-21 recordings (S24 Ultra main lens, 4K, night): camera values

Mount by tape (`Data/.../261121_Verbauort_Smartphone-Kamera_Position_Masse.PNG`): 0.95 m behind
the front axle (1.996 m ahead of the rear axle), 0.00 m lateral, 1.25 m above ground.

| recording | focal (1080p) | horizon row | yaw | source |
|---|---|---|---|---|
| St2392 (19:04) | 1430 px | 434.5 | -0.708 deg | lane VP (71 frames, spread 0.13 deg) |
| 2026-11-21_19-37-30 | 1430 px | 466.7 | -0.666 deg | lane VP (79 frames, spread 0.09 deg); phone tilted ~1.5 deg up vs St2392 (bonnet edge moves by the same 30 px) |
| Am_Westpark (18:42) | 1430 px | 436.6 | -0.708 deg | horizon from lane VP; yaw declined on urban streets (spread 0.81 deg), St2392's used (same mount position) |

**Lateral offset (applied 2026-11-22, at the PI's request).** With the tape value 0.00 m the drawn
path sat right of the lane centre on straight roads at 10 m: St2392 +0.161 m (n = 1429), 19:37
+0.052 m (n = 1033), Westpark +0.194 m (n = 2954). The video cannot separate a camera offset from
the driver keeping right; the renders now ASSUME the car was centred on average and use
`--lateral-offset` -0.161 / -0.052 / -0.194 m (camera right of the centreline). Result: lane-centre
offset at 10 m 0.000 / 0.000 / +0.002 and -0.000 lane widths; angle and prediction-vs-outcome
unchanged (a pure shift). This overrides the tape measurement and should be replaced by a measured
offset if one becomes available.

**Focal.** The first value, 1220 px from far-field image shift against the gyro over the whole drive,
was WRONG (contaminated by near street lights at night). It passed every straight-road check,
because on a straight road a range-scale error only moves the path up or down its own line; it
showed in tight turns (roundabouts), where the far path landed on the verge. MEASURED instead by
fitting road-surface flow between frames against the ego motion (height, horizon and VP column
fixed): 1375 / 1425 / 1525 / 1450 px on four slow St2392 windows and 1500 px on the slowest 19:37
window with an 8-frame gap; the gyro method restricted to low speed and features above the horizon
gives 1385-1430 px. Lane width from the tape height (f-independent) is 3.66 m, consistent with
1.25 m. Windows at motorway speed are unusable for the flow fit (tracking fails).

## Variable-frame-rate video: exact frame access (2026-11-22)

The night recordings of 2026-11-21 (Galaxy S24 Ultra, main lens) are variable-frame-rate:
33.3 ms frames, stretched to 40 ms in the dark. Every frame lookup in the pipeline went through
OpenCV's `CAP_PROP_POS_FRAMES`, which turns an index into a time with one average fps, and
`lane_calib` turned times into indices the same way. MEASURED on St2392: the old seek returned
the wrong frame for 10 of 10 probed indices; the rendered pilot showed the camera image 12
frames (0.4 s, about 10 m at 93 km/h) away from its overlay, and the offset changed abruptly,
which played as jumps. The 2026-11-03 1000N recording was constant 30 fps and was not affected.

* `trajlib/frames.py`: `FrameSource` positions by each frame's PTS and confirms the decoder's
  timestamp before returning it; short forward hops decode through. New `get(i)` and
  `index_at(t)`.
* `pipeline.py`: the render keeps one `FrameSource` for the whole clip instead of reopening the
  file and seeking per frame; `_grab_bgr` uses it too.
* `trajlib/lane_calib.py`: frame index from PTS, not `t * fps`.
* Test: `tests/test_frames_vfr.py` builds a VFR clip whose frames carry their own index and
  checks random, sequential and strided access (and that the naive seek is wrong on it).
* **Sync decoder** (`timesync._iter_gray_frames`): the rawvideo pipe defaulted to constant-rate
  output and duplicated frames (St2392: 16,191 emitted for 15,902), while the caller pairs frames
  with `video.pts` by index. Now `-fps_mode passthrough`. On St2392 the sync window (first 40 s)
  had no stretched frames, so its result was unchanged (0.2496 s); a window at 480-520 s gives
  0.3038 s, 54 ms apart.
* **Real-time output.** The render wrote one output frame per source frame at a fixed rate, so
  the clip ran fast wherever frames were stretched (St2392: up to 5.8 s ahead of real time;
  the 60 s pilot played in 55.2 s). It now writes at the nominal rate (median frame interval)
  and repeats a frame for as long as it really lasted (`trajlib.frames.realtime_repeats`).
  `tools/retime_overlay.py` does the same to an already-rendered clip, using the run's
  `trajectory.jsonl` timestamps (refuses if the frame counts differ).

## Longitudinal accelerometer (2026-11-22)

`trajlib/accel_source.py` had been switching the forward accelerometer off on every S24 Ultra
recording ("accelerometer carries no usable longitudinal signal"). The sensor was not at fault.
Tier 1 removed gravity with the phone's own `Orientation` quaternion, and that attitude is
accel-led: it tilts toward any sustained acceleration, so subtracting it cancels the signal.
MEASURED on 2026-11-03 1000N (1 s means against GNSS dv/dt): tier 1 r = 0.27, gain 0.12;
the phone's gravity estimate alone r = 0.90, gain 0.87 (that is the acceleration it absorbed);
the raw accelerometer with gravity held fixed r = 0.94, gain 0.99.

* **Tier 0 (new, default):** raw `TotalAcceleration` in the fixed vehicle frame, gravity treated
  as constant (the mount is rigid), median removed; slow road grade is left to the filter's
  accel-bias state. `cfg["accel_mode"]`: `auto` (default) | `legacy` (old tiers 1-3 and scoring)
  | `none`.
* **Scoring:** 1 s means of the accelerometer against GNSS speed differences (point-sampling a
  100 Hz signal at 1 Hz compares vibration with a finite difference); GNSS speed glitches
  rejected on the joint-fit residual (MAD, iterated); gain is the symmetric slope (both sides
  are noisy) and must lie in 0.6-1.6. St2392 at night (receiver speed accuracy 0.81 m/s vs 0.14)
  went from r = 0.57, gain 0.44 (rejected) to r = 0.85, gain 1.00 (accepted); 4 of 491 intervals
  were glitches.
* **Barometric grade (opt-in, `grade_source="baro"`), off by default:** with it the 1000N channel
  fell from r = 0.94 to 0.76 and one 10 s outage diverged to 153 m. Cabin pressure follows speed
  and ventilation, not only road climb.

GNSS hold-out, `legacy` → `auto` (every 5th fix withheld; plus 8 outages of 10 s and of 30 s
per drive with ALL GNSS removed while moving; n = 8 per gap length, so read them as indicative):

| | 1000N legacy | 1000N auto | St2392 legacy | St2392 auto |
|---|---|---|---|---|
| hold-out position RMS | 1.36 m | **1.08 m** | 1.88 m | 1.91 m |
| hold-out speed RMS | 0.27 m/s | **0.17 m/s** | 0.84 m/s | 0.80 m/s |
| hold-out heading p95 | 1.53° | 1.42° | 3.52° | 3.84° |
| 10 s outage position RMS (worst gap) | 1.80 m (3.57) | **1.28 m (2.94)** | 3.31 m (8.51) | **2.33 m (4.37)** |
| 30 s outage position RMS (worst gap) | 9.90 m (31.6) | **3.57 m (12.5)** | 10.1 m (27.2) | **7.54 m (22.5)** |
| 30 s outage speed RMS | 1.30 m/s | **0.43 m/s** | 1.47 m/s | **1.07 m/s** |

Where GNSS is present it decides the answer and the change is small; across outages the
accelerometer carries the speed, and 30 s outage error drops by 2.8× (1000N) and 1.3× (St2392).
Tests: `tests/test_accel_source.py`.

## Checking an overlay

`tools/verify_overlay.py` measures, on a finished output folder, whether the drawn path
stays in the lane: the angle between path and lane (fitted as whole lines), the offset
from the lane centre at 10 m and 25 m, and prediction vs outcome (where the ribbon said
the car would be at 20/30 m against where it was when it got there), per frame and per
5 s bin. It is the general form of the probes in `studies/2026-09-13-bev-semantic-calib/probes/`,
which were tied to one recording.

```bash
python tools/verify_overlay.py --run <output>/<recording> --json verify.json --draw 300 900 --draw-dir checks/
```

## Tests

`tests/` was ported from TanitAD (`stack/tests/test_trajrecon_*.py`,
`test_horizon_calib.py`), with paths changed to this layout. Run `python -m pytest -q`.
The import check reads import statements without importing, and the integrity check
looks for control bytes and invalid UTF-8, the signature of the corruption that hit
`vp_calib.py` during the copy into TanitAD.

## Not included

From the Drive folder: `work/` (scratch scripts, logs, arrays, images), the recording
zips, `synchronized_output/` and `__pycache__/`. From TanitAD: rendered videos, which
are build outputs.
