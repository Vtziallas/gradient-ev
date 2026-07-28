"""Physics core: environment, forces, power, SoC integration (EnergyEngine.md §2)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gradient_energy.types import RouteSamples, TripContext, VehicleSpec, WeatherSamples

G = 9.80665
R_D = 287.05
R_V = 461.5
ROT_INERTIA = 1.05
PASSENGER_KG = 75.0


def air_density(temp_c: np.ndarray, pressure_hpa: np.ndarray, humidity_pct: np.ndarray) -> np.ndarray:
    t_k = temp_c + 273.15
    p_sat_hpa = 6.1078 * 10.0 ** (7.5 * temp_c / (temp_c + 237.3))   # Tetens
    p_v = humidity_pct / 100.0 * p_sat_hpa * 100.0                    # Pa
    p_d = pressure_hpa * 100.0 - p_v
    return p_d / (R_D * t_k) + p_v / (R_V * t_k)


def headwind_mps(wind_speed_mps: np.ndarray, wind_dir_deg: np.ndarray,
                 heading_deg: np.ndarray) -> np.ndarray:
    """Component of wind along travel direction; wind_dir is where wind blows FROM."""
    return wind_speed_mps * np.cos(np.radians(wind_dir_deg - heading_deg))  # type: ignore[no-any-return]


def effective_mass_kg(vehicle: VehicleSpec, ctx: TripContext) -> float:
    return vehicle.mass_kg + PASSENGER_KG * ctx.passengers + ctx.cargo_kg


def rolling_coeff(vehicle: VehicleSpec, ctx: TripContext, weather: WeatherSamples) -> np.ndarray:
    f_rain = np.where(weather.rain_mm_h > 0.1, 1.15, 1.0)
    f_snow = np.where(weather.snow, 1.5, 1.0)
    f_temp = np.minimum(1.0 + 0.004 * np.clip(10.0 - weather.temp_c, 0.0, None), 1.12)
    return vehicle.c_rr_base * f_rain * f_snow * f_temp / ctx.tire_pressure_factor


@dataclass
class Forces:
    f_roll_n: np.ndarray
    f_aero_n: np.ndarray
    f_grade_n: np.ndarray
    f_accel_n: np.ndarray
    f_total_n: np.ndarray


def compute_forces(route: RouteSamples, weather: WeatherSamples,
                   vehicle: VehicleSpec, ctx: TripContext) -> Forces:
    m = effective_mass_kg(vehicle, ctx)
    theta = np.arctan(route.grade)
    v = route.expected_speed_mps

    c_rr = rolling_coeff(vehicle, ctx, weather)
    f_roll = c_rr * m * G * np.cos(theta)

    rho = air_density(weather.temp_c, weather.pressure_hpa, weather.humidity_pct)
    v_air = v + headwind_mps(weather.wind_speed_mps, weather.wind_dir_deg, route.heading_deg)
    f_aero = 0.5 * rho * vehicle.cd * vehicle.frontal_area_m2 * v_air * np.abs(v_air)

    f_grade = m * G * np.sin(theta)

    ds = np.diff(route.s_m)
    a = (v[1:] ** 2 - v[:-1] ** 2) / (2.0 * ds)
    a = np.append(a, 0.0)
    f_accel = ROT_INERTIA * m * a

    return Forces(
        f_roll_n=f_roll, f_aero_n=f_aero, f_grade_n=f_grade, f_accel_n=f_accel,
        f_total_n=f_roll + f_aero + f_grade + f_accel,
    )
