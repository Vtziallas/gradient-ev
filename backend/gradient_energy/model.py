"""Physics core: environment, forces, power, SoC integration (EnergyEngine.md §2)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gradient_energy.types import (
    DriverProfile,
    EnergyResult,
    RouteSamples,
    TripContext,
    VehicleSpec,
    WeatherSamples,
)

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


ELECTRONICS_W = 250.0
HEAT_W_PER_K = 220.0      # cabin heating demand per Kelvin of deficit (v1 heuristic)
COOL_W_PER_K = 180.0
COOL_COP = 2.5
DEFOG_W = 300.0


def hvac_power_w(weather: WeatherSamples, ctx: TripContext, vehicle: VehicleSpec) -> np.ndarray:
    n = weather.temp_c.size
    p = np.zeros(n)
    if ctx.hvac_mode == "heat":
        dt = np.clip(ctx.cabin_target_c - weather.temp_c, 0.0, None)
        demand = HEAT_W_PER_K * dt
        cop = np.maximum(1.0, 3.0 - 0.05 * dt) if vehicle.has_heat_pump else np.ones(n)
        p = demand / cop
    elif ctx.hvac_mode == "cool":
        dt = np.clip(weather.temp_c - ctx.cabin_target_c, 0.0, None)
        p = COOL_W_PER_K * dt / COOL_COP
    return p + np.where(weather.rain_mm_h > 0.1, DEFOG_W, 0.0)


def aux_power_w(weather: WeatherSamples, ctx: TripContext, vehicle: VehicleSpec) -> np.ndarray:
    return vehicle.aux_base_w + hvac_power_w(weather, ctx, vehicle) + ELECTRONICS_W


def temp_derate_factor(temp_c: np.ndarray) -> np.ndarray:
    """Temperature-only regen derating factor, shared by regen_derate() and integrate()."""
    return np.clip(0.4 + 0.6 * (temp_c + 10.0) / 15.0, 0.4, 1.0)


def regen_derate(soc_pct: float | np.ndarray, temp_c: np.ndarray) -> np.ndarray:
    f_soc = np.clip((100.0 - np.asarray(soc_pct, dtype=np.float64)) / 10.0, 0.0, 1.0)
    f_temp = temp_derate_factor(temp_c)
    return f_soc * f_temp  # type: ignore[no-any-return]


def battery_eff(temp_c: np.ndarray) -> np.ndarray:
    return np.clip(1.0 - 0.008 * np.clip(10.0 - temp_c, 0.0, None) * (0.08 / 0.12), 0.92, 1.0)


def battery_power_w(forces: Forces, route: RouteSamples, weather: WeatherSamples,
                    vehicle: VehicleSpec, ctx: TripContext, soc_pct: float) -> np.ndarray:
    v = route.expected_speed_mps
    p_wheel = forces.f_total_n * v
    p_aux = aux_power_w(weather, ctx, vehicle)
    p_regen_cap = vehicle.max_regen_kw * 1000.0 * regen_derate(soc_pct, weather.temp_c)
    drive = p_wheel / vehicle.drivetrain_eff + p_aux
    regen = np.maximum(p_wheel, -p_regen_cap) * vehicle.regen_eff + p_aux
    return np.where(p_wheel >= 0.0, drive, regen)  # type: ignore[no-any-return]


def integrate(route: RouteSamples, weather: WeatherSamples, vehicle: VehicleSpec,
              ctx: TripContext, driver: DriverProfile | None = None) -> EnergyResult:
    route.validate()
    calib = (driver or DriverProfile()).calibration_factor

    forces = compute_forces(route, weather, vehicle, ctx)
    v = route.expected_speed_mps
    p_wheel = forces.f_total_n * v
    p_aux = aux_power_w(weather, ctx, vehicle)
    p_drive = p_wheel / vehicle.drivetrain_eff + p_aux    # valid where p_wheel >= 0

    ds = np.append(np.diff(route.s_m), 0.0)
    dt = np.where(v > 0, ds / v, 0.0)
    eta_b = battery_eff(weather.temp_c)
    usable_wh = vehicle.usable_kwh * 1000.0 * vehicle.degradation_factor

    n = route.n
    p_batt = np.empty(n)
    e_wh = np.zeros(n)
    soc = np.empty(n)
    soc[0] = ctx.start_soc_pct
    cum_drop = np.zeros(n)
    regen_cap_temp = vehicle.max_regen_kw * 1000.0 * temp_derate_factor(weather.temp_c)

    s = ctx.start_soc_pct
    drop = 0.0
    for i in range(n):
        if p_wheel[i] >= 0.0:
            p = p_drive[i]
        else:
            cap = regen_cap_temp[i] * np.clip((100.0 - s) / 10.0, 0.0, 1.0)
            p = max(p_wheel[i], -cap) * vehicle.regen_eff + p_aux[i]
        p_batt[i] = p
        if i < n - 1:
            e = p * dt[i] / 3600.0                        # Wh at battery terminals
            if e > 0.0:
                e *= calib
            e_wh[i] = e
            d_soc = e / (usable_wh * eta_b[i]) * 100.0
            s = max(0.0, s - d_soc)
            soc[i + 1] = s
            drop += d_soc
            cum_drop[i + 1] = drop

    pos = e_wh[e_wh > 0.0].sum()
    neg = -e_wh[e_wh < 0.0].sum()
    return EnergyResult(
        p_batt_w=p_batt, e_wh=e_wh, soc_pct=soc, dt_s=dt,
        energy_used_kwh=float(pos / 1000.0), energy_regen_kwh=float(neg / 1000.0),
        cum_soc_drop_pct=cum_drop,
    )
