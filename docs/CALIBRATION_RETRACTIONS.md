# Calibration retractions (2026-09-13 → 2026-09-24)

Copied verbatim from TanitAD's `Project Steering/RETRACTION_LOG.md` (the entries from
`R-2026-09-13-horizon` to the end of the log on 2026-10-24). Each one records a claim
about this pipeline's calibration that turned out to be wrong, the measurement that
refuted it, and the **class** of mistake, so the same mistake is recognised next time.

Class codes (C1–C6, C15) refer to the table at the top of the TanitAD log:

| # | class | recognition signal |
|---|---|---|
| **C1** | Faster-moving source than the harness | the number came from something that updates every few steps |
| **C2** | Absence from a single probe | "X does not exist" after exactly one check |
| **C3** | Mechanism instead of measurement | the sentence contains "because" and no artifact path |
| **C4** | Inherited without re-verification | cannot name the file the number lives in |
| **C5** | Scalar off a noisy curve at one point | a ratio or exponent with no window, R², or n |
| **C6** | Confounded comparison | two arms differ in ≥2 respects and only one is named |
| **C15** | A quantity's meaning taken from its NAME rather than from where it is built | a key or field is used as if its name were a specification |

Paths in the entries are TanitAD paths. The study folders they cite are copied here under
`studies/`.

---

## R-2026-09-13-horizon — ⛔ I RULED THE FOE HORIZON WRONG AND THE LANE-VP HORIZON RIGHT. IT IS THE OTHER WAY ROUND.

**Context.** Sayed: *"the yaw angle is definitely wrong in the video"*, then *"all the values are
wrong yaw, pitch, height and lateral offset (I estimate this to -12 cm), i think also the 1.6m height
are very plausible"*. The camera calibration for `2026-08-08_14-19-54-android` has three candidate
horizon rows, and the horizon is what the pitch encodes.

**What I asserted earlier this session** (and carried into `bev_calib.py`, `lag_scale.py`,
`lane_width.py` and the run defaults): the lane vanishing point puts the horizon at **523.4 px**
[513.3, 534.8], the pipeline's FOE puts it at **464.4 px**, they are 2.29 deg apart, and *the FOE is
the wrong one*. Every subsequent module defaulted to `--horizon 523.4`.

**MEASURED today, two independent ways, and both say 523.4 is the outlier:**

| probe | horizon | what it is |
|---|---|---|
| row-flow fit, 65,132 tracked points over 218 frame pairs | **448.4 px** | `dv = D q²/(A - D q)`, horizon = the value at which the per-point `f*h` stops trending with image row |
| lane width held range-independent, 120 frames | **~485 px** | far/near width ratio 1.045 at 485, vs **1.415 at 523.4** and 0.864 at 464.4 |
| pipeline FOE (inherited) | 464.4 px | 425,093 flow vectors, inliers 0.86 |
| lane VP (my earlier claim) | 523.4 px | **refuted by the two above** |

Three estimates now cluster at **448-485 px**, straddling the FOE's 464.4. The lane-VP value sits
**~50 px away from all of them**, and at 523.4 the reconstructed lane width grows **41.5% from the
8-13 m slab to the 18-25 m slab** — the plane is tilted, which is exactly what a wrong horizon does.

**Consequences, because this was load-bearing:**
- The claim *"the pipeline's pitch is wrong by 2.29 deg"* is **WITHDRAWN**. The pipeline's pitch is
  approximately right; the FOE gate fix earlier in this session stands on its own evidence (it fixed
  a rotation gate fed by a timing instrument) and is untouched by this.
- `f*h` is **2444 px·m** [flow], against the shipped `1478.3 x 1.17 = 1729` — **41% low**. With the
  lateral ruler giving `h ≈ 1.7 m`, `f ≈ 1421 px` (HFOV 68.5 deg), i.e. **the shipped FOCAL was
  roughly right and the shipped HEIGHT was badly wrong.** I had been searching for a focal error.
- Sayed's *"1.6 m is very plausible"* is corroborated, not contradicted, by the measurement.

**ROOT-CAUSE CLASS — C6 (confounded comparison), with a C3 tail.** I compared two horizon estimates
against each other and picked the one I could explain, instead of finding a **third, independent
criterion that neither had been fitted to**. Both candidates were *derived from image structure*;
the arbiter had to come from somewhere else (ego motion, and range-consistency of a lateral metre).
The C3 tail: I supplied a mechanism ("the FOE is contaminated") and let it settle a measurement.

⇒ **RULE: when two estimates of the same quantity disagree, do not adjudicate between them on
plausibility — find a criterion that is orthogonal to BOTH and let it vote.** Two probes that share
a failure mode can agree, or disagree, for reasons neither reveals.
⇒ **RULE: a defaulted parameter carries its evidence.** `--horizon 523.4` propagated into four
modules as a *default*, where it stopped looking like a claim and started looking like a constant.
Defaults inherit the evidence class of whatever set them — here, a retracted one.
⇒ **Same family as the `df` / Thor-`free` / cgroup-`usage_in_bytes` traps:** not a wrong number, a
probe answering a question next to the one asked. A vanishing point measures where lane lines
converge; the horizon is where the GROUND PLANE vanishes, and on a crowned, curving road those are
not the same row.

---

## R-2026-09-14-onvideo — the on-video overlay check was measuring the wrong 10 metres

**WITHDRAWN:** *"the joint fit is measurably worse on the actual video — left gap 21 px vs 49 px at
row 420, covering a line 4 %/3 %/2 % against 1 %/0 %/0 %"*, and with it the decision **not to ship
the joint fit**. The comparison is void; both arms have to be re-measured.

**What the probe actually did** (`/tmp/overlap.py`, now superseded by
`probes/overlay_far.py`), three independent defects, all in the same direction:

| # | defect | measured consequence |
|---|---|---|
| 1 | assumed the camera panel was **1178 px** wide | `compose_panels` resizes 1920×1080 to height 720, so the panel is **1280 px** (scale exactly 2/3) and the BEV starts at column 1280 — CONFIRMED here, first near-white column = 1280 on both renders. **153 source columns were cut off the right edge**, so every RIGHT-hand gap it printed was measured against a truncated image. |
| 2 | sampled **fixed composite rows 420–660** | with `f·h = 2703`, horizon 485 those rows are source rows 630–990, i.e. ranges **4.8 m to 14.2 m**. Sayed's complaint is *"cuts road markings at LARGE distances"*. **The probe never looked past 14 m.** |
| 3 | required **≥ 25 green pixels** in the row | the fill ramps green→amber with time (`col = (60+40f, 230−60f, 40+200f)` BGR), so beyond a few seconds G < R and the fill is not green at all — only the two edge polylines, drawn opaque at `(200,255,200)`, stay green, and they contribute ~4–8 px. The far rows were **silently skipped**, which is why defect 2 was invisible. |

