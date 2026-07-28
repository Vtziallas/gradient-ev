"""Energy Timeline: collapse per-sample energy into human-scale chapters."""
from __future__ import annotations

import numpy as np

from gradient_energy.model import headwind_mps, hvac_power_w, integrate
from gradient_energy.profile import next_summit_distance
from gradient_energy.types import (
    Chapter, ChapterCause, ChapterClass, EnergyResult, RouteSamples, TripContext,
    VehicleSpec, WeatherSamples,
)

REGEN_W = -500.0
EFFICIENT_X = 1.1
HEAVY_X = 1.6
HEAVY_GRADE = 0.06
CLASS_NAMES: tuple[ChapterClass, ...] = ("regen", "efficient", "medium", "heavy")


def baseline_wh_per_km(vehicle: VehicleSpec) -> float:
    n = 200
    route = RouteSamples(
        s_m=np.arange(n, dtype=np.float64) * 25.0, elevation_m=np.zeros(n),
        grade=np.zeros(n), curvature_1pm=np.zeros(n), heading_deg=np.zeros(n),
        speed_limit_mps=np.full(n, 25.0), expected_speed_mps=np.full(n, 25.0),
    )
    weather = WeatherSamples.uniform(n, temp_c=25.0)
    res = integrate(route, weather, vehicle, TripContext(start_soc_pct=60.0))
    km = float(route.s_m[-1]) / 1000.0
    return res.energy_used_kwh * 1000.0 / km


def classify_samples(result: EnergyResult, route: RouteSamples,
                     vehicle: VehicleSpec) -> np.ndarray:
    base = baseline_wh_per_km(vehicle)
    v = route.expected_speed_mps
    wh_km = result.p_batt_w / (3.6 * v)
    c = np.full(route.n, 2, dtype=np.int64)                       # medium default
    c[wh_km < EFFICIENT_X * base] = 1
    c[(wh_km >= HEAVY_X * base) | (route.grade > HEAVY_GRADE)] = 3
    c[result.p_batt_w < REGEN_W] = 0
    return c


def _cause(idx: slice, route: RouteSamples, weather: WeatherSamples,
           result: EnergyResult, ctx: TripContext, vehicle: VehicleSpec) -> ChapterCause:
    g = float(np.mean(route.grade[idx]))
    if g > 0.01:
        return "climb"
    if g < -0.01:
        return "descent"
    hw = headwind_mps(weather.wind_speed_mps[idx], weather.wind_dir_deg[idx],
                      route.heading_deg[idx])
    if float(np.mean(hw)) > 3.0:
        return "wind"
    hvac = hvac_power_w(
        WeatherSamples(
            temp_c=weather.temp_c[idx], wind_speed_mps=weather.wind_speed_mps[idx],
            wind_dir_deg=weather.wind_dir_deg[idx], rain_mm_h=weather.rain_mm_h[idx],
            snow=weather.snow[idx], humidity_pct=weather.humidity_pct[idx],
            pressure_hpa=weather.pressure_hpa[idx],
        ), ctx, vehicle)
    p_mean = float(np.mean(np.abs(result.p_batt_w[idx])))
    if p_mean > 0 and float(np.mean(hvac)) / p_mean >= 0.25:
        return "hvac"
    return "speed"


def build_timeline(result: EnergyResult, route: RouteSamples, weather: WeatherSamples,
                   vehicle: VehicleSpec, ctx: TripContext,
                   min_chapter_m: float = 500.0) -> list[Chapter]:
    codes = classify_samples(result, route, vehicle)

    # runs of equal class -> (start_idx, end_idx exclusive)
    change = np.flatnonzero(np.diff(codes)) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [route.n]))

    # merge short runs into the previous run
    merged: list[tuple[int, int, int]] = []                        # (start, end, code)
    for st, en in zip(starts, ends):
        length = float(route.s_m[min(en, route.n - 1)] - route.s_m[st])
        if merged and length < min_chapter_m:
            p_st, p_en, p_code = merged[-1]
            merged[-1] = (p_st, en, p_code)
        else:
            merged.append((int(st), int(en), int(codes[st])))

    chapters: list[Chapter] = []
    for st, en, code in merged:
        idx = slice(st, en)
        last = min(en, route.n) - 1
        delta = float(result.soc_pct[last] - result.soc_pct[st])
        cause = _cause(idx, route, weather, result, ctx, vehicle)
        summit = None
        if cause == "climb":
            summit = next_summit_distance(route.s_m, route.elevation_m, st)
        chapters.append(Chapter(
            klass=CLASS_NAMES[code],
            start_m=float(route.s_m[st]), end_m=float(route.s_m[last]),
            delta_soc=delta, cause=cause,
            grade_avg_pct=float(np.mean(route.grade[idx])) * 100.0,
            distance_to_summit_m=summit,
        ))
    return chapters
