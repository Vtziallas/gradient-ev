import numpy as np

from gradient_energy.model import (
    air_density, compute_forces, effective_mass_kg, headwind_mps, rolling_coeff,
)
from gradient_energy.types import TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route, hill_route


def test_air_density_standard_conditions():
    rho = air_density(np.array([15.0]), np.array([1013.25]), np.array([0.0]))
    assert abs(rho[0] - 1.225) < 0.003


def test_air_density_humid_air_is_lighter():
    dry = air_density(np.array([30.0]), np.array([1013.25]), np.array([0.0]))
    humid = air_density(np.array([30.0]), np.array([1013.25]), np.array([100.0]))
    assert humid[0] < dry[0]


def test_headwind_projection():
    # driving north (0 deg); wind FROM north = headwind; FROM south = tailwind
    w = np.array([10.0, 10.0, 10.0])
    d = np.array([0.0, 180.0, 90.0])
    h = np.array([0.0, 0.0, 0.0])
    out = headwind_mps(w, d, h)
    assert abs(out[0] - 10.0) < 1e-9
    assert abs(out[1] + 10.0) < 1e-9
    assert abs(out[2]) < 1e-9                              # pure crosswind


def test_effective_mass():
    ctx = TripContext(start_soc_pct=80.0, passengers=2, cargo_kg=20.0)
    assert effective_mass_kg(MODEL3, ctx) == 1850.0 + 150.0 + 20.0


def test_rolling_coeff_rain_and_cold_increase_it():
    ctx = TripContext(start_soc_pct=80.0)
    mild = WeatherSamples.uniform(4)
    wet = WeatherSamples.uniform(4, rain_mm_h=2.0, temp_c=2.0)
    assert np.all(rolling_coeff(MODEL3, ctx, wet) > rolling_coeff(MODEL3, ctx, mild))


def test_forces_flat_constant_speed():
    r = flat_route(n=100)
    w = WeatherSamples.uniform(100)
    ctx = TripContext(start_soc_pct=80.0)
    f = compute_forces(r, w, MODEL3, ctx)
    m = effective_mass_kg(MODEL3, ctx)
    # F_roll = crr*m*g ~ 0.010*1925*9.80665 ~ 189 N ; aero at 25 m/s, rho 1.225:
    # 0.5*1.225*0.23*2.22*625 ~ 195 N
    assert abs(np.mean(f.f_roll_n) - 0.010 * m * 9.80665) < 2.0
    assert abs(np.mean(f.f_aero_n) - 195.0) < 8.0
    assert np.allclose(f.f_grade_n, 0.0) and np.allclose(f.f_accel_n, 0.0)
    assert np.allclose(f.f_total_n, f.f_roll_n + f.f_aero_n)


def test_forces_grade_sign():
    r = hill_route(n=100)
    w = WeatherSamples.uniform(100)
    f = compute_forces(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    assert np.all(f.f_grade_n[:49] > 0)                    # climbing
    assert np.all(f.f_grade_n[51:] < 0)                    # descending


def test_forces_acceleration_term():
    r = flat_route(n=3)
    r.expected_speed_mps = np.array([20.0, 25.0, 25.0])
    w = WeatherSamples.uniform(3)
    f = compute_forces(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    m_eff = 1.05 * effective_mass_kg(MODEL3, TripContext(start_soc_pct=80.0))
    a0 = (25.0**2 - 20.0**2) / (2 * 25.0)
    assert abs(f.f_accel_n[0] - m_eff * a0) < 1e-6
    assert f.f_accel_n[-1] == 0.0