**ROOT-CAUSE CLASS — C-SCOPE (a probe answering a different question than the one asked),** the same
family as `df` on pod disk, Thor's `free`/`tegrastats`, cgroup `usage_in_bytes`, and the Google-Drive
404 classifier. Every one of those returned a confident number for a question next to the real one.
Here the question was *"does the corridor cut the paint far away?"* and the instrument answered
*"how close is the corridor to the paint between 5 and 14 metres?"*

**The aggravating factor, and the actual lesson.** This probe was not a measurement I was curious
about — **it was the arbiter I used to reject a fitted calibration.** It was written in one pass, run
once, and given decision authority immediately.

⇒ **RULE: an instrument that will DECIDE something gets a validity check before its first verdict,
not after a surprising one.** The cheap check here was three lines — print the RANGE of every row it
samples. It would have shown 4.8–14.2 m instantly.
⇒ **RULE: when a probe reads an image a renderer produced, the panel geometry is a MEASUREMENT, not
an assumption.** One `colmean` scan settled it.
⇒ **Corollary to "verify before alarming": also verify before REJECTING.** The cost of this one was
a fitted calibration discarded on a metric that could not see the defect it was fitted against.

---

## R-2026-09-14-yaw — every mount yaw used on this recording was ~1.3° too negative

**WITHDRAWN:** `−7.01` (lane VP), `−6.80`, `−6.59`, `−7.80`, `−8.52` — every yaw rendered or
proposed for `2026-08-08_14-19-54-android`. **MEASURED: −5.30°**, robust sd 1.01° over 54 straight
frames, from the paint alone: the left lane line's column **at the horizon row** is `cx + f·tan(yaw)`,
because the `y/h` term vanishes exactly at `v = v_h`. No trajectory, no ego motion, no flow.

Corroborated independently by a render-less yaw scan on **three separately rendered videos**
(rendered at −6.59, −6.80, −7.80): **−5.34 / −5.30 / −5.55**, spread 0.25°.

**ROOT-CAUSE CLASS — C-COUPLED (a parameter fitted through a wrong coupled parameter, then frozen).**
Not one of these yaws was independently wrong. Every one was the correct answer *to the question
asked*, and the question contained a horizon that was 37–75 px too low. `yaw = atan((u(v_h) − cx)/f)`
is a function of `v_h`; a 37 px horizon error moves it by about 1.1°. The session then spent hours
refitting yaw — including a refit that made the video measurably worse — while the parameter that
was actually wrong sat frozen upstream.

⇒ **RULE: before refitting a parameter that keeps coming out wrong, write down what it is a function
of and check THOSE first.** The symptom appears in the dependent parameter and the defect lives in
the independent one. Three refits of yaw all moved the wrong dial.
⇒ **RULE: a parameter is only "measured" together with the parameters it was measured through.**
`−7.01 at horizon 523.4` and `−7.01` are different claims, and only the first one is true.
⇒ **Corollary that actually broke the deadlock:** the escape from a coupled chain is an estimator
that CANCELS the coupling algebraically, not a better optimiser. Two were found, both by eliminating
range between the two projection equations: `Δy = Δu·h/(v − v_h)` (no focal length) and
`du/dv = y/h` (no focal length AND no horizon). The second measured the camera height —
**1.573 m [1.511, 1.628]** — which nothing had managed in the entire session, and it then confirmed
the horizon from outside the chain that produced it.

---

## R-2026-09-14-slopeheight — the "no-horizon" camera height was a prior, not a measurement

**WITHDRAWN:** *"h = 1.573 m [1.511, 1.628], measured from the lane-line slope difference with no
horizon, no focal length and no ego motion"*, and with it the claim that it **confirmed** the joint
fit *"from a route that shares no parameter with the route that produced it"*.

The algebra is right: `du/dv = y/h` for a road-parallel line, so `|m_L − m_R| = 3.5/h` really does
carry no horizon and no focal length. The failure is in the read-out. The estimate was the median of
the values falling in a **1.6–3.2 band that I chose from prior expectation**, on the stated grounds
that it was where a single lane "should" sit.

**MEASURED today, the histogram inside that band, 200 frames:**

    1.6-1.7 n14 | 1.7-1.8 n8 | 1.8-1.9 n8 | 1.9-2.0 n4 | 2.0-2.1 n6 | 2.1-2.2 n12
    2.2-2.3 n9  | 2.3-2.4 n9 | 2.4-2.5 n10| 2.5-2.6 n10| 2.6-2.7 n5 | 2.7-2.8 n3
    2.8-2.9 n5  | 2.9-3.0 n7 | 3.0-3.1 n9 | 3.1-3.2 n5

**It is FLAT.** There is no single-lane cluster. The median of a flat distribution over a band I
picked is the band's centre, so the "measurement" was reporting my own prior back to me — and it
moves with the sample: **2.2247 → h 1.573 m** on one frame set, **2.327 → h 1.504 m** on another.
The per-pair IQR maps to h ∈ **[1.316, 1.827] m**, which is not a measurement of anything.

**I flagged the weakness in the same message that made the claim** — *"the slope-difference
histogram does NOT show the crisp 1-lane / 2-lane pair of clusters that the width histogram does, so
the 1.6–3.2 single-lane band here is a prior, not a read-off"* — and then used the number as
confirmation two paragraphs later. **Writing the caveat is not the same as obeying it.**

**ROOT-CAUSE CLASS — C-PRIOR (a selection band chosen from expectation, then read as a result),** a
sibling of the circular-association class that killed `lane_residual.py`. There the window confirmed
whatever height it was handed; here the band confirmed whatever height I expected.

⇒ **RULE: a cluster must be VISIBLE before it may be selected.** If the estimate requires a band,
publish the histogram inside the band in the same breath; a flat histogram means there is no
estimate, only a prior.
⇒ **RULE: a caveat that does not change the conclusion is decoration.** State the caveat, then act
on it — or do not state it.

**What survives, and what does not.** §50's lane-WIDTH measurement is untouched and remains the
height estimate: its histogram does show the structure — a single-lane cluster at 2.25–2.50 and a
two-lane cluster at 4.50–5.00, **exactly 2× apart** — which is evidence, not a chosen band. So
`h ≈ 1.59 m` still stands, but it stands on ONE route (which needs the horizon), not two, and the
claim of independent cross-confirmation is withdrawn. The delivered overlay is unaffected: it was
verified on the video itself, not on `h`.

---

## R-2026-09-14-foliage — the "paint detector" has been detecting the roadside bank

**WITHDRAWN:** every measurement on the 2026-08-08 recording that depended on finding the
**RIGHT-hand lane boundary**. Named explicitly, because several are load-bearing:

