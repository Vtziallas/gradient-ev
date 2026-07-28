import numpy as np

from gradient_energy.profile import compute_grade, next_summit_distance, smooth_elevation


def test_smoothing_removes_noise_but_preserves_ascent():
    rng = np.random.default_rng(42)
    s = np.arange(1000, dtype=np.float64) * 25.0
    clean = np.where(s < 12500, s * 0.05, 625.0)          # 5% climb then flat
    noisy = clean + rng.normal(0.0, 2.0, s.size)          # DEM noise ~2 m
    smoothed = smooth_elevation(noisy)
    ascent = lambda h: float(np.sum(np.clip(np.diff(h), 0, None)))  # noqa: E731
    assert abs(ascent(smoothed) - ascent(clean)) / ascent(clean) < 0.20
    assert np.max(np.abs(smoothed - clean)) < 5.0


def test_smoothing_flattens_bridge_spike():
    s = np.arange(200, dtype=np.float64) * 25.0
    h = np.zeros(200)
    h[100] = 40.0                                         # single-sample DEM artifact
    g = compute_grade(s, smooth_elevation(h))
    assert np.max(np.abs(g)) < 0.20                       # raw spike would be 1.6


def test_grade_forward_difference_and_clamp():
    s = np.array([0.0, 25.0, 50.0, 75.0])
    h = np.array([0.0, 1.25, 2.5, 40.0])                  # last step = 150% -> clamp
    g = compute_grade(s, h)
    assert g.shape == (4,)
    assert abs(g[0] - 0.05) < 0.02
    assert np.max(g) <= 0.25 + 1e-9
    assert g[-1] == g[-2]                                 # last repeats


def test_next_summit_distance():
    s = np.arange(9, dtype=np.float64) * 100.0
    h = np.array([0.0, 10, 20, 30, 25, 20, 30, 45, 40.0])  # local max @3, higher @7
    assert next_summit_distance(s, h, 0) == 300.0
    assert next_summit_distance(s, h, 4) == 300.0          # from idx4 -> summit @7
    assert next_summit_distance(s, h, 8) is None
