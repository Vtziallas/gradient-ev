"""Digital-twin correction: Kalman-filtered calibration + display smoothing contract.

The smoothing contract (<= 0.5 %/s, 3 s consistency) is a product guarantee
(EnergyEngine.md §4); its tests are unwaivable.
"""
from __future__ import annotations

import math


class KalmanCalibration:
    """1-D Kalman filter on log(calibration factor)."""

    def __init__(self, q: float = 1e-5, r_default: float = 0.02) -> None:
        self._x = 0.0            # log-space state
        self._p = 0.01
        self._q = q
        self._r_default = r_default

    @property
    def factor(self) -> float:
        return math.exp(self._x)

    def update(self, observed_ratio: float, r: float | None = None) -> float:
        z = math.log(max(observed_ratio, 1e-6))
        r_eff = self._r_default if r is None else r
        self._p += self._q
        k = self._p / (self._p + r_eff)
        self._x += k * (z - self._x)
        self._p *= 1.0 - k
        return self.factor


class DisplaySmoother:
    """Slew-limited display value with a consistency gate against transients."""

    DEADBAND = 0.05

    def __init__(self, max_slew_pct_s: float = 0.5, consistency_s: int = 3) -> None:
        self._max_slew = max_slew_pct_s
        self._need = consistency_s
        self._shown: float | None = None
        self._streak = 0
        self._streak_sign = 0

    def update(self, target: float, dt_s: float = 1.0) -> float:
        if self._shown is None:
            self._shown = target
            return target
        delta = target - self._shown
        sign = 1 if delta > self.DEADBAND else (-1 if delta < -self.DEADBAND else 0)
        if sign == 0 or sign != self._streak_sign:
            self._streak = 1 if sign != 0 else 0
            self._streak_sign = sign
            return self._shown
        self._streak += 1
        if self._streak < self._need:
            return self._shown
        step = min(abs(delta), self._max_slew * dt_s)
        self._shown += math.copysign(step, delta)
        return self._shown
