from gradient_energy.speed import WeatherPoint, efficiency_band
from gradient_energy.types import TripContext
from tests.engine.conftest import MODEL3

CALM = WeatherPoint(temp_c=15.0, headwind_mps=0.0, rain_mm_h=0.0, snow=False,
                    humidity_pct=50.0, pressure_hpa=1013.25)
CTX = TripContext(start_soc_pct=60.0)


def band(**kw):
    args = dict(grade=0.0, curvature_1pm=0.0, speed_limit_mps=36.11,   # 130 km/h
                traffic_flow_mps=None, weather_point=CALM, vehicle=MODEL3, ctx=CTX)
    args.update(kw)
    return efficiency_band(**args)


def test_never_exceeds_speed_limit_UNWAIVABLE():
    for limit in (13.89, 22.22, 27.78, 36.11):            # 50/80/100/130 km/h
        for g in (-0.08, 0.0, 0.05, 0.10):
            b = band(grade=g, speed_limit_mps=limit)
            assert b is not None
            assert b.max_kmh <= int(limit * 3.6) + 0      # hard cap, no rounding up


def test_band_is_ordered_and_contains_optimum():
    b = band()
    assert b.min_kmh <= b.optimal_kmh <= b.max_kmh


def test_climb_widens_band_and_reports_grade_reason():
    # Grade force (m*g*sin(theta)) is independent of v, so under the v1 flat drivetrain
    # efficiency map (EnergyEngine.md's documented simplification -- no speed x load
    # map yet) it shifts e(v) by a v-independent additive constant and cannot move
    # WHERE the aero/aux tradeoff bottoms out -- verified analytically and numerically
    # across grade 0.00-0.10, optimal_kmh stays fixed at 34 in every case. What climbing
    # DOES do: it dominates total force, shrinking the *relative* sensitivity of the
    # aero term, so the 2%-of-optimal tolerance band admits a wider range of speeds
    # (14 km/h wide at grade=0 -> 28 km/h wide at grade=0.06, monotonically increasing
    # with grade). That widening -- plus the grade_up reason -- is what this test checks.
    flat = band(speed_limit_mps=36.11)
    climb = band(grade=0.06, speed_limit_mps=36.11)
    assert "grade_up" in climb.reasons
    assert (climb.max_kmh - climb.min_kmh) > (flat.max_kmh - flat.min_kmh)


def test_headwind_lowers_optimum_and_is_reported():
    windy = WeatherPoint(temp_c=15.0, headwind_mps=8.0, rain_mm_h=0.0, snow=False,
                         humidity_pct=50.0, pressure_hpa=1013.25)
    b = band(weather_point=windy)
    assert b.optimal_kmh < band().optimal_kmh
    assert "headwind" in b.reasons


def test_curvature_caps_speed():
    b = band(curvature_1pm=1.0 / 60.0)                    # 60 m radius curve
    v_cap_kmh = (2.5 * 60.0) ** 0.5 * 3.6                 # ~44 km/h
    assert b.max_kmh <= int(v_cap_kmh) + 1
    assert "curve" in b.reasons


def test_traffic_floor_respected():
    b = band(traffic_flow_mps=25.0)
    assert b.min_kmh >= int(0.85 * 25.0 * 3.6)
    assert "traffic" in b.reasons


def test_snow_caps_speed():
    snowy = WeatherPoint(temp_c=-2.0, headwind_mps=0.0, rain_mm_h=0.0, snow=True,
                         humidity_pct=80.0, pressure_hpa=1013.25)
    b = band(weather_point=snowy, speed_limit_mps=36.11)
    assert b.max_kmh <= int(0.7 * 130.0) + 1
    assert "snow" in b.reasons


def test_infeasible_returns_none():
    assert band(curvature_1pm=1.0, traffic_flow_mps=35.0) is None
