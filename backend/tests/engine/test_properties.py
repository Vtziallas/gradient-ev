import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from gradient_energy.model import integrate
from gradient_energy.types import TripContext, WeatherSamples
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
