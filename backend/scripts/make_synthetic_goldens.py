"""One-off: seed synthetic golden trips from the engine itself (harness plumbing check).
Real logged trips replace/augment these at Alpha (Roadmap M2)."""
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from gradient_energy.prediction import predict
from gradient_energy.types import TripContext, WeatherSamples
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