| claim | where | status |
|---|---|---|
| camera height **h = 1.586 m** from lane-width range-constancy | §50 | ⛔ rests on a lane width whose right edge may be foliage |
| the horizon **joint fit → 448** | §51 | ⛔ its lane-width branch shares that input |
| lane width **varies 3.27–4.10 m** across the clip | §76 | ⛔ withdrawn |
| ego **offset 0.25–0.90 m** from lane centre | §76, §75 | ⛔ withdrawn |
| **lane pair found in 81 % of frames**, width 3.38 ± 0.23 m | this turn | ⛔ withdrawn |
| the corridor is **0.37 m too far right** | this turn | ⛔ never reported, withdrawn before use |

**HOW IT WAS FOUND — by drawing the detector's input on the image, which I should have done
before running any statistic on it.** `overlay_far.ridge_cols` takes the brightest narrow features
in each image row, thresholded at the row's **99th percentile**. On this footage the sunlit
vegetation and pale rock bank to the RIGHT of the carriageway are brighter and far more textured
than the road markings, so the detector's points land overwhelmingly **on the bank**. In the
annotated frames the fitted "lane pair" sits entirely in the bushes.

**Why it went unnoticed for so long, and what that says.** The symptom was visible the whole time
and I read it as noise instead of as a wrong object:

* the right boundary had **55 median inliers against the left's 136** — read as "the dashed line is
  sparse", actually "this is not a line";
* **94 %** of frames failed a parallelism test — read as "the detector is weak";
* the implied lane read **6.41 m at 10 m growing to 18.28 m at 40 m** — read as "the gate is wrong";
* the two detectors agreed on the same left line in **0 of 260 frames** — which is what finally
  forced me to look at a picture.

Four escalating absurdities, each explained away with a plausible mechanism. **A quantity that is
physically impossible (an 18 m lane) is not a weak measurement, it is a wrong object.**

**ROOT-CAUSE CLASS — C-SCOPE (a probe answering a different question than the one asked),** the
same family as `df` on pod disk, Thor's `free`, cgroup `usage_in_bytes`, the Drive 404 classifier
and R-2026-09-14-onvideo. The operator was asked for "bright narrow ridges" and answered exactly
that — correctly. It was never asked for **road markings**, and nothing in the pipeline restricted
it to the road.

⇒ **RULE: before the first statistic, render the detector's INPUT onto the image and look at it.**
Not the fit, not the residual — the raw detections. Two minutes here would have saved a day, and
the four warning signs above were all cheaper than the picture and all less conclusive.
⇒ **RULE: a physically impossible intermediate value halts the chain.** An 18 m lane, a 42 m camera
height (§65), a 0.82 m camera height (§50) — each was treated as a gate to tune. Each was the
measurement telling me it was measuring something else.
⇒ **THE FIX is the one `ground_calib.collect_road_tracks` already uses: mask to the projected road
corridor.** The probes in `incoming/2026-09-13-bev-semantic-calib/` do not, and must.

**WHAT SURVIVES, and why.** `overlay_far` gates every candidate line to pass within **0.75 m** of a
predicted position near the corridor at the seed range — the bank is far outside that window — so
its numbers (the flat 1.15–1.28 m profile, the crossing row, the render-less yaw scan, and the
loop closing at +0.00) are **not** implicated. Left-line measurements are largely intact: the
contamination is on the right of the carriageway. The delivered renders are unaffected; what is in
doubt is the evidence for `h`, and through it `f`.

---

## `R-2026-09-15-seam` — the right-hand lane boundary was a TAR SEAM (and before that a bank, and beside it the gravel)

**WITHDRAWN.** Everything `does_it_cut_paint.py` produced from a right-hand line fit, including the
run made earlier the same day *with* the road mask: the corridor placement **−0.32 m** (−0.38 m
h-free), the camera at **−0.36 m** from lane centre, `lane w` **3.33→2.83 m**, and the
boundary-convergence row **466.1 ± 9.4 (n 183)**. Also **`h = 1.668 m`** (`h_masked.py`, §86) and
the `crop ≈ 1.0 ⇒ EIS is not cropping` conclusion built on it — both rest on a pair search whose
pair has not been shown to be the lane.

**ROOT-CAUSE CLASS — A SELECTION STEP CANNOT REPORT THAT IT SELECTED BADLY.** RANSAC scores a line
by **inlier count**. On this recording the left boundary is SOLID and the right is DASHED, so a
continuous tar seam up the middle of the ego lane offers more inliers than the real right line. The
detector was not confused — **it answered the question it was asked**, and returned the seam with a
confident support count. This is the THIRD non-paint feature a selection step here has returned
with confidence: the sunlit bank (`R-2026-09-14-foliage`), the seam, and the gravel apron at the
foot of the barrier (which is the *mode* of the lateral histogram, 5848 counts at −2.15 m).

**WHAT THE STATISTICS SAID, AND WHY I ALMOST MISSED IT.** The output table contained its own
diagnosis: `clear L` flat to **0.02 m** across 10→30 m while `clear R` drifted **0.58 m**, and the
"lane" shrank 0.50 m while the *drawn* ribbon read flat. **A range-dependent error on exactly one
side is not a calibration error — it is one of the two lines not being a line.** I had begun
writing a downgrade/horizon explanation for it before drawing the fit on the image.

⇒ **THE FIX IS NOT A BETTER GATE. It is to stop selecting.** `--hist` converts every detection to a
vehicle-frame lateral and counts; the paint, the seam and the gravel appear as separate labelled
peaks and the reader sees the structure. A fit may follow a histogram; it may not replace one.

⇒ **AND THE PREVIEW MUST DRAW THE DETECTOR'S OUTPUT, NOT ONLY ITS INPUT.** `R-2026-09-14-foliage`
established "draw the detector's input before the first statistic". That rule was FOLLOWED here and
was NOT enough: the input looked fine, the *fitted line* did not. `--preview` now runs the same
`fit_pair` as the measurement and draws the fitted lines, the mask and a **labelled lateral ruler**.

**WHAT SURVIVES.** The yaw. `overlay_far` reads the corridor against the LEFT line, and the left
line is confirmed real, isolated and narrow (a clean peak at +1.62 m with 1–30 counts either side
of it, ±0.10 m after per-frame re-referencing). §87's "rendered −5.35 vs optimum −5.10" and the
flat 1.12–1.19 m profile stand. The delivered renders' DIRECTION is right; their lateral SCALE is
in doubt.

## `R-2026-09-15-scope` — the ridge detector's threshold was set by pixels it then discards

**WITHDRAWN:** the implicit claim that adding the road mask could only improve detection. It made it
**worse**, and measurably: with the mask on, **three of four preview frames found no lane pair at
all** while the left boundary is plainly bright paint in every one.

