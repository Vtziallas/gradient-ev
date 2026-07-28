"""Safe efficiency speed band (Smart Speed Bubble). Never recommends above the limit —
the cap lives HERE, not in any UI (Security.md §6)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gradient_energy.model import G, air_density, effective_mass_kg
from gradient_energy.types import SpeedBand, TripContext, VehicleSpec

MAX_LATERAL_MPS2 = 2.5
BAND_TOLERANCE = 1.02
MIN_SPEED_MPS = 8.0
RAIN_CAP = 0.9
SNOW_CAP = 0.7
TRAFFIC_FLOOR = 0.85
HVAC_AND_BASE_W = 600.0  # aux approximation for the per-meter amortization term


@dataclass(frozen=True)
class WeatherPoint:
    temp_c: float
    headwind_mps: float
    rain_mm_h: float
    snow: bool
    humidity_pct: float
    pressure_hpa: float


def efficiency_band(*, grade: float, curvature_1pm: float, speed_limit_mps: float,
                    traffic_flow_mps: float | None, weather_point: WeatherPoint,
                    vehicle: VehicleSpec, ctx: TripContext) -> SpeedBand | None:
    reasons: set[str] = set()
    m = effective_mass_kg(vehicle, ctx)
    rho = float(air_density(np.array([weather_point.temp_c]),
                            np.array([weather_point.pressure_hpa]),
                            np.array([weather_point.humidity_pct]))[0])
    theta = float(np.arctan(grade))

    v_max = speed_limit_mps
    if weather_point.snow:
        v_max = min(v_max, SNOW_CAP * speed_limit_mps)
        reasons.add("snow")
    elif weather_point.rain_mm_h > 0.1:
        v_max = min(v_max, RAIN_CAP * speed_limit_mps)
        reasons.add("rain")
    if curvature_1pm > 1e-6:
        v_curve = float(np.sqrt(MAX_LATERAL_MPS2 / curvature_1pm))
        if v_curve < v_max:
            v_max = v_curve
            reasons.add("curve")

    v_min = MIN_SPEED_MPS
    if traffic_flow_mps is not None:
        floor = TRAFFIC_FLOOR * traffic_flow_mps
        if floor > v_min:
            v_min = floor
            reasons.add("traffic")

    if v_min > v_max:
        return None

    v = np.arange(np.ceil(v_min * 3.6), np.floor(v_max * 3.6) + 1.0) / 3.6  # 1 km/h grid
    if v.size == 0:
        return None

    c_rr = vehicle.c_rr_base / ctx.tire_pressure_factor
    if weather_point.snow:
        c_rr *= 1.5
    elif weather_point.rain_mm_h > 0.1:
        c_rr *= 1.15
    f_roll = c_rr * m * G * np.cos(theta)
    v_air = v + weather_point.headwind_mps
    f_aero = 0.5 * rho * vehicle.cd * vehicle.frontal_area_m2 * v_air * np.abs(v_air)
    f_grade = m * G * np.sin(theta)
    f_total = f_roll + f_aero + f_grade

    e = np.where(
        f_total >= 0.0,
        f_total / vehicle.drivetrain_eff + HVAC_AND_BASE_W / v,
        f_total * vehicle.regen_eff + HVAC_AND_BASE_W / v,
    )
    i_opt = int(np.argmin(e))
    in_band = e <= BAND_TOLERANCE * e[i_opt] if e[i_opt] > 0 else e <= e[i_opt] / BAND_TOLERANCE

    if grade > 0.02:
        reasons.add("grade_up")
    elif grade < -0.02:
        reasons.add("grade_down")
    if weather_point.headwind_mps > 3.0:
        reasons.add("headwind")
    if not reasons:
        reasons.add("aero")

    kmh = np.round(v * 3.6).astype(int)
    limit_kmh = int(speed_limit_mps * 3.6)
    band_kmh = np.minimum(kmh[in_band], limit_kmh)         # belt AND suspenders
    return SpeedBand(
        min_kmh=int(band_kmh.min()), max_kmh=int(band_kmh.max()),
        optimal_kmh=min(int(kmh[i_opt]), limit_kmh),
        reasons=tuple(sorted(reasons)),
    )
