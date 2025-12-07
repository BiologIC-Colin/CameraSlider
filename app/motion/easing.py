from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


def linear(u: float) -> float:
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    return u


@dataclass(frozen=True)
class CubicBezier:
    # Control points (x1, y1, x2, y2); start is (0,0) end is (1,1)
    p1x: float
    p1y: float
    p2x: float
    p2y: float

    def sample(self, u: float) -> float:
        """Return y for a given u in [0,1], solving x(u') = u, then y(u').

        Uses a small Newton-Raphson iteration with a fallback bisection.
        """
        if u <= 0.0:
            return 0.0
        if u >= 1.0:
            return 1.0

        # Precompute coefficients for cubic Bezier
        # Bx(t) = 3*(1-t)^2*t*x1 + 3*(1-t)*t^2*x2 + t^3
        # Derivative for NR
        def bx(t: float) -> float:
            mt = 1 - t
            return 3 * mt * mt * t * self.p1x + 3 * mt * t * t * self.p2x + t ** 3

        def by(t: float) -> float:
            mt = 1 - t
            return 3 * mt * mt * t * self.p1y + 3 * mt * t * t * self.p2y + t ** 3

        def dx(t: float) -> float:
            # derivative of Bx
            return (
                3 * (1 - t) * (1 - t) * self.p1x
                + 6 * (1 - t) * t * (self.p2x - self.p1x)
                + 3 * t * t * (1 - self.p2x)
            )

        # Initial guess t ~ u
        t = u
        for _ in range(6):
            x_t = bx(t)
            d = dx(t)
            if abs(d) < 1e-6:
                break
            t -= (x_t - u) / d
            if t < 0.0:
                t = 0.0
                break
            if t > 1.0:
                t = 1.0
                break

        # If not accurate, refine with bisection
        x_t = bx(t)
        if abs(x_t - u) > 1e-4:
            lo, hi = 0.0, 1.0
            t = u
            for _ in range(12):
                x_t = bx(t)
                if x_t < u:
                    lo = t
                else:
                    hi = t
                t = 0.5 * (lo + hi)
                if abs(x_t - u) <= 1e-5:
                    break

        return by(t)
