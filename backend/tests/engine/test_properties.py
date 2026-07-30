import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from gradient_energy.charging import optimize
from gradient_energy.model import integrate
from gradient_energy.speed import WeatherPoint, efficiency_band
from gradient_energy.types import ChargerCandidate, TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route, hill_route


@settings(max_examples=50, deadline=None)
@given(grade=st.floats(0.01, 0.12), speed=st.floats(10.0, 33.0))
def test_round_trip_never_gains_energy(grade: float, speed: float) -> None:
    r = hill_route(n=400, grade=grade, speed_mps=speed)
    w = WeatherSamples.uniform(400)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    assert res.soc_pct[-1] <= res.soc_pct[0] + 1e-9


@settings(max_examples=50, deadline=None)
@given(extra_kg=st.floats(0.0, 500.0))
def test_more_mass_never_cheaper_uphill(extra_kg: float) -> None:
    r = hill_route(n=200, grade=0.06)
    r2 = hill_route(n=200, grade=0.06)
    w = WeatherSamples.uniform(200)
    light = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    heavy = integrate(r2, w, MODEL3, TripContext(start_soc_pct=80.0, cargo_kg=extra_kg))
    assert heavy.energy_used_kwh >= light.energy_used_kwh - 1e-9


@settings(max_examples=30, deadline=None)
@given(wind=st.floats(0.0, 15.0))
def test_headwind_never_cheaper(wind: float) -> None:
    r = flat_route(n=200)
    calm = WeatherSamples.uniform(200)
    windy = WeatherSamples.uniform(200, wind_speed_mps=wind, wind_dir_deg=0.0)
    a = integrate(r, calm, MODEL3, TripContext(start_soc_pct=80.0))
    b = integrate(r, windy, MODEL3, TripContext(start_soc_pct=80.0))
    assert b.energy_used_kwh >= a.energy_used_kwh - 1e-9


def test_sample_spacing_invariance():
    fine = hill_route(n=1600, spacing_m=12.5)
    coarse = hill_route(n=400, spacing_m=50.0)
    w_f = WeatherSamples.uniform(1600)
    w_c = WeatherSamples.uniform(400)
    ctx = TripContext(start_soc_pct=80.0)
    a = integrate(fine, w_f, MODEL3, ctx)
    b = integrate(coarse, w_c, MODEL3, ctx)
    assert abs(a.soc_pct[-1] - b.soc_pct[-1]) < 0.3        # % SoC


@settings(max_examples=30, deadline=None)
@given(soc=st.floats(2.0, 99.0), grade=st.floats(-0.12, 0.12))
def test_soc_always_finite_in_bounds(soc: float, grade: float) -> None:
    r = hill_route(n=200, grade=abs(grade))
    w = WeatherSamples.uniform(200, temp_c=-15.0)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=soc))
    assert np.all(np.isfinite(res.soc_pct))
    assert np.all((res.soc_pct >= 0.0) & (res.soc_pct <= 100.0))


@settings(max_examples=100, deadline=None)
@given(
    grade=st.floats(-0.15, 0.15),
    curvature_1pm=st.floats(0.0, 0.02),
    speed_limit_kmh=st.floats(20.0, 130.0),
    headwind_mps=st.floats(-15.0, 15.0),
    temp_c=st.floats(-20.0, 40.0),
    rain_mm_h=st.floats(0.0, 5.0),
    snow=st.booleans(),
)
def test_speed_band_never_exceeds_speed_limit(
    grade: float, curvature_1pm: float, speed_limit_kmh: float, headwind_mps: float,
    temp_c: float, rain_mm_h: float, snow: bool,
) -> None:
    """UNWAIVABLE invariant: the recommended speed band must never exceed the
    posted speed_limit, under any weather/route/vehicle combination."""
    speed_limit_mps = speed_limit_kmh / 3.6
    wp = WeatherPoint(
        temp_c=temp_c, headwind_mps=headwind_mps, rain_mm_h=rain_mm_h, snow=snow,
        humidity_pct=50.0, pressure_hpa=1013.25,
    )
    band = efficiency_band(
        grade=grade, curvature_1pm=curvature_1pm, speed_limit_mps=speed_limit_mps,
        traffic_flow_mps=None, weather_point=wp, vehicle=MODEL3,
        ctx=TripContext(start_soc_pct=80.0),
    )
    if band is None:
        return
    limit_kmh = int(speed_limit_mps * 3.6)
    assert band.max_kmh <= limit_kmh
    assert band.optimal_kmh <= limit_kmh
    assert band.min_kmh <= band.max_kmh


@settings(max_examples=25, deadline=None)
@given(
    temp_c=st.floats(-15.0, 20.0),
    km=st.floats(80.0, 350.0),
    start_soc=st.floats(50.0, 95.0),
    n_candidates=st.integers(0, 4),
)
def test_charging_plan_never_breaches_reserve(
    temp_c: float, km: float, start_soc: float, n_candidates: int,
) -> None:
    """UNWAIVABLE invariant: a returned ChargingPlan must never dip below the
    reserve SoC anywhere along the route -- checked against the SAME eta_b-adjusted
    ground truth integrate() itself uses (result.cum_soc_drop_pct), not just
    optimize()'s own internal bookkeeping. This is deliberately fuzzed with cold
    temperatures (down to -15 C) since the bug this guards against (optimize()
    dividing energy by usable_wh alone, ignoring the temperature-dependent battery
    efficiency eta_b) was invisible at the fixture's default 15 C.
    """
    n = int(km * 1000.0 / 50.0) + 1
    r = flat_route(n=n, spacing_m=50.0, speed_mps=27.0)
    w = WeatherSamples.uniform(n, temp_c=temp_c)
    ctx = TripContext(start_soc_pct=start_soc)
    res = integrate(r, w, MODEL3, ctx)

    positions = np.linspace(0.15, 0.85, max(n_candidates, 1)) * km * 1000.0
    candidates = [
        ChargerCandidate(f"c{i}", float(p), 150.0, 0.5, 0.0, 0.95, 2.0)
        for i, p in enumerate(positions[:n_candidates])
    ]
    plan = optimize(res, r.s_m, candidates, MODEL3, start_soc=start_soc)
    if plan is None:
        return

    reserve_soc = 10.0
    tol = 0.5
    prev_m, prev_soc = 0.0, start_soc
    for stop in plan.stops:
        drop = float(np.interp(stop.position_m, r.s_m, res.cum_soc_drop_pct)
                     - np.interp(prev_m, r.s_m, res.cum_soc_drop_pct))
        true_arr = prev_soc - drop
        assert abs(true_arr - stop.arrival_soc) < tol
        assert true_arr >= reserve_soc - tol               # UNWAIVABLE reserve
        prev_m, prev_soc = stop.position_m, stop.departure_soc
    drop = float(np.interp(r.s_m[-1], r.s_m, res.cum_soc_drop_pct)
                 - np.interp(prev_m, r.s_m, res.cum_soc_drop_pct))
    true_final = prev_soc - drop
    assert abs(true_final - plan.arrival_soc) < tol
    assert true_final >= reserve_soc - tol
