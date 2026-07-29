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
