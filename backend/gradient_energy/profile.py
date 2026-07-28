"""Elevation profile conditioning: DEM noise removal, grade, summit lookup.

Smoothing choice per EnergyEngine.md: Savitzky-Golay preserves real grades while
killing single-sample DEM artifacts (bridges, tunnels).
"""
from __future__ import annotations

import numpy as np
from scipy.signal import savgol_filter


def smooth_elevation(elevation_m: np.ndarray, window: int = 11, polyorder: int = 3) -> np.ndarray:
    n = elevation_m.size
    if n < window:
        window = n if n % 2 == 1 else n - 1
        polyorder = min(polyorder, window - 1)
    if window < 3:
        return elevation_m.astype(np.float64)
    return savgol_filter(elevation_m.astype(np.float64), window, polyorder)  # type: ignore[no-any-return]


def compute_grade(s_m: np.ndarray, elevation_m: np.ndarray, clamp: float = 0.25) -> np.ndarray:
    dh = np.diff(elevation_m)
    ds = np.diff(s_m)
    g = np.clip(dh / ds, -clamp, clamp)
    g = np.append(g, g[-1])                     # len n; last repeats previous
    if g.size >= 5:                             # light second pass on grade itself
        g = savgol_filter(g, 5, 2)
        g = np.clip(g, -clamp, clamp)
    return g


def next_summit_distance(
    s_m: np.ndarray, elevation_m: np.ndarray, start_index: int, min_prominence_m: float = 2.0
) -> float | None:
    h = elevation_m
    n = h.size
    for i in range(max(start_index + 1, 1), n - 1):
        if h[i] >= h[i - 1] and h[i] > h[i + 1] and h[i] - h[start_index] >= min_prominence_m:
            return float(s_m[i] - s_m[start_index])
    return None
