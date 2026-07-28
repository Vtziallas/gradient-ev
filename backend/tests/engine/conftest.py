import numpy as np
import pytest

from gradient_energy.types import RouteSamples, TripContext, VehicleSpec, WeatherSamples

MODEL3 = VehicleSpec(
    mass_kg=1850.0, cd=0.23, frontal_area_m2=2.22, c_rr_base=0.010,
    usable_kwh=75.0, max_regen_kw=120.0, max_dc_kw=250.0,
    charge_curve=((0.0, 200.0), (50.0, 150.0), (80.0, 70.0), (100.0, 10.0)),
)


def flat_route(n: int = 400, spacing_m: float = 25.0, speed_mps: float = 25.0) -> RouteSamples:
    return RouteSamples(
        s_m=np.arange(n, dtype=np.float64) * spacing_m,
        elevation_m=np.zeros(n),
        grade=np.zeros(n),
        curvature_1pm=np.zeros(n),
        heading_deg=np.zeros(n),
        speed_limit_mps=np.full(n, 36.11),
        expected_speed_mps=np.full(n, speed_mps),
    )


def hill_route(n: int = 800, spacing_m: float = 25.0, grade: float = 0.05,
               speed_mps: float = 20.0) -> RouteSamples:
    """Up at +grade for the first half, down at -grade for the second half."""
    g = np.where(np.arange(n) < n // 2, grade, -grade)
    elev = np.concatenate(([0.0], np.cumsum(g[:-1] * spacing_m)))
    return RouteSamples(
        s_m=np.arange(n, dtype=np.float64) * spacing_m,
        elevation_m=elev, grade=g,
        curvature_1pm=np.zeros(n), heading_deg=np.zeros(n),
        speed_limit_mps=np.full(n, 27.78),
        expected_speed_mps=np.full(n, speed_mps),
    )


@pytest.fixture
def vehicle() -> VehicleSpec:
    return MODEL3


@pytest.fixture
def ctx() -> TripContext:
    return TripContext(start_soc_pct=80.0)


@pytest.fixture
def mild_weather() -> WeatherSamples:
    return WeatherSamples.uniform(n=400)
