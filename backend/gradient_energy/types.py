"""Typed inputs/outputs for the energy engine. Pure data — no behavior beyond validation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

HvacMode = Literal["off", "heat", "cool"]


@dataclass(frozen=True)
class VehicleSpec:
    mass_kg: float
    cd: float
    frontal_area_m2: float
    c_rr_base: float
    usable_kwh: float
    max_regen_kw: float
    max_dc_kw: float
    charge_curve: tuple[tuple[float, float], ...]  # (soc_pct, kw), soc ascending
    drivetrain_eff: float = 0.90
    regen_eff: float = 0.65
    aux_base_w: float = 350.0
    has_heat_pump: bool = True
    degradation_factor: float = 1.0


@dataclass(frozen=True)
class TripContext:
    start_soc_pct: float
    passengers: int = 1
    cargo_kg: float = 0.0
    hvac_mode: HvacMode = "off"
    cabin_target_c: float = 21.0
    tire_pressure_factor: float = 1.0


@dataclass(frozen=True)
class DriverProfile:
    calibration_factor: float = 1.0


@dataclass
class RouteSamples:
    """Per-sample route arrays, shape (n,). s_m strictly increasing, s_m[0] == 0."""

    s_m: np.ndarray
    elevation_m: np.ndarray
    grade: np.ndarray            # fraction (0.05 = 5%)
    curvature_1pm: np.ndarray    # 1/radius, >= 0
    heading_deg: np.ndarray      # direction of travel, compass degrees
    speed_limit_mps: np.ndarray
    expected_speed_mps: np.ndarray

    def validate(self) -> None:
        arrays = {
            "s_m": self.s_m, "elevation_m": self.elevation_m, "grade": self.grade,
            "curvature_1pm": self.curvature_1pm, "heading_deg": self.heading_deg,
            "speed_limit_mps": self.speed_limit_mps,
            "expected_speed_mps": self.expected_speed_mps,
        }
        shape = self.s_m.shape
        for name, a in arrays.items():
            if a.shape != shape:
                raise ValueError(f"all arrays must have the same shape; {name} differs")
        if self.s_m.size < 2:
            raise ValueError("need at least 2 samples")
        if not np.all(np.diff(self.s_m) > 0):
            raise ValueError("s_m must be strictly increasing")
        if not np.all(self.expected_speed_mps > 0):
            raise ValueError("expected_speed_mps must be positive")

    @property
    def n(self) -> int:
        return int(self.s_m.size)


@dataclass
class WeatherSamples:
    temp_c: np.ndarray
    wind_speed_mps: np.ndarray
    wind_dir_deg: np.ndarray     # meteorological: direction wind blows FROM
    rain_mm_h: np.ndarray
    snow: np.ndarray             # bool array
    humidity_pct: np.ndarray
    pressure_hpa: np.ndarray

    @classmethod
    def uniform(
        cls, n: int, temp_c: float = 15.0, wind_speed_mps: float = 0.0,
        wind_dir_deg: float = 0.0, rain_mm_h: float = 0.0, snow: bool = False,
        humidity_pct: float = 50.0, pressure_hpa: float = 1013.25,
    ) -> "WeatherSamples":
        def full(v: float) -> np.ndarray:
            return np.full(n, v, dtype=np.float64)
        return cls(
            temp_c=full(temp_c), wind_speed_mps=full(wind_speed_mps),
            wind_dir_deg=full(wind_dir_deg), rain_mm_h=full(rain_mm_h),
            snow=np.full(n, snow, dtype=bool), humidity_pct=full(humidity_pct),
            pressure_hpa=full(pressure_hpa),
        )


@dataclass
class EnergyResult:
    """Output of model.integrate(): per-sample power/energy/SoC plus totals."""

    p_batt_w: np.ndarray         # battery power per sample (+ = discharge)
    e_wh: np.ndarray             # per-segment energy at battery, len n (last = 0)
    soc_pct: np.ndarray          # SoC at each sample, soc_pct[0] == start_soc
    dt_s: np.ndarray             # per-segment traversal time, len n (last = 0)
    energy_used_kwh: float       # sum of positive e_wh / 1000
    energy_regen_kwh: float      # -sum of negative e_wh / 1000


@dataclass
class Prediction:
    arrival_soc: float
    best_case_soc: float
    worst_case_soc: float
    confidence: int              # 0-100
    energy_used_kwh: float
    energy_regen_kwh: float
    remaining_range_km: float
    soc_curve: np.ndarray


ChapterClass = Literal["regen", "efficient", "medium", "heavy"]
ChapterCause = Literal["climb", "descent", "wind", "hvac", "speed"]


@dataclass(frozen=True)
class Chapter:
    klass: ChapterClass
    start_m: float
    end_m: float
    delta_soc: float             # signed % (positive = gained)
    cause: ChapterCause
    grade_avg_pct: float
    distance_to_summit_m: float | None = None


@dataclass(frozen=True)
class SpeedBand:
    min_kmh: int
    max_kmh: int
    optimal_kmh: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ChargerCandidate:
    station_id: str
    position_m: float            # distance along route
    power_kw: float
    price_per_kwh: float
    session_fee: float
    reliability: float           # 0-1
    expected_wait_min: float


@dataclass(frozen=True)
class ChargeStop:
    station_id: str
    position_m: float
    arrival_soc: float
    departure_soc: float
    duration_min: float
    cost: float
    expected_wait_min: float


@dataclass(frozen=True)
class ChargingPlan:
    stops: tuple[ChargeStop, ...]
    arrival_soc: float
    total_charge_min: float
    total_cost: float


@dataclass(frozen=True)
class EngineInfo:
    version: str = "0.1.0"


ENGINE_VERSION = EngineInfo().version
