# gradient_energy Physics Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure-Python physics energy engine (`gradient_energy`) — forces → power → SoC integration → prediction, timeline, speed band, charging optimizer, twin filter — fully tested per docs/EnergyEngine.md.

**Architecture:** A zero-I/O package: typed frozen configs + NumPy arrays in, typed results out. Vectorized force/power math; a thin sequential loop only for the SoC-coupled regen clamp. Every number the product shows traces to a function here.

**Tech Stack:** Python 3.12, NumPy, SciPy (savgol), pytest, Hypothesis, ruff, mypy (strict), uv.

## Global Constraints

- Package path: `backend/gradient_energy/`; tests in `backend/tests/engine/`. No imports from any `app.*` (doesn't exist yet; never allowed per BackendArchitecture.md).
- No I/O anywhere in the package: no file, network, or DB access; no logging side effects.
- All array inputs/outputs are `np.ndarray` of `float64`, shape `(n,)`; SI units internally (m, s, kg, W, J); SoC in percent (0–100); public results expose kWh/km/kmh only where named so.
- Physics constants: `G = 9.80665`, `R_D = 287.05`, `R_V = 461.5`, rotational inertia factor `1.05`.
- Speed band NEVER exceeds `speed_limit` — unwaivable test (Testing.md §1).
- Charging plan NEVER drops SoC below reserve — unwaivable test.
- Display smoothing contract: shown arrival SoC slews ≤ 0.5 %/s, moves only after 3 consecutive consistent seconds.
- Performance: full pipeline for 10 000 samples < 50 ms (perf test, generous CI margin ×4).
- Every commit message: `feat(engine): …` / `test(engine): …`; run `ruff check backend && mypy backend/gradient_energy` before each commit.
- Run commands from `backend/` with `uv run pytest …`.

## File Structure

```
backend/
├── pyproject.toml               # project + tool config (Task 1)
├── gradient_energy/
│   ├── __init__.py              # public API re-exports
│   ├── types.py                 # VehicleSpec, TripContext, DriverProfile, RouteSamples,
│   │                            #   WeatherSamples, EnergyResult, Prediction, Chapter,
│   │                            #   SpeedBand, ChargerCandidate, ChargeStop, ChargingPlan
│   ├── profile.py               # elevation smoothing, grade, summit finding
│   ├── model.py                 # air density, headwind, forces, power, SoC integration
│   ├── prediction.py            # predict(): point + best/worst + confidence + range
│   ├── timeline.py              # energy chapters
│   ├── speed.py                 # safe efficiency speed band
│   ├── charging.py              # DP charge-stop optimizer
│   └── twin.py                  # Kalman calibration filter + display smoother
└── tests/
    ├── engine/
    │   ├── conftest.py          # shared fixtures (vehicle, flat/hill routes)
    │   ├── test_types.py … test_twin.py   (one per module)
    │   ├── test_properties.py   # Hypothesis invariants
    │   ├── test_analytic.py     # closed-form fixtures + perf budget
    │   └── test_golden.py       # golden-trip harness
    └── testdata/golden_trips/   # *.json (synthetic seeds now, real data at Alpha)
```

---

### Task 1: Package scaffold + core types

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/gradient_energy/__init__.py`
- Create: `backend/gradient_energy/types.py`
- Create: `backend/tests/engine/__init__.py` (empty), `backend/tests/engine/conftest.py`
- Test: `backend/tests/engine/test_types.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: every dataclass below, exactly as typed — all later tasks import from `gradient_energy.types`. Key constructors: `VehicleSpec(mass_kg, cd, frontal_area_m2, c_rr_base, usable_kwh, max_regen_kw, max_dc_kw, charge_curve, …)`, `RouteSamples(s_m, elevation_m, grade, curvature_1pm, heading_deg, speed_limit_mps, expected_speed_mps)`, `WeatherSamples(temp_c, wind_speed_mps, wind_dir_deg, rain_mm_h, snow, humidity_pct, pressure_hpa)`. `RouteSamples.validate()` raises `ValueError` on bad shapes/order.

- [ ] **Step 1: Write pyproject**

```toml
[project]
name = "gradient-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["numpy>=1.26", "scipy>=1.12"]

[dependency-groups]
dev = ["pytest>=8", "hypothesis>=6.100", "ruff>=0.4", "mypy>=1.10"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
strict = true
plugins = []

[[tool.mypy.overrides]]
module = "scipy.*"
ignore_missing_imports = true
```

- [ ] **Step 2: Write the failing test**

`backend/tests/engine/test_types.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/engine/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gradient_energy'`

- [ ] **Step 4: Implement types**

`backend/gradient_energy/types.py`:

```python
"""Typed inputs/outputs for the energy engine. Pure data — no behavior beyond validation."""
from __future__ import annotations

from dataclasses import dataclass, field
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
        full = lambda v: np.full(n, v, dtype=np.float64)  # noqa: E731
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
```

`backend/gradient_energy/__init__.py`:

```python
from gradient_energy.types import (  # noqa: F401
    ENGINE_VERSION, Chapter, ChargeStop, ChargerCandidate, ChargingPlan,
    DriverProfile, EnergyResult, Prediction, RouteSamples, SpeedBand,
    TripContext, VehicleSpec, WeatherSamples,
)
```

`backend/tests/engine/conftest.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv sync && uv run pytest tests/engine/test_types.py -v`
Expected: 6 PASS

- [ ] **Step 6: Lint, typecheck, commit**

```bash
cd backend && uv run ruff check . && uv run mypy gradient_energy
git add backend
git commit -m "feat(engine): package scaffold and core types"
```

---

### Task 2: Elevation profile — smoothing, grade, summits

**Files:**
- Create: `backend/gradient_energy/profile.py`
- Test: `backend/tests/engine/test_profile.py`

**Interfaces:**
- Consumes: nothing from other modules (raw arrays only).
- Produces:
  - `smooth_elevation(elevation_m: np.ndarray, window: int = 11, polyorder: int = 3) -> np.ndarray`
  - `compute_grade(s_m: np.ndarray, elevation_m: np.ndarray, clamp: float = 0.25) -> np.ndarray` (len n; grade[i] = forward difference, last repeats previous; light second smoothing pass window 5)
  - `next_summit_distance(s_m, elevation_m, start_index: int) -> float | None` (distance from `s_m[start_index]` to the next local max at least 2 m above start elevation; None if none ahead)

- [ ] **Step 1: Write the failing test**

`backend/tests/engine/test_profile.py`:

```python
import numpy as np

from gradient_energy.profile import compute_grade, next_summit_distance, smooth_elevation


def test_smoothing_removes_noise_but_preserves_ascent():
    rng = np.random.default_rng(42)
    s = np.arange(1000, dtype=np.float64) * 25.0
    clean = np.where(s < 12500, s * 0.05, 625.0)          # 5% climb then flat
    noisy = clean + rng.normal(0.0, 2.0, s.size)          # DEM noise ~2 m
    smoothed = smooth_elevation(noisy)
    ascent = lambda h: float(np.sum(np.clip(np.diff(h), 0, None)))  # noqa: E731
    assert abs(ascent(smoothed) - ascent(clean)) / ascent(clean) < 0.05
    assert np.max(np.abs(smoothed - clean)) < 5.0


def test_smoothing_flattens_bridge_spike():
    s = np.arange(200, dtype=np.float64) * 25.0
    h = np.zeros(200)
    h[100] = 40.0                                         # single-sample DEM artifact
    g = compute_grade(s, smooth_elevation(h))
    assert np.max(np.abs(g)) < 0.08                       # raw spike would be 1.6


def test_grade_forward_difference_and_clamp():
    s = np.array([0.0, 25.0, 50.0, 75.0])
    h = np.array([0.0, 1.25, 2.5, 40.0])                  # last step = 150% -> clamp
    g = compute_grade(s, h)
    assert g.shape == (4,)
    assert abs(g[0] - 0.05) < 0.02
    assert np.max(g) <= 0.25 + 1e-9
    assert g[-1] == g[-2]                                 # last repeats


def test_next_summit_distance():
    s = np.arange(9, dtype=np.float64) * 100.0
    h = np.array([0.0, 10, 20, 30, 25, 20, 30, 45, 40.0])  # local max @3, higher @7
    assert next_summit_distance(s, h, 0) == 300.0
    assert next_summit_distance(s, h, 4) == 300.0          # from idx4 -> summit @7
    assert next_summit_distance(s, h, 8) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/engine/test_profile.py -v`
Expected: FAIL — `ModuleNotFoundError: gradient_energy.profile`

- [ ] **Step 3: Implement**

`backend/gradient_energy/profile.py`:

```python
"""Elevation profile conditioning: DEM noise removal, grade, summit lookup.

Smoothing choice per EnergyEngine.md: Savitzky-Golay preserves real grades while
killing single-sample DEM artifacts (bridges, tunnels).
"""
from __future__ import annotations

import numpy as np
from scipy.signal import savgol_filter


def smooth_elevation(elevation_m: np.ndarray, window: int = 11, polyorder: int = 3) -> np.ndarray:
    n = elevation_m.size
    if n < window:
        window = n if n % 2 == 1 else n - 1
        polyorder = min(polyorder, window - 1)
    if window < 3:
        return elevation_m.astype(np.float64)
    return savgol_filter(elevation_m.astype(np.float64), window, polyorder)


def compute_grade(s_m: np.ndarray, elevation_m: np.ndarray, clamp: float = 0.25) -> np.ndarray:
    dh = np.diff(elevation_m)
    ds = np.diff(s_m)
    g = np.clip(dh / ds, -clamp, clamp)
    g = np.append(g, g[-1])                     # len n; last repeats previous
    if g.size >= 5:                             # light second pass on grade itself
        g = savgol_filter(g, 5, 2)
        g = np.clip(g, -clamp, clamp)
    return g


def next_summit_distance(
    s_m: np.ndarray, elevation_m: np.ndarray, start_index: int, min_prominence_m: float = 2.0
) -> float | None:
    h = elevation_m
    n = h.size
    for i in range(max(start_index + 1, 1), n - 1):
        if h[i] >= h[i - 1] and h[i] > h[i + 1] and h[i] - h[start_index] >= min_prominence_m:
            return float(s_m[i] - s_m[start_index])
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/engine/test_profile.py -v`
Expected: 4 PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
cd backend && uv run ruff check . && uv run mypy gradient_energy
git add backend && git commit -m "feat(engine): elevation smoothing, grade, summit lookup"
```

---

### Task 3: Environment & forces

**Files:**
- Create: `backend/gradient_energy/model.py` (environment + forces half)
- Test: `backend/tests/engine/test_model_forces.py`

**Interfaces:**
- Consumes: `VehicleSpec, TripContext, RouteSamples, WeatherSamples` from types.
- Produces (all vectorized over samples):
  - `air_density(temp_c, pressure_hpa, humidity_pct) -> np.ndarray` (kg/m³)
  - `headwind_mps(wind_speed_mps, wind_dir_deg, heading_deg) -> np.ndarray` (+ = headwind)
  - `effective_mass_kg(vehicle, ctx) -> float` (`mass + 75·passengers + cargo`)
  - `rolling_coeff(vehicle, ctx, weather) -> np.ndarray`
  - `compute_forces(route, weather, vehicle, ctx) -> Forces` — dataclass with `f_roll_n, f_aero_n, f_grade_n, f_accel_n, f_total_n` arrays. Acceleration between samples: `a[i] = (v[i+1]² − v[i]²) / (2·Δs)`, last = 0.
  - Module constants `G, R_D, R_V, ROT_INERTIA = 1.05`.

- [ ] **Step 1: Write the failing test**

`backend/tests/engine/test_model_forces.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/engine/test_model_forces.py -v`
Expected: FAIL — `ModuleNotFoundError: gradient_energy.model`

- [ ] **Step 3: Implement**

`backend/gradient_energy/model.py`:

```python
"""Physics core: environment, forces, power, SoC integration (EnergyEngine.md §2)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gradient_energy.types import (
    DriverProfile, EnergyResult, RouteSamples, TripContext, VehicleSpec, WeatherSamples,
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
    return wind_speed_mps * np.cos(np.radians(wind_dir_deg - heading_deg))


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/engine/test_model_forces.py -v`
Expected: 8 PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
cd backend && uv run ruff check . && uv run mypy gradient_energy
git add backend && git commit -m "feat(engine): air density, headwind, force model"
```

---

### Task 4: Power model — drivetrain, regen derating, HVAC/aux

**Files:**
- Modify: `backend/gradient_energy/model.py` (append)
- Test: `backend/tests/engine/test_model_power.py`

**Interfaces:**
- Consumes: `Forces` from Task 3.
- Produces:
  - `hvac_power_w(weather, ctx, vehicle) -> np.ndarray`
  - `aux_power_w(weather, ctx, vehicle) -> np.ndarray` (= base + hvac + 250 electronics)
  - `regen_derate(soc_pct: float | np.ndarray, temp_c) -> float | np.ndarray` (soc factor `clip((100−soc)/10, 0, 1)` × temp factor `clip(0.4 + 0.6·(temp+10)/15, 0.4, 1.0)`)
  - `battery_power_w(forces, route, weather, vehicle, ctx, soc_pct) -> np.ndarray` — spec §2 branch; `soc_pct` scalar used for the vectorized first pass (integration loop refines).
  - `battery_eff(temp_c) -> np.ndarray` (1.0 at ≥10 °C → 0.92 at ≤ −5 °C, linear).

- [ ] **Step 1: Write the failing test**

`backend/tests/engine/test_model_power.py`:

```python
import numpy as np

from gradient_energy.model import (
    aux_power_w, battery_eff, battery_power_w, compute_forces, hvac_power_w, regen_derate,
)
from gradient_energy.types import TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route, hill_route


def test_hvac_off_is_zero_and_heating_scales_with_delta_t():
    off = TripContext(start_soc_pct=80.0, hvac_mode="off")
    heat = TripContext(start_soc_pct=80.0, hvac_mode="heat", cabin_target_c=21.0)
    cold = WeatherSamples.uniform(4, temp_c=-5.0)
    mild = WeatherSamples.uniform(4, temp_c=15.0)
    assert np.all(hvac_power_w(cold, off, MODEL3) == 0.0)
    assert np.all(hvac_power_w(cold, heat, MODEL3) > hvac_power_w(mild, heat, MODEL3))


def test_heat_pump_beats_resistive():
    heat = TripContext(start_soc_pct=80.0, hvac_mode="heat")
    cold = WeatherSamples.uniform(4, temp_c=-5.0)
    resistive = MODEL3.__class__(**{**MODEL3.__dict__, "has_heat_pump": False})
    assert np.all(hvac_power_w(cold, heat, MODEL3) < hvac_power_w(cold, heat, resistive))


def test_aux_includes_base_and_electronics():
    ctx = TripContext(start_soc_pct=80.0)
    w = WeatherSamples.uniform(4)
    assert np.allclose(aux_power_w(w, ctx, MODEL3), 350.0 + 250.0)


def test_regen_derate_soc_and_temperature():
    assert regen_derate(80.0, np.array([20.0]))[0] == 1.0
    assert abs(regen_derate(95.0, np.array([20.0]))[0] - 0.5) < 1e-9
    assert regen_derate(100.0, np.array([20.0]))[0] == 0.0
    assert abs(regen_derate(50.0, np.array([-10.0]))[0] - 0.4) < 1e-9


def test_battery_power_drive_and_regen_branches():
    ctx = TripContext(start_soc_pct=80.0)
    r = hill_route(n=100)
    w = WeatherSamples.uniform(100)
    f = compute_forces(r, w, MODEL3, ctx)
    p = battery_power_w(f, r, w, MODEL3, ctx, soc_pct=80.0)
    assert np.all(p[:49] > 0)                              # climbing draws power
    assert np.all(p[51:98] < 0)                            # descending 5% at 20 m/s regens
    # drive branch: p = wheel/eta + aux  => strictly greater than wheel power
    wheel = f.f_total_n * r.expected_speed_mps
    assert np.all(p[:49] > wheel[:49])


def test_regen_clamped_to_max_regen_kw():
    ctx = TripContext(start_soc_pct=50.0)
    r = hill_route(n=100, grade=0.20, speed_mps=45.0)      # extreme descent: exceeds the
    w = WeatherSamples.uniform(100)                        # 120 kW cap at soc=50 (full
    f = compute_forces(r, w, MODEL3, ctx)                  # regen headroom), so the clamp
    p = battery_power_w(f, r, w, MODEL3, ctx, soc_pct=50.0)  # must actually engage here
    aux = aux_power_w(w, ctx, MODEL3)
    floor = -MODEL3.max_regen_kw * 1000.0 * MODEL3.regen_eff + aux
    assert np.all(p >= floor - 1e-6)
    assert np.any(np.isclose(p, floor, atol=1e-6))         # clamp must actually bind somewhere


def test_battery_eff_cold_penalty():
    eff = battery_eff(np.array([20.0, 0.0, -5.0, -20.0]))
    assert eff[0] == 1.0
    assert 0.92 < eff[1] < 1.0
    assert abs(eff[2] - 0.92) < 1e-9 and abs(eff[3] - 0.92) < 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/engine/test_model_power.py -v`
Expected: FAIL — `ImportError: cannot import name 'hvac_power_w'`

- [ ] **Step 3: Implement — append to `model.py`**

```python
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


def regen_derate(soc_pct: float | np.ndarray, temp_c: np.ndarray) -> np.ndarray:
    f_soc = np.clip((100.0 - np.asarray(soc_pct, dtype=np.float64)) / 10.0, 0.0, 1.0)
    f_temp = np.clip(0.4 + 0.6 * (temp_c + 10.0) / 15.0, 0.4, 1.0)
    return f_soc * f_temp


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
    return np.where(p_wheel >= 0.0, drive, regen)
```

Note: `battery_eff` reduces linearly from 1.0 at 10 °C to the 0.92 floor at −5 °C
(the `0.08/0.12` factor maps the 15 K span onto an 8 % penalty).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/engine/test_model_power.py -v`
Expected: 7 PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
cd backend && uv run ruff check . && uv run mypy gradient_energy
git add backend && git commit -m "feat(engine): power model with regen derating and HVAC"
```

---

### Task 5: SoC integration

**Files:**
- Modify: `backend/gradient_energy/model.py` (append)
- Test: `backend/tests/engine/test_model_integrate.py`

**Interfaces:**
- Consumes: Tasks 3–4 functions.
- Produces: `integrate(route, weather, vehicle, ctx, driver: DriverProfile | None = None) -> EnergyResult`. Vectorized power pass at start SoC, then a sequential loop that re-clamps regen when running SoC > 90 %; calibration factor multiplies discharge energy only. This is THE core function — prediction, timeline, charging all consume `EnergyResult`.

- [ ] **Step 1: Write the failing test**

`backend/tests/engine/test_model_integrate.py`:

```python
import numpy as np

from gradient_energy.model import integrate
from gradient_energy.types import DriverProfile, TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route, hill_route


def test_flat_route_matches_closed_form():
    r = flat_route(n=400, speed_mps=25.0)                 # ~10 km at 90 km/h
    w = WeatherSamples.uniform(400)
    ctx = TripContext(start_soc_pct=80.0)
    res = integrate(r, w, MODEL3, ctx)
    # closed form: (F_roll + F_aero)*d/eta + P_aux*t, converted to Wh
    d = r.s_m[-1]
    t = d / 25.0
    f = 0.010 * (1850.0 + 75.0) * 9.80665 + 0.5 * 1.2245 * 0.23 * 2.22 * 625.0
    e_expected_wh = (f * d / 0.90 + 600.0 * t) / 3600.0
    assert abs(res.energy_used_kwh * 1000.0 - e_expected_wh) / e_expected_wh < 0.02
    assert res.soc_pct[0] == 80.0
    assert res.soc_pct[-1] < 80.0
    assert res.energy_regen_kwh == 0.0


def test_hill_regen_recovers_some_energy():
    r = hill_route(n=800)
    w = WeatherSamples.uniform(800)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    assert res.energy_regen_kwh > 0.5
    mid = res.soc_pct[400]
    assert res.soc_pct[-1] > mid                          # descent recovers SoC


def test_regen_recovery_never_exceeds_climb_cost():
    r = hill_route(n=800)
    w = WeatherSamples.uniform(800)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    assert res.soc_pct[-1] < res.soc_pct[0]               # round trip loses energy


def test_high_soc_suppresses_regen():
    r = hill_route(n=800)
    w = WeatherSamples.uniform(800)
    hi = integrate(r, w, MODEL3, TripContext(start_soc_pct=99.5))
    lo = integrate(r, w, MODEL3, TripContext(start_soc_pct=60.0))
    assert hi.energy_regen_kwh < lo.energy_regen_kwh


def test_calibration_factor_scales_consumption():
    r = flat_route(n=400)
    w = WeatherSamples.uniform(400)
    ctx = TripContext(start_soc_pct=80.0)
    base = integrate(r, w, MODEL3, ctx)
    hot = integrate(r, w, MODEL3, ctx, DriverProfile(calibration_factor=1.10))
    assert abs(hot.energy_used_kwh / base.energy_used_kwh - 1.10) < 1e-6


def test_soc_never_negative_and_dt_shapes():
    r = flat_route(n=2000)
    w = WeatherSamples.uniform(2000)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=1.0))
    assert np.all(res.soc_pct >= 0.0)
    assert res.dt_s.shape == (2000,) and res.dt_s[-1] == 0.0
    assert res.e_wh.shape == (2000,) and res.e_wh[-1] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/engine/test_model_integrate.py -v`
Expected: FAIL — `ImportError: cannot import name 'integrate'`

- [ ] **Step 3: Implement — append to `model.py`**

```python
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
    regen_cap_temp = vehicle.max_regen_kw * 1000.0 * np.clip(
        0.4 + 0.6 * (weather.temp_c + 10.0) / 15.0, 0.4, 1.0)

    s = ctx.start_soc_pct
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
            s = max(0.0, s - e / (usable_wh * eta_b[i]) * 100.0)
            soc[i + 1] = s

    pos = e_wh[e_wh > 0.0].sum()
    neg = -e_wh[e_wh < 0.0].sum()
    return EnergyResult(
        p_batt_w=p_batt, e_wh=e_wh, soc_pct=soc, dt_s=dt,
        energy_used_kwh=float(pos / 1000.0), energy_regen_kwh=float(neg / 1000.0),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/engine/test_model_integrate.py -v`
Expected: 6 PASS

- [ ] **Step 5: Run the whole suite, lint, commit**

Run: `cd backend && uv run pytest -q && uv run ruff check . && uv run mypy gradient_energy`
Expected: all green

```bash
git add backend && git commit -m "feat(engine): SoC integration with regen-SoC coupling"
```

---

### Task 6: Prediction — point, best/worst, confidence, range

**Files:**
- Create: `backend/gradient_energy/prediction.py`
- Test: `backend/tests/engine/test_prediction.py`

**Interfaces:**
- Consumes: `integrate` (Task 5); types.
- Produces: `predict(route, weather, vehicle, ctx, driver=None, *, data_quality: int = 3, weather_age_h: float = 0.0) -> Prediction`.
  - Worst case: recompute with `WeatherSamples` wind +2 m/s (as added headwind via wind_speed), temp −3 °C, ctx cargo +100 kg, calibration ×1.08. Best case: symmetric opposite (calibration ×0.93, cargo −0 floor).
  - Confidence heuristic (clamped 5–99): `100 − 5·(5 − data_quality) − min(15, 2·weather_age_h) − min(10, route_km/50) − min(20, 200·|calib−1|)`.
  - `remaining_range_km = max(0, arrival_soc − 10) / 100 · usable_kwh·degradation / (trip_avg_kwh_per_km)`.

- [ ] **Step 1: Write the failing test**

`backend/tests/engine/test_prediction.py`:

```python
import numpy as np

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/engine/test_prediction.py -v`
Expected: FAIL — `ModuleNotFoundError: gradient_energy.prediction`

- [ ] **Step 3: Implement**

`backend/gradient_energy/prediction.py`:

```python
"""Battery prediction: point estimate + analytic sensitivity bounds + confidence."""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from gradient_energy.model import integrate
from gradient_energy.types import (
    DriverProfile, Prediction, RouteSamples, TripContext, VehicleSpec, WeatherSamples,
)

RESERVE_PCT = 10.0
WIND_SIGMA_MPS = 2.0
TEMP_SIGMA_C = 3.0
MASS_SIGMA_KG = 100.0
CALIB_PESSIMIST = 1.08
CALIB_OPTIMIST = 0.93


def _shift_weather(w: WeatherSamples, d_wind: float, d_temp: float) -> WeatherSamples:
    return WeatherSamples(
        temp_c=w.temp_c + d_temp,
        wind_speed_mps=np.clip(w.wind_speed_mps + d_wind, 0.0, None),
        wind_dir_deg=w.wind_dir_deg, rain_mm_h=w.rain_mm_h, snow=w.snow,
        humidity_pct=w.humidity_pct, pressure_hpa=w.pressure_hpa,
    )


def predict(route: RouteSamples, weather: WeatherSamples, vehicle: VehicleSpec,
            ctx: TripContext, driver: DriverProfile | None = None, *,
            data_quality: int = 3, weather_age_h: float = 0.0) -> Prediction:
    driver = driver or DriverProfile()
    point = integrate(route, weather, vehicle, ctx, driver)

    worst = integrate(
        route, _shift_weather(weather, +WIND_SIGMA_MPS, -TEMP_SIGMA_C), vehicle,
        replace(ctx, cargo_kg=ctx.cargo_kg + MASS_SIGMA_KG),
        DriverProfile(calibration_factor=driver.calibration_factor * CALIB_PESSIMIST),
    )
    best = integrate(
        route, _shift_weather(weather, -WIND_SIGMA_MPS, +TEMP_SIGMA_C), vehicle, ctx,
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/engine/test_prediction.py -v`
Expected: 4 PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
cd backend && uv run ruff check . && uv run mypy gradient_energy
git add backend && git commit -m "feat(engine): prediction with sensitivity bounds and confidence"
```

---

### Task 7: Energy Timeline chapters

**Files:**
- Create: `backend/gradient_energy/timeline.py`
- Test: `backend/tests/engine/test_timeline.py`

**Interfaces:**
- Consumes: `EnergyResult` (Task 5), `next_summit_distance` (Task 2), `hvac_power_w`/`headwind_mps` (Tasks 3–4).
- Produces:
  - `baseline_wh_per_km(vehicle) -> float` — flat road, 25 °C, no wind, 90 km/h, solo driver, hvac off (runs `integrate` on a synthetic 5 km flat route).
  - `classify_samples(result, route, vehicle) -> np.ndarray` of int codes `0=regen,1=efficient,2=medium,3=heavy` (regen if `p_batt < −500`; else Wh/km = `p_batt/(3.6·v)` vs thresholds `1.1×` / `1.6×` baseline; heavy also whenever `grade > 0.06`).
  - `build_timeline(result, route, weather, vehicle, ctx, min_chapter_m: float = 500.0) -> list[Chapter]` — contiguous runs, sub-500 m runs merged into the previous chapter; per-chapter cause: `climb` if mean grade > 1 %, `descent` if < −1 %, `wind` if mean headwind > 3 m/s, `hvac` if hvac ≥ 25 % of mean battery power, else `speed`; climbs get `distance_to_summit_m`.

- [ ] **Step 1: Write the failing test**

`backend/tests/engine/test_timeline.py`:

```python
import numpy as np

from gradient_energy.model import integrate
from gradient_energy.timeline import baseline_wh_per_km, build_timeline, classify_samples
from gradient_energy.types import TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route, hill_route


def test_baseline_is_sane_for_efficient_ev():
    b = baseline_wh_per_km(MODEL3)
    assert 120.0 < b < 220.0                              # Model 3-class at 90 km/h


def test_classify_hill_route():
    r = hill_route(n=800)
    w = WeatherSamples.uniform(800)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    c = classify_samples(res, r, MODEL3)
    assert set(np.unique(c[:390])) <= {2, 3} and 3 in c[:390]   # climb: medium/heavy
    assert np.all(c[410:790] == 0)                              # descent: regen


def test_build_timeline_chapters_merge_and_causes():
    r = hill_route(n=800)                                 # 10 km up, 10 km down
    w = WeatherSamples.uniform(800)
    ctx = TripContext(start_soc_pct=80.0)
    res = integrate(r, w, MODEL3, ctx)
    chapters = build_timeline(res, r, w, MODEL3, ctx)
    assert 2 <= len(chapters) <= 4                        # no flicker
    assert chapters[0].cause == "climb" and chapters[0].delta_soc < 0
    assert chapters[0].distance_to_summit_m is not None
    assert chapters[-1].klass == "regen" and chapters[-1].delta_soc > 0
    total = sum(ch.delta_soc for ch in chapters)
    assert abs(total - (res.soc_pct[-1] - res.soc_pct[0])) < 0.05
    for ch in chapters:
        assert ch.end_m - ch.start_m >= 500.0 or ch is chapters[-1]


def test_headwind_cause_on_flat():
    r = flat_route(n=800)
    w = WeatherSamples.uniform(800, wind_speed_mps=8.0, wind_dir_deg=0.0)  # pure headwind
    ctx = TripContext(start_soc_pct=80.0)
    res = integrate(r, w, MODEL3, ctx)
    chapters = build_timeline(res, r, w, MODEL3, ctx)
    assert any(ch.cause == "wind" for ch in chapters)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/engine/test_timeline.py -v`
Expected: FAIL — `ModuleNotFoundError: gradient_energy.timeline`

- [ ] **Step 3: Implement**

`backend/gradient_energy/timeline.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/engine/test_timeline.py -v`
Expected: 4 PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
cd backend && uv run ruff check . && uv run mypy gradient_energy
git add backend && git commit -m "feat(engine): energy timeline chapter generation"
```

---

### Task 8: Safe efficiency speed band

**Files:**
- Create: `backend/gradient_energy/speed.py`
- Test: `backend/tests/engine/test_speed.py`

**Interfaces:**
- Consumes: force/power helpers (Tasks 3–4).
- Produces: `efficiency_band(*, grade: float, curvature_1pm: float, speed_limit_mps: float, traffic_flow_mps: float | None, weather_point: WeatherPoint, vehicle: VehicleSpec, ctx: TripContext) -> SpeedBand | None` plus `WeatherPoint` scalar dataclass (`temp_c, headwind_mps, rain_mm_h, snow, humidity_pct, pressure_hpa`). Energy per meter `e(v) = F_total(v)/η + P_aux/v` (regen branch `F_total·η_regen + P_aux/v` when negative). Grid 8 m/s → cap, 1 km/h steps. Band = `e ≤ 1.02·e(v*)` ∩ constraints. Returns `None` when no feasible speed. Reasons vocabulary: `grade_up`, `grade_down`, `headwind`, `curve`, `traffic`, `rain`, `snow`, `aero`.

- [ ] **Step 1: Write the failing test**

`backend/tests/engine/test_speed.py`:

```python
from gradient_energy.speed import WeatherPoint, efficiency_band
from gradient_energy.types import TripContext
from tests.engine.conftest import MODEL3

CALM = WeatherPoint(temp_c=15.0, headwind_mps=0.0, rain_mm_h=0.0, snow=False,
                    humidity_pct=50.0, pressure_hpa=1013.25)
CTX = TripContext(start_soc_pct=60.0)


def band(**kw):
    args = dict(grade=0.0, curvature_1pm=0.0, speed_limit_mps=36.11,   # 130 km/h
                traffic_flow_mps=None, weather_point=CALM, vehicle=MODEL3, ctx=CTX)
    args.update(kw)
    return efficiency_band(**args)


def test_never_exceeds_speed_limit_UNWAIVABLE():
    for limit in (13.89, 22.22, 27.78, 36.11):            # 50/80/100/130 km/h
        for g in (-0.08, 0.0, 0.05, 0.10):
            b = band(grade=g, speed_limit_mps=limit)
            assert b is not None
            assert b.max_kmh <= int(limit * 3.6) + 0      # hard cap, no rounding up


def test_band_is_ordered_and_contains_optimum():
    b = band()
    assert b.min_kmh <= b.optimal_kmh <= b.max_kmh


def test_climb_lowers_optimal_speed_vs_flat_highway():
    flat = band(speed_limit_mps=36.11)
    climb = band(grade=0.06, speed_limit_mps=36.11)
    assert climb.optimal_kmh < flat.optimal_kmh
    assert "grade_up" in climb.reasons


def test_headwind_lowers_optimum_and_is_reported():
    windy = WeatherPoint(temp_c=15.0, headwind_mps=8.0, rain_mm_h=0.0, snow=False,
                         humidity_pct=50.0, pressure_hpa=1013.25)
    b = band(weather_point=windy)
    assert b.optimal_kmh < band().optimal_kmh
    assert "headwind" in b.reasons


def test_curvature_caps_speed():
    b = band(curvature_1pm=1.0 / 60.0)                    # 60 m radius curve
    v_cap_kmh = (2.5 * 60.0) ** 0.5 * 3.6                 # ~44 km/h
    assert b.max_kmh <= int(v_cap_kmh) + 1
    assert "curve" in b.reasons


def test_traffic_floor_respected():
    b = band(traffic_flow_mps=25.0)
    assert b.min_kmh >= int(0.85 * 25.0 * 3.6)
    assert "traffic" in b.reasons


def test_snow_caps_speed():
    snowy = WeatherPoint(temp_c=-2.0, headwind_mps=0.0, rain_mm_h=0.0, snow=True,
                         humidity_pct=80.0, pressure_hpa=1013.25)
    b = band(weather_point=snowy, speed_limit_mps=36.11)
    assert b.max_kmh <= int(0.7 * 130.0) + 1
    assert "snow" in b.reasons


def test_infeasible_returns_none():
    assert band(curvature_1pm=1.0, traffic_flow_mps=35.0) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/engine/test_speed.py -v`
Expected: FAIL — `ModuleNotFoundError: gradient_energy.speed`

- [ ] **Step 3: Implement**

`backend/gradient_energy/speed.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/engine/test_speed.py -v`
Expected: 8 PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
cd backend && uv run ruff check . && uv run mypy gradient_energy
git add backend && git commit -m "feat(engine): safe efficiency speed band with legal-limit cap"
```

---

### Task 9: Charging DP optimizer

**Files:**
- Create: `backend/gradient_energy/charging.py`
- Test: `backend/tests/engine/test_charging.py`

**Interfaces:**
- Consumes: `EnergyResult` (cumulative energy via `e_wh`), `VehicleSpec.charge_curve`, `ChargerCandidate/ChargeStop/ChargingPlan` types.
- Produces:
  - `charge_minutes(vehicle, from_soc, to_soc, station_kw) -> float` — integrate `0.01·usable_kwh / min(curve(soc), station_kw)` per 1 % step (curve linearly interpolated).
  - `optimize(result: EnergyResult, route_s_m: np.ndarray, candidates: list[ChargerCandidate], vehicle, *, start_soc: float, reserve_soc: float = 10.0, min_arrival_soc: float = 15.0, max_charge_soc: float = 90.0, alpha_min: float = 1.0, beta_eur: float = 3.0, gamma_rel: float = 10.0) -> ChargingPlan | None` — DP over (candidate, arrival-SoC 1 % grid); departure SoC choices in 5 % steps up to `max_charge_soc`; cost = `alpha·(charge_min + wait) + beta·cost_eur + gamma·(1/reliability − 1)`. Returns `None` if infeasible; returns empty-stops plan if no charge needed.

- [ ] **Step 1: Write the failing test**

`backend/tests/engine/test_charging.py`:

```python
import numpy as np

from gradient_energy.charging import charge_minutes, optimize
from gradient_energy.model import integrate
from gradient_energy.types import ChargerCandidate, TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route


def long_flat(km: float = 400.0):
    n = int(km * 1000 / 50) + 1
    r = flat_route(n=n, spacing_m=50.0, speed_mps=30.55)   # 110 km/h
    w = WeatherSamples.uniform(n)
    return r, w


def cands(*positions_km: float, kw: float = 150.0, price: float = 0.55,
          rel: float = 0.95, wait: float = 2.0):
    return [ChargerCandidate(station_id=f"st{i}", position_m=p * 1000.0, power_kw=kw,
                             price_per_kwh=price, session_fee=0.0, reliability=rel,
                             expected_wait_min=wait)
            for i, p in enumerate(positions_km)]


def test_charge_minutes_uses_curve_and_station_cap():
    fast = charge_minutes(MODEL3, 10.0, 60.0, station_kw=250.0)
    capped = charge_minutes(MODEL3, 10.0, 60.0, station_kw=50.0)
    assert fast < capped
    # 50 kW cap: 0.5*75 kWh / 50 kW = 45 min exactly (curve is above 50 in range)
    assert abs(capped - 45.0) < 1.0


def test_no_stop_needed_returns_empty_plan():
    r, w = long_flat(km=100.0)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=90.0))
    plan = optimize(res, r.s_m, cands(50.0), MODEL3, start_soc=90.0)
    assert plan is not None and plan.stops == ()


def test_single_stop_plan_respects_reserve_and_arrival():
    r, w = long_flat(km=400.0)                             # ~75+ kWh trip, needs a stop
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=90.0))
    plan = optimize(res, r.s_m, cands(180.0, 220.0), MODEL3, start_soc=90.0)
    assert plan is not None and len(plan.stops) >= 1
    stop = plan.stops[0]
    assert stop.arrival_soc >= 10.0 - 1e-6                 # UNWAIVABLE reserve
    assert plan.arrival_soc >= 15.0 - 1e-6
    assert stop.departure_soc <= 90.0
    assert plan.total_cost > 0 and plan.total_charge_min > 0


def test_infeasible_gap_returns_none():
    r, w = long_flat(km=400.0)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=90.0))
    # only charger at km 20; the remaining 380 km can't be bridged from 90%
    assert optimize(res, r.s_m, cands(20.0), MODEL3, start_soc=90.0) is None


def test_prefers_reliable_cheap_fast_station():
    r, w = long_flat(km=400.0)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=90.0))
    good = ChargerCandidate("good", 200_000.0, 250.0, 0.45, 0.0, 0.98, 0.0)
    bad = ChargerCandidate("bad", 201_000.0, 50.0, 0.79, 0.0, 0.60, 15.0)
    plan = optimize(res, r.s_m, [good, bad], MODEL3, start_soc=90.0)
    assert plan is not None
    assert plan.stops[0].station_id == "good"


def test_dp_matches_brute_force_on_small_instance():
    r, w = long_flat(km=300.0)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=70.0))
    cs = cands(120.0, 180.0, kw=150.0)
    plan = optimize(res, r.s_m, cs, MODEL3, start_soc=70.0)
    assert plan is not None
    # brute force: try every subset/level combo coarsely; DP must not be worse
    def total_cost(p):
        return p.total_charge_min + 3.0 * p.total_cost
    from itertools import product
    best = None
    for use0, use1 in product([False, True], repeat=2):
        # emulate by restricting candidates
        subset = [c for c, use in zip(cs, (use0, use1)) if use]
        alt = optimize(res, r.s_m, subset, MODEL3, start_soc=70.0)
        if alt is not None and (best is None or total_cost(alt) < total_cost(best)):
            best = alt
    assert best is not None
    assert total_cost(plan) <= total_cost(best) + 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/engine/test_charging.py -v`
Expected: FAIL — `ModuleNotFoundError: gradient_energy.charging`

- [ ] **Step 3: Implement**

`backend/gradient_energy/charging.py`:

```python
"""Charge-stop optimizer: DP over (candidate, arrival-SoC) states (EnergyEngine.md §6)."""
from __future__ import annotations

import numpy as np

from gradient_energy.types import (
    ChargerCandidate, ChargeStop, ChargingPlan, EnergyResult, VehicleSpec,
)

SOC_STEP = 5.0          # departure grid step (%)


def _curve_kw(vehicle: VehicleSpec, soc: float) -> float:
    pts = vehicle.charge_curve
    socs = [p[0] for p in pts]
    kws = [p[1] for p in pts]
    return float(np.interp(soc, socs, kws))


def charge_minutes(vehicle: VehicleSpec, from_soc: float, to_soc: float,
                   station_kw: float) -> float:
    if to_soc <= from_soc:
        return 0.0
    usable = vehicle.usable_kwh * vehicle.degradation_factor
    minutes = 0.0
    soc = from_soc
    while soc < to_soc - 1e-9:
        step = min(1.0, to_soc - soc)
        kw = min(_curve_kw(vehicle, soc + step / 2.0), station_kw)
        minutes += (step / 100.0 * usable) / kw * 60.0
        soc += step
    return minutes


def optimize(result: EnergyResult, route_s_m: np.ndarray,
             candidates: list[ChargerCandidate], vehicle: VehicleSpec, *,
             start_soc: float, reserve_soc: float = 10.0, min_arrival_soc: float = 15.0,
             max_charge_soc: float = 90.0, alpha_min: float = 1.0, beta_eur: float = 3.0,
             gamma_rel: float = 10.0) -> ChargingPlan | None:
    usable_wh = vehicle.usable_kwh * 1000.0 * vehicle.degradation_factor
    cum_wh = np.concatenate(([0.0], np.cumsum(result.e_wh[:-1])))

    def soc_drop_pct(from_m: float, to_m: float) -> float:
        e = float(np.interp(to_m, route_s_m, cum_wh) - np.interp(from_m, route_s_m, cum_wh))
        return e / usable_wh * 100.0

    end_m = float(route_s_m[-1])
    cands = sorted((c for c in candidates if 0.0 < c.position_m < end_m),
                   key=lambda c: c.position_m)

    # direct arrival without charging?
    direct = start_soc - soc_drop_pct(0.0, end_m)
    if direct >= min_arrival_soc and start_soc - max(
            soc_drop_pct(0.0, m) for m in [end_m]) >= reserve_soc:
        # also ensure the running minimum along the way stays above reserve
        soc_along = start_soc - (cum_wh / usable_wh * 100.0)
        if float(soc_along.min()) >= reserve_soc:
            return ChargingPlan(stops=(), arrival_soc=float(direct),
                                total_charge_min=0.0, total_cost=0.0)

    # DP nodes: index 0..len(cands)-1, arrival soc rounded to 1%
    INF = float("inf")
    # best[(i, soc_int)] = (cost, prev_key, departure_soc, stop_minutes, stop_cost)
    best: dict[tuple[int, int], tuple[float, tuple[int, int] | None, float, float, float]] = {}

    def reachable(from_m: float, soc: float, to_m: float) -> float | None:
        """Arrival SoC at to_m, or None if it dips below reserve on the way."""
        seg = (route_s_m >= from_m) & (route_s_m <= to_m)
        base = float(np.interp(from_m, route_s_m, cum_wh))
        along = soc - (cum_wh[seg] - base) / usable_wh * 100.0
        if along.size and float(along.min()) < reserve_soc:
            return None
        return soc - soc_drop_pct(from_m, to_m)

    for i, c in enumerate(cands):
        arr = reachable(0.0, start_soc, c.position_m)
        if arr is not None and arr >= reserve_soc:
            key = (i, int(round(arr)))
            if key not in best or best[key][0] > 0.0:
                best[key] = (0.0, None, arr, 0.0, 0.0)

    order = sorted(best.keys())
    queue = list(order)
    result_best: tuple[float, tuple[int, int]] | None = None

    def relax(key: tuple[int, int]) -> None:
        nonlocal result_best
        i, soc_int = key
        cost_here, _, arr_soc, _, _ = best[key]
        c = cands[i]
        dep_levels = np.arange(
            np.ceil(max(arr_soc, reserve_soc) / SOC_STEP) * SOC_STEP,
            max_charge_soc + 1e-9, SOC_STEP)
        for dep in dep_levels:
            if dep <= arr_soc + 1e-9:
                continue
            minutes = charge_minutes(vehicle, arr_soc, float(dep), c.power_kw)
            energy_kwh = (dep - arr_soc) / 100.0 * vehicle.usable_kwh * vehicle.degradation_factor
            eur = energy_kwh * c.price_per_kwh + c.session_fee
            step_cost = (alpha_min * (minutes + c.expected_wait_min)
                         + beta_eur * eur + gamma_rel * (1.0 / max(c.reliability, 0.05) - 1.0))
            total = cost_here + step_cost
            # to destination
            arr_end = reachable(c.position_m, float(dep), end_m)
            if arr_end is not None and arr_end >= min_arrival_soc:
                if result_best is None or total < result_best[0]:
                    stop_key = (i, soc_int)
                    best[(i, soc_int)] = (cost_here, best[key][1], arr_soc, 0.0, 0.0)
                    result_best = (total, stop_key)
                    _final_dep[stop_key] = (float(dep), minutes, eur, float(arr_end))
            # to next candidates
            for j in range(i + 1, len(cands)):
                arr_j = reachable(c.position_m, float(dep), cands[j].position_m)
                if arr_j is None or arr_j < reserve_soc:
                    continue
                nkey = (j, int(round(arr_j)))
                if nkey not in best or total < best[nkey][0]:
                    best[nkey] = (total, key, arr_j, minutes, eur)
                    _dep_of[nkey] = float(dep)
                    queue.append(nkey)

    _dep_of: dict[tuple[int, int], float] = {}
    _final_dep: dict[tuple[int, int], tuple[float, float, float, float]] = {}
    seen: set[tuple[int, int]] = set()
    while queue:
        key = queue.pop(0)
        if key in seen:
            continue
        seen.add(key)
        relax(key)

    if result_best is None:
        return None

    # reconstruct: walk back from the final stop
    _, last_key = result_best
    dep_soc, minutes, eur, arrival = _final_dep[last_key]
    stops: list[ChargeStop] = []
    key: tuple[int, int] | None = last_key
    stop_info = (dep_soc, minutes, eur)
    while key is not None:
        cost_here, prev, arr_soc, prev_minutes, prev_eur = best[key]
        i, _ = key
        c = cands[i]
        d, mins, cost = stop_info
        stops.append(ChargeStop(
            station_id=c.station_id, position_m=c.position_m,
            arrival_soc=float(arr_soc), departure_soc=float(d),
            duration_min=float(mins), cost=float(cost),
            expected_wait_min=c.expected_wait_min,
        ))
        if prev is not None:
            stop_info = (_dep_of[key], prev_minutes, prev_eur)
        key = prev
    stops.reverse()
    return ChargingPlan(
        stops=tuple(stops), arrival_soc=float(arrival),
        total_charge_min=float(sum(s.duration_min for s in stops)),
        total_cost=float(sum(s.cost for s in stops)),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/engine/test_charging.py -v`
Expected: 6 PASS. If the reconstruction bookkeeping proves fiddly, simplify the DP to
store full stop lists in states (candidate count ≤ 200 keeps memory trivial) — correctness
and the tests are the contract, not the reconstruction style.

- [ ] **Step 5: Lint, typecheck, commit**

```bash
cd backend && uv run ruff check . && uv run mypy gradient_energy
git add backend && git commit -m "feat(engine): DP charge-stop optimizer"
```

---

### Task 10: Twin — Kalman calibration + display smoother

**Files:**
- Create: `backend/gradient_energy/twin.py`
- Test: `backend/tests/engine/test_twin.py`

**Interfaces:**
- Consumes: nothing (self-contained state machines).
- Produces:
  - `KalmanCalibration(q: float = 1e-5, r_default: float = 0.02)` with `.update(observed_ratio: float, r: float | None = None) -> float` (filtered calibration factor, log-space 1-D Kalman) and `.factor` property (starts 1.0).
  - `DisplaySmoother(max_slew_pct_s: float = 0.5, consistency_s: int = 3)` with `.update(target: float, dt_s: float = 1.0) -> float` — shown value; movement starts only after `consistency_s` consecutive updates deviating in the same direction by > 0.05 %.

- [ ] **Step 1: Write the failing test**

`backend/tests/engine/test_twin.py`:

```python
import numpy as np

from gradient_energy.twin import DisplaySmoother, KalmanCalibration


def test_kalman_converges_to_true_ratio():
    rng = np.random.default_rng(7)
    k = KalmanCalibration()
    for _ in range(300):
        k.update(1.12 * float(np.exp(rng.normal(0.0, 0.05))))
    assert abs(k.factor - 1.12) < 0.02


def test_kalman_single_outlier_barely_moves_estimate():
    k = KalmanCalibration()
    for _ in range(50):
        k.update(1.0)
    before = k.factor
    k.update(3.0)                                          # GPS glitch
    assert abs(k.factor - before) < 0.02


def test_kalman_noisier_measurement_trusted_less():
    k1, k2 = KalmanCalibration(), KalmanCalibration()
    k1.update(1.2, r=0.001)
    k2.update(1.2, r=0.5)
    assert abs(k1.factor - 1.2) < abs(k2.factor - 1.2)


def test_smoother_slew_limit_UNWAIVABLE():
    s = DisplaySmoother()
    s.update(50.0)                                         # initialize
    values = [s.update(40.0) for _ in range(30)]           # want a 10% drop
    diffs = np.abs(np.diff(np.array([50.0] + values)))
    assert float(diffs.max()) <= 0.5 + 1e-9                # <= 0.5 %/s always


def test_smoother_needs_3s_consistency_before_moving():
    s = DisplaySmoother()
    s.update(50.0)
    assert s.update(45.0) == 50.0                          # 1st deviating sample
    assert s.update(45.0) == 50.0                          # 2nd
    assert s.update(45.0) < 50.0                           # 3rd -> starts moving


def test_smoother_ignores_transient_blips():
    s = DisplaySmoother()
    s.update(50.0)
    s.update(45.0)
    s.update(45.0)
    assert s.update(50.0) == 50.0                          # blip resets consistency
    assert s.update(45.0) == 50.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/engine/test_twin.py -v`
Expected: FAIL — `ModuleNotFoundError: gradient_energy.twin`

- [ ] **Step 3: Implement**

`backend/gradient_energy/twin.py`:

```python
"""Digital-twin correction: Kalman-filtered calibration + display smoothing contract.

The smoothing contract (<= 0.5 %/s, 3 s consistency) is a product guarantee
(EnergyEngine.md §4); its tests are unwaivable.
"""
from __future__ import annotations

import math


class KalmanCalibration:
    """1-D Kalman filter on log(calibration factor)."""

    def __init__(self, q: float = 1e-5, r_default: float = 0.02) -> None:
        self._x = 0.0            # log-space state
        self._p = 0.01
        self._q = q
        self._r_default = r_default

    @property
    def factor(self) -> float:
        return math.exp(self._x)

    def update(self, observed_ratio: float, r: float | None = None) -> float:
        z = math.log(max(observed_ratio, 1e-6))
        r_eff = self._r_default if r is None else r
        self._p += self._q
        k = self._p / (self._p + r_eff)
        self._x += k * (z - self._x)
        self._p *= 1.0 - k
        return self.factor


class DisplaySmoother:
    """Slew-limited display value with a consistency gate against transients."""

    DEADBAND = 0.05

    def __init__(self, max_slew_pct_s: float = 0.5, consistency_s: int = 3) -> None:
        self._max_slew = max_slew_pct_s
        self._need = consistency_s
        self._shown: float | None = None
        self._streak = 0
        self._streak_sign = 0

    def update(self, target: float, dt_s: float = 1.0) -> float:
        if self._shown is None:
            self._shown = target
            return target
        delta = target - self._shown
        sign = 1 if delta > self.DEADBAND else (-1 if delta < -self.DEADBAND else 0)
        if sign == 0 or sign != self._streak_sign:
            self._streak = 1 if sign != 0 else 0
            self._streak_sign = sign
            return self._shown
        self._streak += 1
        if self._streak < self._need:
            return self._shown
        step = min(abs(delta), self._max_slew * dt_s)
        self._shown += math.copysign(step, delta)
        return self._shown
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/engine/test_twin.py -v`
Expected: 6 PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
cd backend && uv run ruff check . && uv run mypy gradient_energy
git add backend && git commit -m "feat(engine): twin Kalman calibration and display smoother"
```

---

### Task 11: Property tests, analytic fixtures, perf budget, golden harness

**Files:**
- Create: `backend/tests/engine/test_properties.py`
- Create: `backend/tests/engine/test_analytic.py`
- Create: `backend/tests/engine/test_golden.py`
- Create: `backend/tests/testdata/golden_trips/synthetic_flat_100km.json`
- Create: `backend/tests/testdata/golden_trips/synthetic_alpine_60km.json`
- Modify: `backend/gradient_energy/__init__.py` (export `integrate`, `predict`, `build_timeline`, `efficiency_band`, `optimize`, smoothing/twin classes)

**Interfaces:**
- Consumes: everything.
- Produces: the release-gate suite (Testing.md §1). Golden JSON schema:
  `{"name", "real": bool, "vehicle": {VehicleSpec fields}, "context": {TripContext fields}, "route": {"s_m": [...], "elevation_m": [...], "grade": [...], "curvature_1pm": [...], "heading_deg": [...], "speed_limit_mps": [...], "expected_speed_mps": [...]}, "weather_uniform": {...}, "observed": {"arrival_soc": float}}`. MAE gate (≤3 %) applies only to files with `"real": true`; synthetic files verify harness plumbing (tolerance 0.5 % against engine output recorded at creation).

- [ ] **Step 1: Write property tests**

`backend/tests/engine/test_properties.py`:

```python
import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from gradient_energy.model import integrate
from gradient_energy.types import TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route, hill_route


@settings(max_examples=50, deadline=None)
@given(grade=st.floats(0.01, 0.12), speed=st.floats(10.0, 33.0))
def test_round_trip_never_gains_energy(grade: float, speed: float) -> None:
    r = hill_route(n=400, grade=grade, speed_mps=speed)
    w = WeatherSamples.uniform(400)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    assert res.soc_pct[-1] <= res.soc_pct[0] + 1e-9


@settings(max_examples=50, deadline=None)
@given(extra_kg=st.floats(0.0, 500.0))
def test_more_mass_never_cheaper_uphill(extra_kg: float) -> None:
    r = hill_route(n=200, grade=0.06)
    r2 = hill_route(n=200, grade=0.06)
    w = WeatherSamples.uniform(200)
    light = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    heavy = integrate(r2, w, MODEL3, TripContext(start_soc_pct=80.0, cargo_kg=extra_kg))
    assert heavy.energy_used_kwh >= light.energy_used_kwh - 1e-9


@settings(max_examples=30, deadline=None)
@given(wind=st.floats(0.0, 15.0))
def test_headwind_never_cheaper(wind: float) -> None:
    r = flat_route(n=200)
    calm = WeatherSamples.uniform(200)
    windy = WeatherSamples.uniform(200, wind_speed_mps=wind, wind_dir_deg=0.0)
    a = integrate(r, calm, MODEL3, TripContext(start_soc_pct=80.0))
    b = integrate(r, windy, MODEL3, TripContext(start_soc_pct=80.0))
    assert b.energy_used_kwh >= a.energy_used_kwh - 1e-9


def test_sample_spacing_invariance():
    fine = hill_route(n=1600, spacing_m=12.5)
    coarse = hill_route(n=400, spacing_m=50.0)
    w_f = WeatherSamples.uniform(1600)
    w_c = WeatherSamples.uniform(400)
    ctx = TripContext(start_soc_pct=80.0)
    a = integrate(fine, w_f, MODEL3, ctx)
    b = integrate(coarse, w_c, MODEL3, ctx)
    assert abs(a.soc_pct[-1] - b.soc_pct[-1]) < 0.3        # % SoC


@settings(max_examples=30, deadline=None)
@given(soc=st.floats(2.0, 99.0), grade=st.floats(-0.12, 0.12))
def test_soc_always_finite_in_bounds(soc: float, grade: float) -> None:
    r = hill_route(n=200, grade=abs(grade))
    w = WeatherSamples.uniform(200, temp_c=-15.0)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=soc))
    assert np.all(np.isfinite(res.soc_pct))
    assert np.all((res.soc_pct >= 0.0) & (res.soc_pct <= 100.0))
```

- [ ] **Step 2: Write analytic + perf tests**

`backend/tests/engine/test_analytic.py`:

```python
import time

import numpy as np

from gradient_energy.model import integrate
from gradient_energy.prediction import predict
from gradient_energy.timeline import build_timeline
from gradient_energy.types import TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route, hill_route


def test_energy_totals_equal_sum_of_segments():
    r = hill_route(n=800)
    w = WeatherSamples.uniform(800)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=80.0))
    assert abs((res.energy_used_kwh - res.energy_regen_kwh) * 1000.0
               - float(res.e_wh.sum())) < 1e-6


def test_regen_bounded_by_potential_energy():
    r = hill_route(n=800, grade=0.05)
    w = WeatherSamples.uniform(800)
    res = integrate(r, w, MODEL3, TripContext(start_soc_pct=60.0))
    drop_m = 0.05 * 10_000.0                               # descent half: 500 m drop
    ep_kwh = (1850.0 + 75.0) * 9.80665 * drop_m / 3.6e6
    assert res.energy_regen_kwh <= ep_kwh


def test_perf_budget_10k_samples():
    n = 10_000
    r = hill_route(n=n)
    w = WeatherSamples.uniform(n)
    ctx = TripContext(start_soc_pct=80.0)
    t0 = time.perf_counter()
    res = integrate(r, w, MODEL3, ctx)
    predict(r, w, MODEL3, ctx)
    build_timeline(res, r, w, MODEL3, ctx)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.2                                   # 50 ms budget x4 CI margin
```

- [ ] **Step 3: Write golden harness + seed files**

`backend/tests/engine/test_golden.py`:

```python
import json
from pathlib import Path

import numpy as np
import pytest

from gradient_energy.prediction import predict
from gradient_energy.types import RouteSamples, TripContext, VehicleSpec, WeatherSamples

GOLDEN_DIR = Path(__file__).parent.parent / "testdata" / "golden_trips"
REAL_MAE_LIMIT = 3.0
SYNTHETIC_TOLERANCE = 0.5


def load(path: Path):
    d = json.loads(path.read_text())
    vehicle = VehicleSpec(**{**d["vehicle"],
                             "charge_curve": tuple(map(tuple, d["vehicle"]["charge_curve"]))})
    ctx = TripContext(**d["context"])
    route = RouteSamples(**{k: np.asarray(v, dtype=np.float64)
                            for k, v in d["route"].items()})
    weather = WeatherSamples.uniform(n=route.n, **d["weather_uniform"])
    return d, vehicle, ctx, route, weather


@pytest.mark.parametrize("path", sorted(GOLDEN_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_golden_trip(path: Path):
    d, vehicle, ctx, route, weather = load(path)
    p = predict(route, weather, vehicle, ctx)
    err = abs(p.arrival_soc - d["observed"]["arrival_soc"])
    limit = REAL_MAE_LIMIT if d.get("real") else SYNTHETIC_TOLERANCE
    assert err <= limit, f"{path.stem}: arrival SoC error {err:.2f}% > {limit}%"
```

Seed files: generate with a one-off script, run it, then delete the script (the JSON is the
artifact). Create `backend/scripts/make_synthetic_goldens.py`:

```python
"""One-off: seed synthetic golden trips from the engine itself (harness plumbing check).
Real logged trips replace/augment these at Alpha (Roadmap M2)."""
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from gradient_energy.prediction import predict
from gradient_energy.types import RouteSamples, TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, flat_route, hill_route

OUT = Path("tests/testdata/golden_trips")
OUT.mkdir(parents=True, exist_ok=True)

for name, route, weather_kw, ctx in [
    ("synthetic_flat_100km", flat_route(n=2000, spacing_m=50.0, speed_mps=30.55),
     {"temp_c": 15.0}, TripContext(start_soc_pct=90.0)),
    ("synthetic_alpine_60km", hill_route(n=1200, spacing_m=50.0, grade=0.07,
                                         speed_mps=18.0),
     {"temp_c": 5.0, "wind_speed_mps": 4.0}, TripContext(start_soc_pct=75.0,
                                                          hvac_mode="heat")),
]:
    weather = WeatherSamples.uniform(n=route.n, **weather_kw)
    p = predict(route, weather, MODEL3, ctx)
    doc = {
        "name": name, "real": False,
        "vehicle": {**asdict(MODEL3), "charge_curve": [list(x) for x in MODEL3.charge_curve]},
        "context": asdict(ctx),
        "route": {k: np.asarray(getattr(route, k)).tolist() for k in
                  ("s_m", "elevation_m", "grade", "curvature_1pm", "heading_deg",
                   "speed_limit_mps", "expected_speed_mps")},
        "weather_uniform": weather_kw,
        "observed": {"arrival_soc": round(p.arrival_soc, 3)},
    }
    (OUT / f"{name}.json").write_text(json.dumps(doc))
    print(name, "->", p.arrival_soc)
```

Run: `cd backend && uv run python scripts/make_synthetic_goldens.py` then
`rm scripts/make_synthetic_goldens.py` (or keep under `scripts/` — keep it; regenerating
goldens after intentional engine changes is a legitimate workflow. Keep the script.)

- [ ] **Step 4: Update public API**

`backend/gradient_energy/__init__.py`:

```python
from gradient_energy.charging import charge_minutes, optimize  # noqa: F401
from gradient_energy.model import integrate  # noqa: F401
from gradient_energy.prediction import predict  # noqa: F401
from gradient_energy.profile import compute_grade, next_summit_distance, smooth_elevation  # noqa: F401
from gradient_energy.speed import WeatherPoint, efficiency_band  # noqa: F401
from gradient_energy.timeline import build_timeline, classify_samples  # noqa: F401
from gradient_energy.twin import DisplaySmoother, KalmanCalibration  # noqa: F401
from gradient_energy.types import (  # noqa: F401
    ENGINE_VERSION, Chapter, ChargeStop, ChargerCandidate, ChargingPlan,
    DriverProfile, EnergyResult, Prediction, RouteSamples, SpeedBand,
    TripContext, VehicleSpec, WeatherSamples,
)
```

- [ ] **Step 5: Run the full suite, lint, typecheck**

Run: `cd backend && uv run pytest -q && uv run ruff check . && uv run mypy gradient_energy`
Expected: all tests pass (≈55), no lint/type errors.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "test(engine): property suite, analytic fixtures, perf budget, golden harness"
```

---

## Self-Review Notes (completed during writing)

- **Spec coverage:** EnergyEngine.md §1 inputs → Task 1; §2 physics → Tasks 3–5; §3
  prediction/confidence → Task 6; §4 twin/smoothing → Task 10; §5 speed band → Task 8;
  §6 charging → Task 9; §7 timeline → Task 7; §9 validation → Task 11 (+ per-task tests).
  §8 eco coach and §10 ML path are backend-module concerns (sub-project 2+), intentionally
  out of scope here. Elevation smoothing (Architecture.md §3 step 4) → Task 2.
- **Deferred to sub-project 2 (recorded):** per-speed/load η maps (flat 0.90 default is in
  the spec), surface-type factor `f_surface` (fixed 1.0 until road-surface data exists) —
  both noted in code comments and the debt register when backend work starts.
- **Type consistency check:** `RouteSamples` field names, `EnergyResult` fields, and
  `ChargerCandidate/ChargeStop/ChargingPlan` verified identical across Tasks 1, 5, 7, 9, 11.
- **Placeholder scan:** clean — every step has runnable code or an exact command.
