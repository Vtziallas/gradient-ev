from gradient_energy.prediction import predict
from gradient_energy.types import DriverProfile, TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route, hill_route


def test_prediction_ordering_and_curve():
    r = hill_route(n=800)
    w = WeatherSamples.uniform(800)
    p = predict(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    assert p.worst_case_soc < p.arrival_soc < p.best_case_soc
    assert p.soc_curve.shape == (800,)
    assert abs(p.soc_curve[-1] - p.arrival_soc) < 1e-9
    assert p.energy_used_kwh > 0 and p.energy_regen_kwh > 0


def test_confidence_degrades_with_inputs():
    r = flat_route(n=400)
    w = WeatherSamples.uniform(400)
    ctx = TripContext(start_soc_pct=80.0)
    good = predict(r, w, MODEL3, ctx, data_quality=5, weather_age_h=0.0)
    bad = predict(r, w, MODEL3, ctx, data_quality=1, weather_age_h=12.0,
                  driver=DriverProfile(calibration_factor=1.15))
    assert good.confidence > bad.confidence
    assert 5 <= bad.confidence <= 99


def test_remaining_range_positive_and_sane():
    r = flat_route(n=400, speed_mps=25.0)                 # ~10 km trip
    w = WeatherSamples.uniform(400)
    p = predict(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    # 75 kWh pack at highway consumption -> roughly 250-500 km left above reserve
    assert 200.0 < p.remaining_range_km < 600.0


def test_worst_case_reflects_headwind_and_load():
    r = flat_route(n=400)
    w = WeatherSamples.uniform(400)
    p = predict(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    spread = p.best_case_soc - p.worst_case_soc
    assert 0.1 < spread < 15.0
