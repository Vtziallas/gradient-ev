"""Battery prediction: point estimate + analytic sensitivity bounds + confidence."""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from gradient_energy.model import headwind_mps, integrate
from gradient_energy.types import (
    DriverProfile, Prediction, RouteSamples, TripContext, VehicleSpec, WeatherSamples,
)

RESERVE_PCT = 10.0
WIND_SIGMA_MPS = 2.0        # headwind perturbation (not raw wind-speed magnitude)
TEMP_SIGMA_C = 3.0
MASS_SIGMA_KG = 100.0
CALIB_PESSIMIST = 1.08
CALIB_OPTIMIST = 0.93


def _shift_weather(w: WeatherSamples, heading_deg: np.ndarray, d_headwind: float,
                   d_temp: float) -> WeatherSamples:
    """Shift temperature by `d_temp` and the HEADWIND component (not raw wind speed
    magnitude) by `d_headwind`, regardless of the current wind direction.

    Perturbing wind_speed_mps directly is direction-unaware: in a tailwind, adding to
    the speed magnitude makes conditions strictly BETTER (stronger tailwind), which
    fights the "worst case" pessimism it's meant to provide and can collapse the
    worst/best spread. Since headwind_mps() is the only place wind speed/direction
    together affect the physics (aero drag), it's equivalent -- and sign-safe -- to
    perturb the resulting headwind scalar directly and re-derive a synthetic
    (speed, direction) pair that reproduces it exactly.
    """
    base_headwind = headwind_mps(w.wind_speed_mps, w.wind_dir_deg, heading_deg)
    new_headwind = base_headwind + d_headwind
    new_speed = np.abs(new_headwind)
    new_dir = np.where(new_headwind >= 0.0, heading_deg, heading_deg + 180.0)
    return WeatherSamples(
        temp_c=w.temp_c + d_temp,
        wind_speed_mps=new_speed,
        wind_dir_deg=new_dir, rain_mm_h=w.rain_mm_h, snow=w.snow,
        humidity_pct=w.humidity_pct, pressure_hpa=w.pressure_hpa,
    )


def predict(route: RouteSamples, weather: WeatherSamples, vehicle: VehicleSpec,
            ctx: TripContext, driver: DriverProfile | None = None, *,
            data_quality: int = 3, weather_age_h: float = 0.0) -> Prediction:
    driver = driver or DriverProfile()
    point = integrate(route, weather, vehicle, ctx, driver)

    worst = integrate(
        route, _shift_weather(weather, route.heading_deg, +WIND_SIGMA_MPS, -TEMP_SIGMA_C),
        vehicle, replace(ctx, cargo_kg=ctx.cargo_kg + MASS_SIGMA_KG),
        DriverProfile(calibration_factor=driver.calibration_factor * CALIB_PESSIMIST),
    )
    best = integrate(
        route, _shift_weather(weather, route.heading_deg, -WIND_SIGMA_MPS, +TEMP_SIGMA_C),
        vehicle, ctx,
        DriverProfile(calibration_factor=driver.calibration_factor * CALIB_OPTIMIST),
    )

    route_km = float(route.s_m[-1]) / 1000.0
    confidence = (
        100.0
        - 5.0 * (5 - max(1, min(5, data_quality)))
        - min(15.0, 2.0 * max(0.0, weather_age_h))
        - min(10.0, route_km / 50.0)
        - min(20.0, 200.0 * abs(driver.calibration_factor - 1.0))
    )

    arrival = float(point.soc_pct[-1])
    net_kwh = point.energy_used_kwh - point.energy_regen_kwh
    avg_kwh_per_km = max(net_kwh / route_km, 0.05) if route_km > 0 else 0.15
    usable = vehicle.usable_kwh * vehicle.degradation_factor
    remaining_km = max(0.0, arrival - RESERVE_PCT) / 100.0 * usable / avg_kwh_per_km

    return Prediction(
        arrival_soc=arrival,
        best_case_soc=float(best.soc_pct[-1]),
        worst_case_soc=float(worst.soc_pct[-1]),
        confidence=int(np.clip(confidence, 5, 99)),
        energy_used_kwh=point.energy_used_kwh,
        energy_regen_kwh=point.energy_regen_kwh,
        remaining_range_km=float(remaining_km),
        soc_curve=point.soc_pct,
    )
