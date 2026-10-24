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