`ridge_cols(row, w)` called with no window sets `thr = max(28, percentile(c, 99))` over the **WHOLE
ROW** — here the sunlit bank and the concrete barrier, both **outside** the mask — and the mask is
applied *after* thresholding. So discarded structures were setting the bar the paint had to clear.
`ridge_cols` has accepted `lo`/`hi` for exactly this since it was written; no caller passed them.

**ROOT-CAUSE CLASS — A STATISTIC AGGREGATED OVER THE WRONG SCOPE, READ AS AN ANSWER.** Fourth
costume, after `df` reporting the 965 TB cluster instead of the pod quota, `free`/`tegrastats` on
Thor unified memory, and cgroup `usage_in_bytes` counting reclaimable page cache. ⇒ **When a probe
and a filter are composed, check which one runs first.** A threshold computed before a mask is a
threshold for a different image.

---

## `R-2026-09-15-lanewidth` — the 3.5 m lane was an ASSUMPTION, and the optics refute it

**WITHDRAWN:** *"the lane is 3.50 m"* as an **input** to this calibration, and with it every `h`
derived from it — §16's `h ≈ 1.65–1.86 m`, §86's `h = 1.668 m`, and the justification (though not
the values) of the adopted `h = 1.586 · f = 1533`.

**THE CIRCULARITY.** `f·h` came from the row flow against the odometer (no paint). `h` came from
dividing an **assumed** 3.5 m lane by a measured paint separation. `f = f·h/h` closed the loop and
was then checked against the lens bound. `R-2026-09-15-seam` retracts the middle step — the
separations were a bank, a seam and a gravel apron, never the lane — so the loop can be run the
other way, with the lane width as the **free variable under test** instead of an input.

**MEASURED.** The near-band lateral histogram gives `lane/h = 1.873`, and that ratio is **free of
the focal**: with `x = f·h/(v−v_h)`, the `f` in `y = −(u−u₀)·f/x` cancels, leaving
`y = −(u−u₀)·h/(v−v_h)`. Against the row-flow `f·h = 2431` and the lens bound `f ≥ 1442` (26 mm
equivalent at 1920 px; **EIS can only crop IN**):

| W | h = W/1.873 | f = 2431/h | crop |
|---|---|---|---|
| 3.00 m | 1.602 | 1517 | 1.05× |
| 3.25 m | 1.736 | 1401 | **0.97× ⛔** |
| 3.50 m | 1.869 | 1301 | **0.90× ⛔** |

⇒ **W ≤ 3.16 m.** A 3.5 m lane would need the recorded image to be wider than the lens.

**ROOT-CAUSE CLASS — AN ASSUMED CONSTANT THAT WAS NEVER PROMOTED TO A MEASUREMENT, INSIDE A LOOP
THAT COULD HAVE TESTED IT.** The 3.5 m was reasonable (it is the French/Spanish motorway standard)
and it was labelled as an assumption in §22. What went wrong is that it then sat in the denominator
of every `h` for three parts of the document while an *independent* bound on the same quantity —
the lens — was being applied to the OUTPUT of the chain rather than being propagated back to the
input. **When an assumption and an independent constraint bracket the same unknown, solve for the
unknown; do not use the constraint only to audit the answer.**

⚠️ **The adopted values survive their own justification being retracted** — `h = 1.586, f = 1533`
implies `W = 2.97 m`, inside the admissible band, and the frames show a contraflow/roadworks
cross-section where 2.75–3.0 m is normal. **Not excluded, and consistent** — which is a weaker
claim than "confirmed" and is the one the evidence supports.

## `R-2026-09-15-burstiness` — a dash detector that measured my own frame sampling

**WITHDRAWN before use:** the occupancy/Fano-factor discriminator intended to separate the *dashed*
right-hand lane line from the *continuous* gravel apron.

**MEASURED:** Fano **15–75 in every lateral bin**, occupancy 2–79 % in every bin, **including the
left SOLID line** (+1.65 m: occupancy 51 %, Fano 25.6). It does not discriminate at all.

**ROOT CAUSE:** the 240 frames are sampled ~**9 s apart** for coverage. Between two samples the road
section, sun, exposure, curvature and the car's lateral position have all changed, and that variance
swamps the dash period by an order of magnitude. **The statistic measured the sampling scheme, not
the road.** It is only meaningful on *consecutive* frames.

**ROOT-CAUSE CLASS — A STATISTIC COMPUTED OVER THE WRONG SCOPE**, fifth costume, after `df` on a
pod, `free`/`tegrastats` on Thor, cgroup `usage_in_bytes`, and `ridge_cols`' whole-row threshold
(`R-2026-09-15-scope`). ⇒ **Before reading a temporal statistic, ask what the sampling interval is
relative to the phenomenon.** A 9 s stride cannot see a structure with a ~1 s period.

---

## `R-2026-09-15-longitudinal` — `project_ground`'s x is from the REAR AXLE, and I fed it camera ranges

**WITHDRAWN:** `R-2026-09-15-lanewidth` in full, and with it §97's *"the lens caps the lane at
W ≤ 3.16 m, so the 3.5 m assumption is refuted"*. **The conclusion INVERTS: the cap is W ≤ 3.93 m
and a 3.5 m lane is comfortably admissible** (`h = 1.500 m, f = 1620 px, crop 1.12×`). Also
withdrawn: §92's left boundary at **+1.62 m** (true **+2.05 m**) and §94's horizon scan in its
entirety.

**THE BUG.** `RR.NOMINAL` carries `longitudinal: 2.1`, and `CameraModel.t_v = [longitudinal_m,
lateral_m, height_m]` is the camera's position **in the vehicle frame**. So `project_ground`'s `x`
is measured from the **trajectory origin (rear axle)** and `project_ground([[10, y]])` sits
**7.80 m ahead of the camera**. Every probe that inverted a row to a range used
`x = f·h/(v − v_h)` — the range from the **camera** — and handed it to `project_ground` as a range
from the **rear axle**, so the lateral scale applied was `f/(x − 2.1)` where `f/x` was needed:
**−27 % at 8 m, −21 % at 10 m, −12 % at 20 m, −7 % at 30 m.**

**ROOT-CAUSE CLASS — TWO FUNCTIONS THAT SHARE A VARIABLE NAME AND NOT ITS ORIGIN.** Both call it
`x` and both mean "metres forward"; they disagree about *forward of what*. Nothing type-checks a
datum. ⇒ **When composing a closed-form inversion with a library projection, verify the round trip
numerically before trusting it** — one `project_ground(x)` → read the row → invert → compare would
have caught this on day one, and it is now the standard check.

**⭐ AND THE ERROR IS RANGE-DEPENDENT, WHICH IS WHY IT WAS EXPENSIVE.** A constant scale error would
have been caught by any sanity check against a known width. This one shrinks with range, so it
**manufactures a drift** — and §94's horizon estimator works by looking for exactly such a drift and
attributing it to `v_h`. It injected ~0.28 m of spurious drift, the same order as the signal.
**§94 measured this bug and reported it as an unresolved horizon.** Same family as the wrong-scope
statistics of `R-2026-09-15-scope` and `R-2026-09-15-burstiness`: the probe answered a different
question than the one asked.

