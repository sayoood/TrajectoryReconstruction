"""FrameSource must return frame i exactly on a variable-frame-rate MP4.

cv2.CAP_PROP_POS_FRAMES maps an index to a time with one average fps, so on VFR
video it lands on a neighbour -- the 2026-11-21 night render showed the image
12 frames away from its overlay.  Each synthetic frame carries its index as a
bright bar, so a wrong frame is unambiguous."""
import shutil
import subprocess

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")

N = 240
W, H = 320, 96


def _frame(i):
    img = np.zeros((H, W), np.uint8)
    x = 4 + (i % 100) * 3                  # position encodes i mod 100 ...
    img[10:50, x:x + 2] = 255
    y = 56 + (i // 100) * 12               # ... the row band encodes i // 100
    img[y:y + 8, 4:20] = 255
    return img


def _index_of(img):
    g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    col = g[10:50].mean(axis=0)
    x = int(np.argmax(col))
    row = g[56:H, 4:20].mean(axis=1)
    band = int(np.argmax(row)) // 12
    return band * 100 + int(round((x - 4) / 3))


@pytest.fixture(scope="module")
def vfr_video(tmp_path_factory):
    d = tmp_path_factory.mktemp("vfr")
    out = d / "vfr.mp4"
    # 33.3 ms frames, stretched to 40 ms for frames 81..199 (as at night)
    t = ("if(lte(N,81),N/30,if(lt(N,200),81/30+(N-81)*0.04,"
         "81/30+119*0.04+(N-200)/30))/TB")
    raw = b"".join(_frame(i).tobytes() for i in range(N))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray",
                    "-s", f"{W}x{H}", "-r", "30", "-i", "-", "-vf", f"setpts='{t}'",
                    "-fps_mode", "passthrough", "-enc_time_base:v", "1/90000",
                    "-video_track_timescale", "90000", "-c:v", "libx264", "-g", "48",
                    "-pix_fmt", "yuv420p", "-crf", "12", str(out)], input=raw, check=True)
    from trajlib.timesync import probe_video
    v = probe_video(str(out))
    assert len(v.pts) >= N - 1
    d = np.diff(v.pts)
    assert d.min() > 0.03 and d.max() > 0.038      # really variable, no duplicate stamps
    return v


def test_naive_index_seek_is_wrong_on_vfr(vfr_video):
    cap = cv2.VideoCapture(vfr_video.path)
    wrong = 0
    for i in (150, 190, 220):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, img = cap.read()
        wrong += ok and _index_of(img) != i
    cap.release()
    assert wrong >= 1          # the failure this module exists to avoid


def test_framesource_random_access_is_exact(vfr_video):
    from trajlib.frames import FrameSource
    rng = np.random.default_rng(0)
    idx = list(rng.integers(0, len(vfr_video.pts), 25)) + [0, len(vfr_video.pts) - 1, 199, 81]
    with FrameSource(vfr_video) as src:
        for i in idx:
            assert _index_of(src.get(int(i))) == int(i)


def test_framesource_sequential_and_strided(vfr_video):
    from trajlib.frames import FrameSource
    n = len(vfr_video.pts)
    with FrameSource(vfr_video) as src:
        for i in range(60, n, 7):              # forward hops (render with --video-stride)
            assert _index_of(src.get(i)) == i
        src.seek(100)
        for i in range(100, 130):              # seek once, then read()
            assert _index_of(src.read()) == i


def test_index_at_uses_pts_not_average_fps(vfr_video):
    from trajlib.frames import FrameSource
    with FrameSource(vfr_video) as src:
        for i in (10, 120, 199, 230):
            assert src.index_at(float(vfr_video.pts[i]) + 0.004) == i
        # the average-fps mapping is off by several frames at the end of the slow stretch
        assert abs(int(round(float(vfr_video.pts[199]) * src.fps)) - 199) >= 2


def test_realtime_repeats_keeps_wall_clock():
    from trajlib.frames import realtime_repeats
    # 30 fps with a stretch of 40 ms frames
    d = np.r_[np.full(100, 1 / 30), np.full(150, 0.040), np.full(100, 1 / 30)]
    t = np.r_[0.0, np.cumsum(d)]
    r = realtime_repeats(t, 30.0)
    assert len(r) == len(t) and r.min() >= 1           # nothing dropped
    assert abs(r.sum() / 30.0 - (t[-1] - t[0])) <= 1 / 30 + 1e-9   # duration kept (± one tick)
    # every output tick shows the frame current at that time
    shown = np.repeat(np.arange(len(t)), r)
    ticks = t[0] + np.arange(len(shown)) / 30.0
    assert np.all(t[shown] <= ticks + 1e-3)
    assert np.all(np.r_[t[1:], np.inf][shown] > ticks - 1e-3)
    # constant 30 fps input -> exactly one write per frame
    assert np.all(realtime_repeats(np.arange(300) / 30.0, 30.0) == 1)


def test_sync_decoder_emits_each_frame_once(vfr_video):
    """timesync pairs decoded frames with video.pts BY INDEX; a constant-rate decoder
    duplicates frames on VFR input (St2392: 16,191 emitted for 15,902)."""
    from trajlib.timesync import _iter_gray_frames
    n = sum(1 for _ in _iter_gray_frames(vfr_video.path, 64, 20))
    assert n == len(vfr_video.pts)
