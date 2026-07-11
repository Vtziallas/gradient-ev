# Gradient — Physics Energy Engine

The engine is a **pure Python package** (`gradient_energy`) with zero I/O: inputs are arrays
+ typed configs, outputs are arrays + typed results. NumPy-vectorized. This is the product's
core IP and the most heavily tested code in the system.

## 1. Inputs

```
RouteSamples        s[i] distance (m), h[i] elevation (m), grade[i], curvature[i],
                    speed_limit[i], expected_speed[i] (traffic-adjusted)
VehicleSpec         mass_kg, cd, frontal_area_m2, c_rr_base, usable_kwh, max_regen_kw,
                    max_dc_kw, charge_curve (SoC→kW), drivetrain_eff, regen_eff,
                    aux_base_w, battery_chemistry, degradation_factor
TripContext         passengers, cargo_kg, hvac_mode(heat/cool/off), cabin_target_c,
                    tire_pressure_factor, start_soc
WeatherPerSample    temp_c, wind_speed, wind_dir, rain_mm_h, snow, humidity, pressure_hpa
DriverProfile       calibration_factor (default 1.0), accel_aggressiveness
```

## 2. Physics model (per 25–50 m sample)

Effective mass: `m = mass_kg + 75·passengers + cargo_kg`, rotational inertia
`m_eff = 1.05·m` for the acceleration term.

Air density from ideal gas with humidity correction:
`ρ = (p_d/(R_d·T)) + (p_v/(R_v·T))`  (p from weather, T in K).

Wind: project wind vector on segment heading → `v_air = v + v_headwind`.

Forces (θ = atan(grade)):

```
F_roll  = c_rr · m · g · cos θ        c_rr = c_rr_base · f_surface · f_rain · f_temp / tire_pressure_factor
F_aero  = ½ · ρ · cd · A · v_air²     (sign of v_air preserved for tailwind)
F_grade = m · g · sin θ
F_accel = m_eff · a                    a from expected_speed profile between samples
F_total = F_roll + F_aero + F_grade + F_accel
```

Wheel power `P_wheel = F_total · v`. Battery power:

```
if P_wheel ≥ 0:  P_batt = P_wheel / η_drive(v, P_wheel) + P_aux
else:            P_batt = max(P_wheel, -P_regen_max(soc, temp)) · η_regen + P_aux
```

- `η_drive`: 2-D efficiency map (speed × load), default 0.90 flat map when the model lacks
  data; per-model maps improve over time.
- `P_regen_max`: derated linearly above 90% SoC (→0 at 100%) and below 5 °C battery temp
  (cold battery ≈ 40% regen); friction brakes absorb the remainder (energy lost).
- `P_aux = aux_base_w + P_hvac(temp_c, cabin_target, mode) + 250 W electronics`.
  HVAC model: heat pump COP curve vs ΔT for heating (resistive fallback for pre-heat-pump
  models), compressor curve for cooling; rain adds defogger load.

Segment energy `E_i = P_batt · Δt_i`, `Δt_i = Δs_i / v_i`. Battery state integrates
`soc[i+1] = soc[i] − E_i / (usable_kwh · degradation_factor · η_batt(temp))` with
`η_batt` cold-battery internal-resistance penalty (≤ 8% below −5 °C).

Everything above is vectorized: one pass over the arrays, <50 ms for 10k samples.

## 3. Battery prediction & confidence

- **Point prediction:** the integration above → arrival SoC, per-sample SoC curve,
  energy gained (regen) and lost totals, remaining range (greedy extension along a flat
  virtual road at current efficiency).
- **Best/worst case + confidence:** analytic sensitivity, not Monte Carlo, for MVP speed:
  recompute with a pessimistic tuple (wind +1σ, temp −1σ, mass +100 kg, calibration ×1.08)
  and optimistic tuple. Confidence score = f(vehicle-model data quality, weather forecast
  age, route length, |calibration_factor−1| history variance), mapped to 0–100.
- **Headline rule (safety):** if worst-case arrival < 15%, UI leads with worst case.

## 4. Live correction (digital twin, every 1 s)

1. Map-match GPS → route position `s`.
2. Observed energy rate vs predicted rate over trailing 60 s window →
   error ratio `r_obs`.
3. **Filter:** 1-D Kalman on log(calibration factor): process noise small, measurement noise
   scaled by GPS/speed variance. No raw jumps.
