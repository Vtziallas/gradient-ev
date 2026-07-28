import numpy as np

from gradient_energy.model import integrate
from gradient_energy.types import DriverProfile, RouteSamples, TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route, hill_route


def test_flat_route_matches_closed_form():
    r = flat_route(n=400, speed_mps=25.0)                 # ~10 km at 90 km/h
    w = WeatherSamples.uniform(400)
    ctx = TripContext(start_soc_pct=80.0)
    res = integrate(r, w, MODEL3, ctx)
    # closed form: (F_roll + F_aero)*d/eta + P_aux*t, converted to Wh
    d = r.s_m[-1]
    t = d / 25.0
    f = 0.010 * (1850.0 + 75.0) * 9.80665 + 0.5 * 1.2245 * 0.23 * 2.22 * 625.0
    e_expected_wh = (f * d / 0.90 + 600.0 * t) / 3600.0
    assert abs(res.energy_used_kwh * 1000.0 - e_expected_wh) / e_expected_wh < 0.02
    assert res.soc_pct[0] == 80.0
    assert res.soc_pct[-1] < 80.0
    assert res.energy_regen_kwh == 0.0


def test_hill_regen_recovers_some_energy():
    r = hill_route(n=800)
    w = WeatherSamples.uniform(800)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    assert res.energy_regen_kwh > 0.5
    mid = res.soc_pct[400]
    assert res.soc_pct[-1] > mid                          # descent recovers SoC


def test_regen_recovery_never_exceeds_climb_cost():
    r = hill_route(n=800)
    w = WeatherSamples.uniform(800)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    assert res.soc_pct[-1] < res.soc_pct[0]               # round trip loses energy


def test_high_soc_suppresses_regen():
    # Pure descent from sample 0 (no preceding climb): with hill_route's climb-then-
    # descend shape, the climb alone drains a 99.5% start down to ~94% by the time
    # descent begins, and at grade 5%/20 m/s the regen demand (~12.6 kW) never nears
    # even the suppressed cap (~69 kW at 94%) -- so suppression would never engage and
    # this test would pass or fail independent of the mechanism it's meant to check.
    # A route that starts descending immediately keeps the entered start_soc in force
    # exactly when regen begins, so the suppression is actually exercised.
    n = 400
    s_m = np.arange(n, dtype=np.float64) * 25.0
    grade = np.full(n, -0.05)
    elevation_m = np.concatenate(([0.0], np.cumsum(grade[:-1] * 25.0)))
    r = RouteSamples(
        s_m=s_m, elevation_m=elevation_m, grade=grade,
        curvature_1pm=np.zeros(n), heading_deg=np.zeros(n),
        speed_limit_mps=np.full(n, 27.78), expected_speed_mps=np.full(n, 20.0),
    )
    w = WeatherSamples.uniform(n)
    hi = integrate(r, w, MODEL3, TripContext(start_soc_pct=99.5))
    lo = integrate(r, w, MODEL3, TripContext(start_soc_pct=60.0))
    assert hi.energy_regen_kwh < lo.energy_regen_kwh


def test_calibration_factor_scales_consumption():
    r = flat_route(n=400)
    w = WeatherSamples.uniform(400)
    ctx = TripContext(start_soc_pct=80.0)
    base = integrate(r, w, MODEL3, ctx)
    hot = integrate(r, w, MODEL3, ctx, DriverProfile(calibration_factor=1.10))
    assert abs(hot.energy_used_kwh / base.energy_used_kwh - 1.10) < 1e-6


def test_soc_never_negative_and_dt_shapes():
    r = flat_route(n=2000)
    w = WeatherSamples.uniform(2000)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=1.0))
    assert np.all(res.soc_pct >= 0.0)
    assert res.dt_s.shape == (2000,) and res.dt_s[-1] == 0.0
    assert res.e_wh.shape == (2000,) and res.e_wh[-1] == 0.0