**HOW IT WAS CAUGHT — a disagreement, not a review.** Two probes read the *same* left line as
+1.62 m and +2.01 m. A 0.39 m gap on one feature is not noise. ⇒ **Measuring one quantity two ways
is worth more than measuring two quantities once**, and this is the second time in two days that a
cross-check, not an audit, found the defect.

**WHAT SURVIVES.** Anything that never called `project_ground`: `clear_L`, the render-less yaw scan
and §87's *"rendered −5.35 vs optimum −5.10"*, the flat 1.12–1.19 m profile, the row-flow `f·h`.
**The renderer is unaffected** — it works in vehicle coordinates end to end, and its
self-consistency check (drawn ribbon vs projected ribbon) passes at **±0.04 m** across 10–30 m.

---

## `R-2026-09-15-missingfield` — `.get(key, default)` on a schema I never enumerated

**WITHDRAWN:** the label *"straight frames only (|yaw rate| < 1 °/s)"* on §102's corridor-placement
table, and the yaw-rate stratification in the first run of `where_is_the_corridor --per-frame`.
The numbers in §102 stand — they are simply over **all** frames, not straight ones.

**THE BUG.** These trajectory records carry `frame · pts_s · speed_ms · steer_wheel_deg ·
steer_valid · standstill · t · x · y · yaw · v · pos_sigma`. There is **no `yaw_rate_dps`**, so
`r.get("yaw_rate_dps", 0.0)` returned `0.0` for every frame: the filter passed everything and the
stratification put **228 of 228 frames into one band**.

**⚠️ IT HAD ALREADY ANNOUNCED ITSELF AND I READ PAST IT.** The probe printed *"2156 straight frames
… out of 2216"* — **97 % of a recording on a visibly bending road classified as straight**. ⇒ **A
filter that rejects almost nothing is a filter that is not running.** Print the reject count, and
disbelieve a pass rate near 100 %.

**ROOT-CAUSE CLASS — A DEFAULT SILENTLY SUBSTITUTED FOR A FACT.** Same family as
`R-2026-09-15-longitudinal` (a variable that means something different in the function next door)
and `R-2026-09-15-scope` (a statistic over the wrong scope): in each, the code ran, returned
plausible numbers, and answered a question nobody asked. ⇒ **`.get(k, default)` is only admissible
on a schema you have enumerated.** Enumerate it once, in the probe, and fail loudly on a missing
key rather than defaulting.

**THE REPLACEMENT IS BETTER THAN THE ORIGINAL INTENT.** `steer_wheel_deg` is real and measured, and
the records carry the future path (`x`, `y`) — so `y` interpolated at a range is not a *proxy* for
why the ribbon leaves the lane, it **is** the ribbon's predicted lateral there. That substitution is
what produced §109's `r = −0.789`, which settled the symptom.

---

## `R-2026-09-15-acflag` — an autocorrelation that found the detector, not the road (caught by its own control)

**WITHDRAWN before it produced a result:** the first consecutive-frame dash test. It flagged
**every** lateral bin as dashed paint — **including the SOLID left line** — all at **lag 6, which
was the scan's own lower bound**.

**ROOT CAUSE.** Consecutive frames 0.2 s apart are nearly identical, so the **detector's own
temporal smoothness** dominates the autocorrelation at short lags and is indistinguishable from a
period. High-passing the count series (subtract a 9-frame moving average) and excluding lags below
any physical dash cycle fixes it; the control then passes cleanly (solid line acf **+0.12**, gravel
**+0.13**) and the real signal appears at a single 0.2 m-wide location in **all three** independent
stretches.

**⭐ THE CONTROL IS WHY THIS COST MINUTES INSTEAD OF DAYS.** It was declared in the docstring before
the first run — *"the LEFT line is solid, so it must show no periodicity; if it does, the instrument
is manufacturing it and nothing here is admissible"* — so the failure announced itself instead of
being published. Every retraction above was found the other way round: by a downstream
contradiction, days later. ⇒ **A discriminator must be given something it should NOT fire on, and
the negative control must be named in advance.**

**⚠️ FOURTH BOUNDARY SOLUTION IN THIS WORK** — §94's first horizon pass, `--scan`'s default, the
bonnet symmetry band, and now this. ⇒ **A scan whose optimum sits at an end of its range is not a
measurement.** It is now checked explicitly wherever a scan runs, and the range is a flag rather
than a literal.

**ROOT-CAUSE CLASS — A STATISTIC THAT MEASURES THE INSTRUMENT.** Same family as
`R-2026-09-15-burstiness` (measured the 9 s sampling stride) and `R-2026-09-15-scope` (a threshold
over the wrong scope). In all three the code ran, returned plausible numbers, and described the
apparatus rather than the world.

---

## `R-2026-09-15-oneside` — I measured the easy side, and a one-sided instrument cannot see a placement error

**WITHDRAWN:** §114's *"the corridor's geometry is verified end to end"* as to **lateral
placement**; §103's bonnet-symmetry mount offset (−0.05…−0.11 m); and §117's closure of the `h`/`f`
split.

**THE DEFECT IS REAL.** The drawn corridor sits **0.28 m right of the lane centre** (frame-cluster
bootstrap CI [0.26, 0.29], 584 frames): clearance **+1.09 m left, +0.51 m right**. On the frame
Sayed showed, the right clearance is **+0.03 m at 9 m** — the edge is on the paint. The correction
is `--lateral-offset −0.126 → −0.41 m`, and **the pipeline's own default was −0.35**: the override
was the error.

**ROOT CAUSE 1 — A ONE-SIDED INSTRUMENT.** Every probe in Parts 22–23 measured the **LEFT** line,
because it is solid and clean. But a single boundary yields a *clearance*, and a clearance is
consistent with **any** placement once the car is allowed to be off-centre — which is exactly the
escape hatch I used. ⇒ **A placement error is only observable from BOTH boundaries.** Measuring the
side that measures well is not measuring.

**ROOT CAUSE 2 — A DASHED FEATURE HANDED TO A NEAREST-NEIGHBOUR SELECTOR.** Whenever a dash had a
gap at the sampled range, "nearest paint to the right" returned the **shoulder edge line at −2.5 m**
— and it did so preferentially in the frames where the ribbon was closest to the paint. A reported
metre of clearance that did not exist. Same class as `R-2026-09-15-seam`, fourth occurrence: **a
selection step handed an incomplete feature silently returns the next thing out.** The fix is a
DECLARED GATE (the right boundary is within 2.2 m; beyond is shoulder), after which the lane width
stabilises at 3.40 m ± 0.25 instead of ranging 2.5–4.4 m.

