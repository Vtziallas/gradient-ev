from gradient_energy.charging import charge_minutes, optimize
from gradient_energy.model import integrate
from gradient_energy.types import ChargerCandidate, TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route


def long_flat(km: float = 400.0):
    n = int(km * 1000 / 50) + 1
    r = flat_route(n=n, spacing_m=50.0, speed_mps=30.55)   # 110 km/h
    w = WeatherSamples.uniform(n)
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


def test_single_stop_plan_respects_reserve_and_arrival():
    r, w = long_flat(km=400.0)                             # ~75+ kWh trip, needs a stop
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=90.0))
    plan = optimize(res, r.s_m, cands(180.0, 220.0), MODEL3, start_soc=90.0)
    assert plan is not None and len(plan.stops) >= 1
    stop = plan.stops[0]
    assert stop.arrival_soc >= 10.0 - 1e-6                 # UNWAIVABLE reserve
    assert plan.arrival_soc >= 15.0 - 1e-6
    assert stop.departure_soc <= 90.0
    assert plan.total_cost > 0 and plan.total_charge_min > 0


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
