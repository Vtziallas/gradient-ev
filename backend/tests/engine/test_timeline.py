import numpy as np

from gradient_energy.model import integrate
from gradient_energy.timeline import baseline_wh_per_km, build_timeline, classify_samples
from gradient_energy.types import RouteSamples, TripContext, WeatherSamples
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


def test_chapters_tile_with_no_gaps_at_coarse_spacing():
    """Regression for the off-by-one chapter boundary bug: end_m used to be
    route.s_m[min(en, n)-1] (one sample short of the next chapter's start), leaving
    a gap between consecutive chapters and omitting that boundary segment's energy
    from delta_soc. Invisible at the 25 m fixture spacing (error ~0.013, under the
    0.05 tolerance here) but grows to 0.053 at 100 m spacing and 0.264 at 500 m --
    both would fail this same tolerance pre-fix.
    """
    ctx = TripContext(start_soc_pct=80.0)
    for spacing in (100.0, 500.0):
        n = int(60_000.0 / spacing)
        r = hill_route(n=n, spacing_m=spacing)
        w = WeatherSamples.uniform(n)
        res = integrate(r, w, MODEL3, ctx)
        chapters = build_timeline(res, r, w, MODEL3, ctx)
        assert chapters[0].start_m == 0.0
        assert chapters[-1].end_m == float(r.s_m[-1])
        for a, b in zip(chapters, chapters[1:]):
            assert a.end_m == b.start_m                    # no gaps, no overlaps
        total = sum(ch.delta_soc for ch in chapters)
        assert abs(total - (res.soc_pct[-1] - res.soc_pct[0])) < 0.05


def test_short_leading_run_merges_forward_not_standalone():
    """Regression for the leading-run merge bug: the merge guard was
    `if merged and length < min_chapter_m`, which only merges a too-short run
    BACKWARD into an already-emitted chapter. When `merged` is still empty (i.e.
    the route's very first run is short), the guard was skipped entirely and the
    short run was emitted standalone -- e.g. a 175 m first chapter on a route with
    a short steep leading pitch. It must instead be merged FORWARD into the run
    that follows.
    """
    n = 1200
    spacing = 25.0
    grade = np.zeros(n)
    grade[:10] = 0.08                                       # 250 m steep leading pitch
    grade[400:] = -0.08                                     # long descent tail
    elevation_m = np.concatenate(([0.0], np.cumsum(grade[:-1] * spacing)))
    r = RouteSamples(
        s_m=np.arange(n, dtype=np.float64) * spacing,
        elevation_m=elevation_m, grade=grade,
        curvature_1pm=np.zeros(n), heading_deg=np.zeros(n),
        speed_limit_mps=np.full(n, 27.78), expected_speed_mps=np.full(n, 20.0),
    )
    w = WeatherSamples.uniform(n)
    ctx = TripContext(start_soc_pct=80.0)
    res = integrate(r, w, MODEL3, ctx)
    chapters = build_timeline(res, r, w, MODEL3, ctx)

    assert chapters[0].start_m == 0.0
    for ch in chapters:
        assert ch.end_m - ch.start_m >= 500.0 or ch is chapters[-1]