**⭐ THE EVIDENCE WAS PUBLISHED AND I EXPLAINED IT AWAY.** §116/§117 reported the left boundary at
+2.05 m and the right at −1.10 m. Those cannot both be right if the car drives between the markings
— they differ by 0.95 m. I attributed the asymmetry to the driver. **The discriminating input was
never in the data: where the car actually sits in its lane.** Sayed supplied it in one sentence.
⇒ **When a measurement admits two readings and only an outside fact separates them, go and get the
outside fact** — do not pick the reading that leaves the model intact.

**⚠️ AND THE SOFT NUMBER SHOULD HAVE BEEN INADMISSIBLE, NOT SOFT.** §103 was published with three
warnings on its face: best correlation 0.68, bands disagreeing in sign, one running to a scan
boundary. I wrote *"not precise enough to correct it, but decisive on what mattered: the mount
offset is small."* **It was not small.** A quantity that weakly determined cannot be decisive about
anything, and calling it so is how a known-bad number became load-bearing.

---

## `R-2026-09-15-nearclip` — the bonnet clip was expressed in the rear-axle frame (second frame-mismatch in two days)

**THE DEFECT.** `viz.draw_trajectory_on_image`'s `near_clip_m` exists to stop the ribbon being drawn
where the bonnet hides the road — its docstring says so. It is applied as `s_fwd >= near`, and
`s_fwd` is arc length from the **TRAJECTORY ORIGIN (rear axle)**, while "under the bonnet" is a fact
about the **LENS**, which sits `longitudinal_m` = 2.10 m forward. So `near_clip_m = 4.0` started the
ribbon **1.9 m ahead of the lens**, against a bonnet that hides the road to **6.37 m**.

**MEASURED:** the ribbon is drawn down to source row **1078** while the road ends at row ~830 —
about **250 rows, a quarter of the frame**, painted on sheet metal at the ribbon's widest point,
immediately beside the visible shoulder. That is what Sayed has been reporting as *"the trajectory
leaves the road"*, and no lateral correction could fix it because the geometry there was never
wrong: those pixels should not have been drawn at all.

**ROOT-CAUSE CLASS — A QUANTITY DOCUMENTED IN ONE FRAME AND APPLIED IN ANOTHER.** Second instance in
two days after `R-2026-09-15-longitudinal`, and the failure mode is identical: two frames, one
variable name, nothing that type-checks a datum. ⇒ **Any length compared against a trajectory
arc-length or a `project_ground` x is in the REAR-AXLE frame; any length describing what the camera
can see is in the LENS frame. State which, at the point of use.**

⚠️ **THE DOCSTRING WAS RIGHT AND THE CODE WAS WRONG, WHICH IS WHY IT SURVIVED.** Anyone reading
`near_clip_m`'s documentation would conclude the bonnet case was handled. The prose asserted an
intent the implementation never delivered, and prose is not checked. *(Same shape as the
`MODEL_REGISTRY` rule that exists because prose lied to us.)*

## `R-2026-09-15-screenshot` — three wrong diagnoses read off compressed screenshots

**WITHDRAWN before acting on it:** a far-field yaw error, inferred from pixel positions measured on
Sayed's screenshot, which I was about to chase by re-opening the yaw.

Tracing the ribbon's own edges out of the render instead showed them converging at source column
**812** against the calibration's `cx + f·tan(yaw)` = **816** — i.e. **the ribbon is drawn exactly as
specified**, and there is no yaw error to find. Earlier in the same session, screenshot-derived pixel
readings also produced a phantom "ribbon 2.3× too wide relative to the lane" and a phantom right-hand
boundary at −1.0 m.

**ROOT CAUSE.** A screenshot is scaled, re-compressed, cropped and of unknown origin; recovering a
source column from it compounds three uncertain scale factors, and the result is confidently wrong
rather than noisy. ⇒ **Locate the frame in the source, render it at full resolution, and measure it
there.** A screenshot is evidence that something is wrong and evidence of *where to look* — it is
never a measurement.

---

## `R-2026-09-16-yawnotlateral` — I fitted a YAW error with the LATERAL parameter, over a 5 m window

**WITHDRAWN:** Part 25's `--lateral-offset −0.41` and §119's diagnosis of *"the ribbon sits 0.28 m
right of lane centre"* **as a lateral defect**. The offset is real but it is **range-dependent** —
`offset = −0.411 + 0.0438·x` on the v3 render, i.e. **2.51° of yaw**, reaching **+1.34 m at 40 m**.
Also withdrawn: §87's *"the delivered render's yaw is right"*.

**ROOT CAUSE — A LEVEL AND AN ANGLE ARE THE SAME THING OVER A SHORT LEVER.** Every placement
measurement I made ran over **7–12 m**. Across a 5 m window a constant offset and a 2.5° rotation
are indistinguishable to within the noise, so the fit assigned all of it to the parameter I was
looking at. The "correction" nulled the error at 10 m and **made it worse at every longer range**,
which is exactly what Sayed kept reporting after each render. ⇒ **Never fit a placement parameter
without varying the range. The slope IS the second parameter, and if you do not measure it you have
silently assumed it is zero.**

**⭐ THE DIAGNOSTIC THAT WORKS IS `clear_L` vs RANGE.** Parallel means FLAT — no lane width, no
right-hand line, no horizon. v3 gave +1.40° (⇒ −6.75°), v4 gave −0.38° (⇒ **−7.01°**).

**⛔ AND THE ANSWER WAS MEASURED CORRECTLY BEFORE ANY OF THIS.** `lane_calib` reported **−7.01°** on
this recording and the pipeline rejected it against an FOE that had failed to fit — a bug this repo
already documents in `tests/test_trajrecon_yaw_gate.py`. Four further independent estimates (VP fit
−6.05 [−6.28, −5.83]; pair-Hough −6.20…−6.51; road-VP −6.26; `clear_L` −6.75/−7.01) all landed
between −6.0 and −7.0. **The render used −5.35, and I withdrew the pair-Hough estimate (§88)
specifically because it disagreed with it.**

⚠️ **THE SURVIVING ESTIMATE WAS THE CONDITIONAL ONE.** §87's single-line read-out evaluates a fitted
line *at the assumed horizon row*, so it measures the yaw **given** the horizon — and the horizon is
the one parameter still unresolved. It agreed with the shipped value because it was anchored to the
same assumption. ⇒ **When one estimate agrees with the status quo and four disagree, the burden is
on the agreeing one**, and the first question is what it shares with the thing it is confirming.

---

## `R-2026-09-19-greenhue` — "19.8 % of frames leave the road" was ROADSIDE FOLIAGE

**WITHDRAWN:** the per-frame result *"19.8 % of v6 frames have a minimum margin below zero"*, and
every number in the distribution that came with it (`p0 −16.30 m`, `p1 −3.22`, `p5 −0.32`), plus the
"worst frames" list `47, 165, 162, 155, 169, 374`. All are artifacts. Inspected at full resolution,
**every one of those frames has the ribbon squarely between the painted lines.**

