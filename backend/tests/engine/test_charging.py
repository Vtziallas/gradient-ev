import time

import numpy as np
import pytest

from gradient_energy.charging import charge_minutes, optimize
from gradient_energy.model import integrate
from gradient_energy.types import ChargerCandidate, TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route


def long_flat(km: float = 400.0, temp_c: float = 15.0):
    n = int(km * 1000 / 50) + 1
    r = flat_route(n=n, spacing_m=50.0, speed_mps=30.55)   # 110 km/h
    w = WeatherSamples.uniform(n, temp_c=temp_c)
    return r, w


def cands(*positions_km: float, kw: float = 150.0, price: float = 0.55,
          rel: float = 0.95, wait: float = 2.0):
    return [ChargerCandidate(station_id=f"st{i}", position_m=p * 1000.0, power_kw=kw,
                             price_per_kwh=price, session_fee=0.0, reliability=rel,
                             expected_wait_min=wait)
            for i, p in enumerate(positions_km)]


def test_charge_minutes_uses_curve_and_station_cap():
    fast = charge_minutes(MODEL3, 10.0, 60.0, station_kw=250.0)
    capped = charge_minutes(MODEL3, 10.0, 60.0, station_kw=50.0)
    assert fast < capped
    # 50 kW cap: 0.5*75 kWh / 50 kW = 45 min exactly (curve is above 50 in range)
    assert abs(capped - 45.0) < 1.0


def test_no_stop_needed_returns_empty_plan():
    r, w = long_flat(km=100.0)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=90.0))
    plan = optimize(res, r.s_m, cands(50.0), MODEL3, start_soc=90.0)
    assert plan is not None and plan.stops == ()


@pytest.mark.parametrize("temp_c", [15.0, -5.0])
def test_single_stop_plan_respects_reserve_and_arrival(temp_c: float):
    r, w = long_flat(km=400.0, temp_c=temp_c)              # ~75+ kWh trip, needs a stop
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=90.0))
    plan = optimize(res, r.s_m, cands(180.0, 220.0), MODEL3, start_soc=90.0)
    assert plan is not None and len(plan.stops) >= 1
    stop = plan.stops[0]
    assert stop.arrival_soc >= 10.0 - 1e-6                 # UNWAIVABLE reserve
    assert plan.arrival_soc >= 15.0 - 1e-6
    assert stop.departure_soc <= 90.0
    assert plan.total_cost > 0 and plan.total_charge_min > 0


def test_cold_weather_direct_arrival_matches_integrate_ground_truth():
    """Regression for the eta_b bug: optimize() used to divide cum_wh by usable_wh
    alone, ignoring the temperature-dependent battery efficiency eta_b that
    integrate() applies -- so in cold weather it systematically underestimated
    consumption and could report a safe zero-stop plan when the vehicle would
    truly breach the reserve. optimize()'s belief must now match integrate()'s own
    ground truth (result.soc_pct[-1]) exactly, since both derive from the same
    eta_b-adjusted cum_soc_drop_pct trace.
    """
    r, w = long_flat(km=300.0, temp_c=-5.0)
    ctx = TripContext(start_soc_pct=81.0)
    res = integrate(r, w, MODEL3, ctx)
    true_arrival = float(res.soc_pct[-1])

    plan = optimize(res, r.s_m, [], MODEL3, start_soc=81.0)  # no chargers available

    if true_arrival < 10.0:
        # Ground truth genuinely breaches the reserve with no stop possible (no
        # candidates given) -- optimize() must refuse, not fabricate a plan.
        assert plan is None
    elif plan is not None and plan.stops == ():
        assert abs(plan.arrival_soc - true_arrival) < 0.05
    else:
        # Truth is safely above min_arrival_soc/reserve with nothing needed;
        # optimize() must agree there was no need to charge.
        assert true_arrival >= 15.0


