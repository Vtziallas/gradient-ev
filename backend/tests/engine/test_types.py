import numpy as np
import pytest

from gradient_energy.types import (
    DriverProfile, RouteSamples, TripContext, VehicleSpec, WeatherSamples,
)


def _arr(*vals: float) -> np.ndarray:
    return np.asarray(vals, dtype=np.float64)


def make_route(n: int = 4) -> RouteSamples:
    return RouteSamples(
        s_m=np.linspace(0.0, 25.0 * (n - 1), n),
        elevation_m=np.zeros(n),
        grade=np.zeros(n),
        curvature_1pm=np.zeros(n),
        heading_deg=np.zeros(n),
        speed_limit_mps=np.full(n, 27.78),
        expected_speed_mps=np.full(n, 25.0),
    )


def test_vehicle_spec_defaults():
    v = VehicleSpec(
        mass_kg=1850.0, cd=0.23, frontal_area_m2=2.22, c_rr_base=0.010,
        usable_kwh=75.0, max_regen_kw=120.0, max_dc_kw=250.0,
        charge_curve=((0.0, 200.0), (50.0, 150.0), (80.0, 70.0), (100.0, 10.0)),
    )
    assert v.drivetrain_eff == 0.90
    assert v.regen_eff == 0.65
    assert v.aux_base_w == 350.0
    assert v.has_heat_pump is True
    assert v.degradation_factor == 1.0


def test_trip_context_and_driver_defaults():
    ctx = TripContext(start_soc_pct=80.0)
    assert ctx.passengers == 1 and ctx.cargo_kg == 0.0
    assert ctx.hvac_mode == "off" and ctx.cabin_target_c == 21.0
    assert ctx.tire_pressure_factor == 1.0
    assert DriverProfile().calibration_factor == 1.0


def test_route_samples_validate_ok():
    make_route().validate()  # must not raise


def test_route_samples_validate_rejects_non_increasing_distance():
    r = make_route()
    r.s_m[2] = r.s_m[1]
    with pytest.raises(ValueError, match="strictly increasing"):
        r.validate()


def test_route_samples_validate_rejects_shape_mismatch():
    r = make_route()
    r.grade = _arr(0.0, 0.0)
    with pytest.raises(ValueError, match="same shape"):
        r.validate()


def test_weather_samples_uniform_constructor():
    w = WeatherSamples.uniform(n=5, temp_c=15.0)
    assert w.temp_c.shape == (5,)
    assert w.pressure_hpa[0] == 1013.25 and not w.snow.any()