**ROOT CAUSE — A DETECTOR WITH NO BRIGHTNESS GATE LOCKED ONTO VEGETATION.** `corridor_edges` selected
the drawn ribbon by hue alone (`g > r+20 & g > b+20`). MEASURED on the v6 render, composite frame 165
row 340: that test returned columns **834–845 at BGR (28,99,77) / (0,64,42)** — dark foliage on the
bank — while the ribbon at the next scanned row sits at **470–521 in pale (206,229,208)**. Two
distinct failures followed, and **both inflate a margin in metres**:

- the foliage **alone** was returned as a 16 px "ribbon"; scaled by the known 1.855 m width that is
  **0.112 m/px, 20× the true scale at that row**, so an ordinary pixel distance became −6.72 / −8.08
  / **−10.68 m**;
- where ribbon and foliage share a row, min/max over green spans **both**: row 360 returned
  (470, 835) for a ribbon ending at 521 — a 547 px "1.855 m", collapsing the scale to 0.003 m/px.

**CLASS: `R-2026-09-15-seam` again** — a detector rewarded for locking onto continuous non-target
structure the test could not exclude. ⇒ **A colour test that selects a DRAWN overlay must gate on the
overlay's own brightness, not only its hue**; the drawn edge is pale (all channels > 190) and every
natural green in frame is dark. Fixed with `v_min=150` plus a contiguity gate.

⚠️ **AND THE HEADLINE IT CONTRADICTED WAS ALSO WRONG, IN THE OTHER DIRECTION.** The "97.9 % on-road"
it was called out against is a **mean over (frame, range) SAMPLES**; Sayed looks at **one frame**, and
a frame is bad if ANY part of the ribbon leaves the road. **A sample mean and a per-frame minimum are
different questions** and I reported the one that flattered the render. Same family as the
`overlapping_holdout_se` rule in `CLAUDE.md`: **the estimator is part of the claim.**

---

## `R-2026-09-19-hsvshadow` — the drivable mask called SHADOWED ASPHALT "not road"

**WITHDRAWN:** `road_containment.drivable_mask`'s HSV test `S < 35 & V > 60`, and with it the
**14.0 %** bad-frame rate it produced for v6 and the per-range profile that appeared to show residual
yaw (`+0.36 m` at 10 m decaying to `−0.05 m` at 40 m). Re-measured with a chromaticity mask the same
calibration gives **4.0 %** and a **FLAT** profile (+0.49 … +0.26), i.e. no residual yaw at all.

**ROOT CAUSE — HSV SATURATION IS NOT A COLOURFULNESS MEASURE FOR DARK PIXELS.** Shadow on this road
is lit by sky, so it is blue, and `S = (max−min)/max` makes a dark blue-grey pixel read as highly
saturated. MEASURED frame 1860: shadowed asphalt BGR (98,79,58) → **S = 104**, against a threshold
written for sunlit asphalt (S = 8). The six worst-scoring frames in the recording were frames failed
on their own shadows. The same test was **accepting** the concrete barrier, padding the right margin.

**THE FIX IS A COLOUR SPACE, NOT A THRESHOLD.** In CIELAB, shadow moves L* and leaves chromaticity
alone. MEASURED over hand-placed regions of frame 1860 (n = 4.4k–68k), kept by `|a*| < 8, −22 < b* < 6`:
sunlit asphalt 99.8 %, **shadowed asphalt 100.0 %**, lane paint 96.5 %, vegetation bank 0.7 %,
concrete barrier 0.0 %, sky 0.0 %.

**CLASS: the `df` / Thor-`free` / cgroup-`usage_in_bytes` family** — a probe that answers a different
question than the one asked, and therefore looks like an answer.

---

## `R-2026-09-19-roadnotlane` — "on the road" is NOT the specification; "between the markings" is

**WITHDRAWN as the deciding metric:** `road_containment.py`, and the reading that v6 at **4.0 % bad
frames** means the calibration is correct. It is not wrong, it is **permissive in exactly the
direction of the error**.

**ROOT CAUSE — A TWO-LANE CARRIAGEWAY.** The drivable surface continues across the left-hand line for
another ~3.5 m, so a ribbon drifting toward the adjacent lane **never leaves the mask and never costs
a point**. Sayed's sentence contains the specification and I scored only its first half: *"the
trajectory still [is] leaving the road, **knowing that ego [is] driving between the road markings**."*

**MEASURED on the frame he sent** (source 908, t = 33.63 s), scale `h/(v−v_h)`, no other calibration:
clearance to the **left** line `+0.43 m` at 10 m and `+0.31 m` at 12 m, to the **right** line
`+1.29 m` and `+1.39 m`; lane 3.59 m, so a centred 1.855 m car should clear **0.87 m each side**. The
ribbon is **0.44 m left of lane centre at 10 m and 0.55 m at 12 m** — both clearances positive, so
road-containment sees nothing, and **a bias that grows with range is residual yaw**.

⇒ `lane_containment.py`: the quantity is the ribbon's offset from the **LANE CENTRE**, whose correct
value is known to be **zero** because the car was driving between the markings. Same family as the
C6 confound — **scoring a marginal that the specification never asked about.**

⚠️ **A SECOND DEFECT, CAUGHT BY A CONTROL, IN THAT METRIC'S FIRST VERSION.** It searched for paint
strictly OUTSIDE the ribbon edges, so a sample where the ribbon *sits on a line* was **dropped for
want of a detection instead of recorded as a crossing** — it reported `cross 0.0 %` for every arm in
the panel, including the first shipped render whose ribbon is over a metre off centre at 30 m. **A
metric structurally incapable of returning a failure is not measuring the failure, and "0.0 %" reads
like a pass.** Anchoring the two searches on the ribbon's CENTRE gives v1 8.2 % and v6 4.0 %.

---

## `R-2026-09-20-horizon472` — the horizon was 9 px out, and the metric that chose it is blind to it

**WITHDRAWN:** `--horizon-row 472`, used for the v6 and v7 renders. **MEASURED** value is
**463**, with a broad interior minimum over 460–464.

**ROOT CAUSE — I CHOSE IT WITH A METRIC THAT CANNOT SEE IT.** `road_containment` is degenerate in
the horizon (its own §137 records the ribbon/road width ratio falling 0.197→0.176 as the horizon
rises 440→500 **while the score rises**), and `lane_containment` scores a *difference* of
clearances, in which a scale error cancels exactly. Both return "fine" for a 9 px horizon error.

