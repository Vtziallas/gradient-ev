import time

from gradient_energy.model import integrate
from gradient_energy.prediction import predict
from gradient_energy.timeline import build_timeline
from gradient_energy.types import TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, hill_route


def test_energy_totals_equal_sum_of_segments():
    r = hill_route(n=800)
    w = WeatherSamples.uniform(800)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    assert abs((res.energy_used_kwh - res.energy_regen_kwh) * 1000.0
               - float(res.e_wh.sum())) < 1e-6


def test_regen_bounded_by_potential_energy():
    r = hill_route(n=800, grade=0.05)
    w = WeatherSamples.uniform(800)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=60.0))
    drop_m = 0.05 * 10_000.0                               # descent half: 500 m drop
    ep_kwh = (1850.0 + 75.0) * 9.80665 * drop_m / 3.6e6
    assert res.energy_regen_kwh <= ep_kwh


def test_perf_budget_10k_samples():
    n = 10_000
    r = hill_route(n=n)
    w = WeatherSamples.uniform(n)
    ctx = TripContext(start_soc_pct=80.0)
    t0 = time.perf_counter()
    res = integrate(r, w, MODEL3, ctx)
    predict(r, w, MODEL3, ctx)
    build_timeline(res, r, w, MODEL3, ctx)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.2                                   # 50 ms budget x4 CI margin
