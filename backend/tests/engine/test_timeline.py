import numpy as np

from gradient_energy.model import integrate
from gradient_energy.timeline import baseline_wh_per_km, build_timeline, classify_samples
from gradient_energy.types import TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route, hill_route


def test_baseline_is_sane_for_efficient_ev():
    b = baseline_wh_per_km(MODEL3)
    assert 120.0 < b < 220.0                              # Model 3-class at 90 km/h


def test_classify_hill_route():
    r = hill_route(n=800)
    w = WeatherSamples.uniform(800)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    c = classify_samples(res, r, MODEL3)
    assert set(np.unique(c[:390])) <= {2, 3} and 3 in c[:390]   # climb: medium/heavy
    assert np.all(c[410:790] == 0)                              # descent: regen


def test_build_timeline_chapters_merge_and_causes():
    r = hill_route(n=800)                                 # 10 km up, 10 km down
    w = WeatherSamples.uniform(800)
    ctx = TripContext(start_soc_pct=80.0)
    res = integrate(r, w, MODEL3, ctx)
    chapters = build_timeline(res, r, w, MODEL3, ctx)
    assert 2 <= len(chapters) <= 4                        # no flicker
    assert chapters[0].cause == "climb" and chapters[0].delta_soc < 0
    assert chapters[0].distance_to_summit_m is not None
    assert chapters[-1].klass == "regen" and chapters[-1].delta_soc > 0
    total = sum(ch.delta_soc for ch in chapters)
    assert abs(total - (res.soc_pct[-1] - res.soc_pct[0])) < 0.05
    for ch in chapters:
        assert ch.end_m - ch.start_m >= 500.0 or ch is chapters[-1]


def test_headwind_cause_on_flat():
    r = flat_route(n=800)
    w = WeatherSamples.uniform(800, wind_speed_mps=8.0, wind_dir_deg=0.0)  # pure headwind
    ctx = TripContext(start_soc_pct=80.0)
    res = integrate(r, w, MODEL3, ctx)
    chapters = build_timeline(res, r, w, MODEL3, ctx)
    assert any(ch.cause == "wind" for ch in chapters)