**THE SIGNATURE THAT DOES WORK, AND IT NEEDS NO KNOWN LANE WIDTH:** the lane is the same width at
8 m and at 30 m; the lateral scale is `h/(v−v_h)`; so a wrong `v_h` makes the MEASURED width trend
with range, and the horizon that makes it **flat** is right. The width's *value* never enters, so
`f` and `h` drop out. At 464 the per-range widths are 3.610 3.659 3.661 3.643 3.634 3.595 3.659
3.656 — **sd 0.024 m over a 3.75× range span**.

**WHAT THE ERROR DID ON SCREEN.** Drawn width ratio `(v−463)/(v−472)` = **1.037 at 10 m and 1.111 at
30 m** ⇒ the ribbon **flares outward with range**, edges ~0.10 m further out each side at 30 m. **A
symmetric flare does not move the centre**, so the centre-offset metric is blind to it — while a
flare is exactly what "the trajectory is leaving the road" looks like.

**CLASS: the same one three times in this part** — `R-2026-09-19-roadnotlane` (scored asphalt, not
lane), the `cross 0.0 %` selection defect (could not return a failure), and now this (blind to a
symmetric flare). ⇒ **Before trusting a metric, ask what error it CANNOT see, and check whether the
complaint lives there.** A metric's blind spot is part of its specification.

⚠️ **`v_h = 463` is an EFFECTIVE horizon for this recording, not a mounting pitch.** A constant road
grade over 8–30 m acts as a horizon offset and is absorbed here — correctly, since the goal is to
land the drawing on *this* road. It must not be quoted as a camera geometry fact.

---

## `R-2026-09-20-nearestridge` — "the car is 0.75 m left of centre" was the DASHED line wandering

**WITHDRAWN:** every per-frame lane-centre number in the frame-908/932 investigation — *"the car is
+0.75 m off the lane centre"*, *"+0.62 m"*, the frame-932 cross-section reading of a left line at
**+1.0 m**, and the inference that the ribbon still sat left of centre under v8. Corrected reading:
**the ribbon is centred to within ~0.09 m** in frame 932 (ribbon 430–610 px in a lane running
330–730 px; ribbon centre 520, lane centre 530).

**ROOT CAUSE — TWO DETECTOR FAULTS, BOTH BIASING THE SAME WAY.**

1. **The right boundary is DASHED.** Between dashes there is no paint, so a nearest-ridge search
   returns the next continuous thing outward — the shoulder edge line or the gravel. The pooled
   histogram shows it plainly: the right side has **three** peaks (−2.18, −1.73, −1.43) where the
   solid left side has **one** (+1.87→+2.02). A right boundary biased outward moves the computed
   lane centre right, which reads as **the car being left**.
2. **`max(left)` picks the NEAREST ridge, not the line.** Any bright structure inside the lane wins.
   Drawn on the image, the detected "left line" sat visibly inside the carriageway; drawn back at the
   measured 1.03 m clearance it landed **left of the real paint**. True clearance ≈ **0.79 m**, which
   is what a centred 1.855 m car has in a 3.5 m lane (0.82 m).

**CLASS: `R-2026-09-15-seam` for the THIRD time**, and `CLAUDE.md` already warns of exactly this
case — *"the ego lane's right boundary is dashed ... a peak-picker will always prefer the continuous
structure beyond it."* **I re-derived the failure instead of reading the rule that names it.**

⚠️ **THE LANE-WIDTH GATE DID NOT CATCH IT AND CANNOT.** A false right line at −2.4 m with a false
left line at +1.0 m gives 3.4 m, comfortably inside the 2.9–4.3 m window. **A plausibility gate on a
DERIVED quantity does not validate the two measurements it was derived from.**

⭐ **WHAT SURVIVES, AND WHY IT WAS NEVER AT RISK.** The v8 calibration stands. Its evidence is the
**slope** of the clearance to the SOLID left line against range — v6 **−1.01 deg (R² 0.94)**, v8
**−0.15 deg (R² 0.29)** over 200 straight frames — and a constant offset in line identification
cannot change a slope. The scale is confirmed independently by the **painted line's own width:
0.156 m measured against the 0.15 m European standard (4 %)**, constant over 8–20 m, which also
re-confirms the horizon, since a wrong one makes that width drift with range.

⇒ **Rule: for this recording, measure against the SOLID line only.** The dashed side may be used for
a width, never for a boundary position in a single frame.

---

## `R-2026-09-24-constantyaw` — "v8 is geometrically correct" — no constant yaw can be, on this clip

**WITHDRAWN:** the conclusion reported to the PI on 2026-09-20 that *"v8 is geometrically right"* and
*"the ribbon is centred to within ~0.09 m"* in frame 932, and `R-2026-09-20-nearestridge`'s "corrected
reading" that rests on it. **The PI was right both times he said the trajectory leaves the lane.**

**WHAT IS TRUE, MEASURED 2026-09-24.** Both lane lines fitted as WHOLE Hough lines — drawn on the frame
and checked to sit on the paint before any number was used — on frame 932 meet at column 834; the drawn
ribbon heads for column 787. The ribbon is rotated **1.75 deg left of the lane** and its left edge
crosses the solid line at ~20–30 m, exactly as reported. Over the clip, on gated straight frames, the
lane's vanishing point **walks ~80 px (≈3 deg of yaw)**: column ~751 at t 0–10 s, ~830 at 40–50 s,
lag-1 autocorrelation +0.64. It tracks **time** (r −0.41), not steering (r +0.09). The row drifts too,
458–490 px. **Electronic stabilisation moves the crop, so the effective camera moves during the clip.**

**ROOT CAUSE — THREE LAYERS.**
1. **A constant-parameter model on a time-varying camera.** EIS was operator-confirmed on in Part 6 and
   named in §2 as *"the single biggest threat ... the one assumption the whole method rests on"*, and
   §1041 records it as *"not measured"*. It was never measured until now. Every constant yaw fitted a
   **pooled** statistic that averages a drifting quantity: v6's −7.75 matched the first 30 s, v8's
   −6.40 sits between, and the 30–50 s stretch the PI kept sending wants ≈ −4.9.
2. **Pooled evidence was used to overrule a specific complaint.** "Median offset −0.04 m over 333
   frames" and "clearance flat over 200 frames" are true of the POOL and false of the STRETCH. A pooled
   statistic cannot rebut a claim about a particular moment when the quantity drifts in time.
3. **The "centred to 0.09 m" reading was an eyeball estimate from a screenshot**, the exact failure
   `R-2026-09-15-screenshot` exists to prevent, and it was used to retract a roughly-correct number.
   The per-row detector's "+0.75 m" was contaminated, but it was closer to the truth than the
   eyeball that replaced it.

**CLASS: a pooled statistic answering a question about a subset** — same family as the sample-mean vs
per-frame-minimum error in `R-2026-09-19-greenhue`, now in the time dimension. ⇒ **When the PI reports
a failure at a specific moment, test for time-dependence BEFORE citing a pooled number against him.**
