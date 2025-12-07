from __future__ import annotations

from typing import Callable, Iterable, List, Tuple

from .easing import linear, CubicBezier
from .models import MotionProfile, Keyframe


def _ease_fn(kf: Keyframe) -> Callable[[float], float]:
    e = kf.ease
    if e.type == "linear":
        return linear
    elif e.type == "cubic-bezier":
        x1, y1, x2, y2 = e.p  # type: ignore
        cb = CubicBezier(x1, y1, x2, y2)
        return cb.sample
    else:
        return linear


def sample_profile(profile: MotionProfile, dt: float = 0.01) -> Tuple[List[float], List[float]]:
    """Sample the motion profile into time and position arrays.

    - dt: sampling interval in seconds (default 10ms)
    Returns (times, positions_mm)
    """
    kfs = profile.keyframes
    times: List[float] = []
    pos: List[float] = []
    total_t = kfs[-1].t
    if total_t <= 0:
        total_t = 0.01

    seg_start_idx = 0
    t = 0.0
    while t <= total_t + 1e-9:
        # Find current segment
        while seg_start_idx < len(kfs) - 2 and t > kfs[seg_start_idx + 1].t:
            seg_start_idx += 1
        k0 = kfs[seg_start_idx]
        k1 = kfs[seg_start_idx + 1]
        u = 0.0 if k1.t == k0.t else (t - k0.t) / (k1.t - k0.t)
        u = 0.0 if u < 0.0 else (1.0 if u > 1.0 else u)
        f = _ease_fn(k1)  # easing stored on arrival keyframe
        y = k0.pos_mm + (k1.pos_mm - k0.pos_mm) * f(u)
        times.append(t)
        pos.append(y)
        t += dt

    # Ensure last sample is exactly last keyframe
    if times[-1] < kfs[-1].t:
        times.append(kfs[-1].t)
        pos.append(kfs[-1].pos_mm)

    return times, pos