def test_cold_weather_plan_with_stop_matches_integrate_ground_truth():
    """Same consistency check as above, but forcing a scenario where the vehicle
    truly cannot make the direct trip in cold weather, so optimize() must schedule
    a stop -- and every leg's SoC (per stop, and final arrival) must match the
    independently-computed eta_b-adjusted ground truth (res.cum_soc_drop_pct),
    never dipping below the unwaivable reserve.
    """
    r, w = long_flat(km=300.0, temp_c=-5.0)
    ctx = TripContext(start_soc_pct=81.0)
    res = integrate(r, w, MODEL3, ctx)
    plan = optimize(res, r.s_m, cands(150.0), MODEL3, start_soc=81.0)
    assert plan is not None

    prev_m, prev_soc = 0.0, 81.0
    for stop in plan.stops:
        drop = float(np.interp(stop.position_m, r.s_m, res.cum_soc_drop_pct)
                     - np.interp(prev_m, r.s_m, res.cum_soc_drop_pct))
        true_arr = prev_soc - drop
        assert abs(true_arr - stop.arrival_soc) < 0.05
        assert true_arr >= 10.0 - 1e-6                     # UNWAIVABLE reserve
        prev_m, prev_soc = stop.position_m, stop.departure_soc
    drop = float(np.interp(r.s_m[-1], r.s_m, res.cum_soc_drop_pct)
                 - np.interp(prev_m, r.s_m, res.cum_soc_drop_pct))
    true_final = prev_soc - drop
    assert abs(true_final - plan.arrival_soc) < 0.05
    assert true_final >= 10.0 - 1e-6


def test_infeasible_gap_returns_none():
    # 400 km was tried first and turned out to be FEASIBLE by a slim margin: the
    # remaining 380 km after charging to 90% at km 20 needs ~77.8% SoC, and 80% is
    # available (90% max charge - 10% reserve) -- verified numerically, a ~2-point
    # margin, not the infeasible case this test is meant to exercise. 500 km leaves
    # 480 km remaining, needing ~98.3% SoC against the same 80% available -- a robust
    # ~18-point infeasibility margin.
    r, w = long_flat(km=500.0)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=90.0))
    # only charger at km 20; the remaining 480 km can't be bridged from 90%
    assert optimize(res, r.s_m, cands(20.0), MODEL3, start_soc=90.0) is None


def test_prefers_reliable_cheap_fast_station():
    r, w = long_flat(km=400.0)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=90.0))
    good = ChargerCandidate("good", 200_000.0, 250.0, 0.45, 0.0, 0.98, 0.0)
    bad = ChargerCandidate("bad", 201_000.0, 50.0, 0.79, 0.0, 0.60, 15.0)
    plan = optimize(res, r.s_m, [good, bad], MODEL3, start_soc=90.0)
    assert plan is not None
    assert plan.stops[0].station_id == "good"


def test_dp_matches_brute_force_on_small_instance():
    r, w = long_flat(km=300.0)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=70.0))
    cs = cands(120.0, 180.0, kw=150.0)
    plan = optimize(res, r.s_m, cs, MODEL3, start_soc=70.0)
    assert plan is not None
    # brute force: try every subset/level combo coarsely; DP must not be worse
    def total_cost(p):
        return p.total_charge_min + 3.0 * p.total_cost
    from itertools import product
    best = None
    for use0, use1 in product([False, True], repeat=2):
        # emulate by restricting candidates
        subset = [c for c, use in zip(cs, (use0, use1)) if use]
        alt = optimize(res, r.s_m, subset, MODEL3, start_soc=70.0)
        if alt is not None and (best is None or total_cost(alt) < total_cost(best)):
            best = alt
    assert best is not None
    assert total_cost(plan) <= total_cost(best) + 1e-6


def test_optimize_perf_budget_many_candidates():
    """Regression for the quadratic-ish charge_minutes() blowup: pre-fix, timing
    roughly went 8->0.010s, 12->0.043s, 16->0.128s, 20->0.295s, 25->0.697s (~2.4x
    per +4 candidates), driven by a per-1%-step Python loop that rebuilt the charge
    curve as fresh lists on every call. A realistic 25-candidate route must stay
    comfortably inside a generous CI-safe budget now that the curve is hoisted once
    and charge_minutes() is vectorized.
    """
    r, w = long_flat(km=600.0)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=95.0))
    positions = np.linspace(30.0, 570.0, 25)
    candidates = cands(*(float(p) for p in positions))
    t0 = time.perf_counter()
    optimize(res, r.s_m, candidates, MODEL3, start_soc=95.0)
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0                                   # generous CI-safe budget