4. Re-scale remaining route prediction by filtered factor; **display smoothing contract:**
   shown arrival SoC slews ≤ 0.5 %/s and only after 3 consecutive seconds of consistent
   drift (prevents tunnel/GPS glitches from moving the number).
5. Persisted at trip end → updates `DriverProfile.calibration_factor` (Bayesian shrinkage
   toward 1.0, per vehicle).

## 5. Safe efficiency speed band (Smart Speed Bubble)

For the current/upcoming segment, minimize energy per distance over speed:

`e(v) = F_total(v)/η + P_aux/v` (aux amortizes over distance — crawling wastes HVAC energy;
this creates the classic U-curve).

Constraints (hard): `v ≤ speed_limit`, `v ≥ max(0.85·traffic_flow, v_min_road)`,
lateral accel `v²·κ ≤ 2.5 m/s²` (curvature), weather caps (rain −10%, snow −30%).
Band = `{v : e(v) ≤ 1.02 · e(v*)}` intersected with constraints, rounded to whole km/h,
e.g. **72–79 km/h**. Every recommendation ships a `reasons[]` list (grade, headwind,
curve, traffic) for the "why" popover. Never displayed above the legal limit — enforced in
the engine, not the UI.

## 6. Charging optimizer

Model as shortest-path/DP over charger graph along the corridor:

- Candidate set: DC chargers within 3 km of route, filtered by connector, min power,
  reliability score ≥ threshold.
- State: (charger, arrival SoC discretized 1%). Edge cost =
  `α·(drive_time + charge_time + expected_wait) + β·cost_eur + γ·(1/reliability)`.
- Charge time from the model's **charge curve** (SoC→kW), charging only to the SoC needed
  to reach the next stop + reserve (fast-charging sweet spot 10–60%), unless stop-count
  minimization preferred by user.
- Hard constraints: SoC never below user reserve (default 10%), arrival SoC ≥ target.
- Output per stop: arrival/departure SoC, duration, cost, expected wait (occupancy history
  by hour-of-week), reliability, alternatives (next-best 2), amenities (OSM POIs within
  400 m: food, coffee, restrooms, shopping).
- DP over ≤ 200 candidates × 100 SoC states solves in <100 ms.

## 7. Energy Timeline generation

Collapse samples into human-scale **chapters**: contiguous runs of the same energy class
(regen/efficient/medium/heavy/charge), min chapter length 500 m, merging flicker. Each
chapter: Δbattery %, distance, dominant cause (grade/wind/speed/HVAC — largest force term),
icon, and for climbs: distance-to-summit. This list *is* the Energy Timeline UI and the
voice narration source.

## 8. Eco coach (post-trip)

Compare recorded telemetry vs the engine's "ideal driver" re-simulation of the same trip
(same route/weather, optimal speed band, smooth accel profile):

- Wasted regen: braking events where friction share > 0 → "you could have regenerated
  2.8 kWh".
- Acceleration aggressiveness: histogram of |a| vs reference; flag events > 2.5 m/s².
- Optimal climb speed hindsight per climb chapter.
- Efficiency score 0–100 = weighted (energy vs ideal 50%, regen capture 25%, smoothness
  15%, speed-band adherence 10%).
- Battery-health tips: rule pack (avoid 100% daily charge, cold fast-charge warnings…).

## 9. Validation (gate for every release)

- **Golden trips:** curated dataset of real logged trips (public OBD datasets + team cars +
  beta users), per vehicle model. CI asserts arrival-SoC MAE ≤ 3% and per-10km segment MAE
  ≤ 1.5%.
- **Property tests:** energy conservation (uphill+downhill round trip loses ≥ 0), regen
  never exceeds potential energy, monotonicity (more mass ⇒ more energy uphill).
- **Cross-check:** total = Σ segment energies = integral check within float tolerance.
- Physics constants and vehicle specs are versioned (`engine_version`, `catalog_version`)
  and stamped on every prediction row for later ML training and regression triage.

## 10. ML evolution path (post-Beta, unchanged interfaces)

1. Per-user calibration factor (already live, §4).
2. Per-model residual GBT correcting `P_batt` from telemetry features — applied as a bounded
   multiplier (0.85–1.15) so physics remains the backbone.
3. HVAC + charge-curve refinement from observed sessions.
4. Only then: learned traffic-speed and wait-time models.
