"""Uniform frame access for an MP4 or a folder of extracted frames.

The 2025-08-11 session exists only as 2247 per-frame directories, not as a video
file, so anything that reaches for ``cv2.VideoCapture`` silently cannot run on
it.  That is how the lane and scale calibrations ended up working on the iPhone
recordings and not on the Android one.

Both access patterns matter and they have opposite costs: seeking is cheap for a
frame folder and expensive for an MP4, while sequential reading is the reverse.
This keeps the fast path for each -- ``seek`` then repeated ``read`` -- instead
of forcing one to emulate the other.
"""
from __future__ import annotations


class FrameSource:
    """``seek(i)`` then ``read()`` repeatedly; ``read`` advances by one frame."""

    def __init__(self, video):
        self.n = int(getattr(video, "nb_frames", 0))
        self.fps = float(getattr(video, "avg_fps", 0.0) or 0.0)
        self.width = int(getattr(video, "width", 0))
        self.height = int(getattr(video, "height", 0))
        self._folder = hasattr(video, "read_bgr")
        if self._folder:
            self._v = video
            self._i = 0
        else:
            import cv2
            import numpy as np
            self._cap = cv2.VideoCapture(str(video.path))
            fps = self._cap.get(cv2.CAP_PROP_FPS)
            if fps and fps > 0:
                self.fps = float(fps)
            pts = np.asarray(getattr(video, "pts", []), dtype=float)
            self._pts = pts if len(pts) else None
            self._next = 0            # index the next read() returns, when known
            self._pending = False     # a frame has been grabbed but not retrieved
            self._off = None          # pts - OpenCV timestamp, measured on first use
            if self._pts is not None and len(self._pts) > 1:
                self._tol = 0.5 * float(np.min(np.diff(self._pts)[np.diff(self._pts) > 0]))
            else:
                self._tol = 0.5 / max(self.fps, 1.0)

    # -- exact frame positioning for MP4 ------------------------------------- #
    # cv2.CAP_PROP_POS_FRAMES converts the index to a time with ONE average fps.
    # On a variable-frame-rate stream that lands on the wrong frame.  MEASURED on
    # the 2026-11-21 St2392 night recording (Galaxy S24 Ultra; frame intervals
    # 33.3 ms, stretched to 40 ms in the dark): a render built on it showed the
    # image 12 frames (0.4 s, ~10 m at 93 km/h) away from the overlay, and the
    # error changed abruptly, which played as jumps.  Here a frame is found by its
    # own PTS and confirmed by the decoder's timestamp before it is returned.
    def _ts(self):
        import cv2
        return self._cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

    def _calibrate_offset(self):
        import cv2
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        if not self._cap.grab():
            raise IOError("cannot decode the first frame")
        self._off = float(self._pts[0]) - self._ts()
        self._next, self._pending = 0, True

    def _seek_exact(self, i: int) -> None:
        import cv2
        if self._off is None:
            self._calibrate_offset()
            if i == 0:
                return
        target = float(self._pts[i])
        back = 1.0
        while True:
            t_set = max(0.0, target - self._off - back)
            self._cap.set(cv2.CAP_PROP_POS_MSEC, t_set * 1000.0)
            if not self._cap.grab():
                raise IOError(f"cannot decode near frame {i}")
            ts = self._ts() + self._off
            if ts <= target + self._tol or t_set == 0.0:
                break
            back *= 2.0                       # landed past it: start further back
        while ts < target - self._tol:
            if not self._cap.grab():
                raise IOError(f"stream ended before frame {i}")
            ts = self._ts() + self._off
        if abs(ts - target) > self._tol:
            raise IOError(f"frame {i}: decoder at {ts:.4f} s, wanted {target:.4f} s")
        self._next, self._pending = i, True

    def seek(self, i: int) -> None:
        i = int(i)
        if self._folder:
            self._i = i
            return
        import cv2
        if self._pts is None or not (0 <= i < len(self._pts)):
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, i)    # no PTS: best effort
            self._next, self._pending = None, False
            return
        if self._next is not None and i == self._next:
            return
        if self._next is not None and 0 < i - self._next <= 90:
            # short hop forward: decode through, exact by construction.
            # `cur` is the frame the decoder currently holds (grabbed or consumed).
            cur = self._next if self._pending else self._next - 1
            while cur < i:
                if not self._cap.grab():
                    raise IOError(f"stream ended before frame {i}")
                cur += 1
            self._next, self._pending = i, True
            return
        self._seek_exact(i)

    def read(self):
        """Frame at the current position as BGR, or None; advances by one."""
        if self._folder:
            if not (0 <= self._i < self.n):
                return None
            img = self._v.read_bgr(self._i)
            self._i += 1
            return img
        if self._pending:
            ok, fr = self._cap.retrieve()
            self._pending = False
        else:
            ok, fr = self._cap.read()
        if self._next is not None:
            self._next += 1
        return fr if ok else None

    def index_at(self, t_video: float) -> int:
        """Frame index whose PTS is nearest ``t_video`` (the same clock as
        ``VideoInfo.pts`` and ``SyncResult.frame_times``: t_session - t_video_start).

        Uses the per-frame PTS when known; ``t * fps`` drifts on variable-rate video."""
        if not self._folder and self._pts is not None:
            import numpy as np
            tt = float(t_video)
            j = int(np.searchsorted(self._pts, tt))
            j = min(max(j, 0), len(self._pts) - 1)
            if j > 0 and abs(self._pts[j - 1] - tt) <= abs(self._pts[j] - tt):
                j -= 1
            return j
        return int(round(float(t_video) * self.fps))

    def get(self, i: int):
        """Frame ``i`` exactly (by PTS for an MP4); cheap when ``i`` moves forward."""
        self.seek(i)
        return self.read()

    def release(self) -> None:
        if not self._folder:
            self._cap.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
        return False
