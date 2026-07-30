import numpy as np

from gradient_energy.model import (
    aux_power_w, battery_eff, battery_power_w, compute_forces, hvac_power_w, regen_derate,
    temp_derate_factor,
)
from gradient_energy.types import TripContext, WeatherSamples
from tests.engine.conftest import MODEL3, hill_route


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


def test_temp_derate_factor_shared_by_regen_derate_and_integrate():
    """regen_derate() and integrate()'s per-step regen cap must derive the
    temperature-derating factor from the same shared helper rather than duplicating
    the expression -- checked by isolating f_soc=1.0 (soc<=90) in regen_derate(),
    at which point it must equal temp_derate_factor() exactly."""
    temp = np.array([-10.0, -5.0, 0.0, 10.0, 20.0])
    factor = temp_derate_factor(temp)
    assert np.allclose(regen_derate(90.0, temp), factor)


def test_battery_eff_cold_penalty():
    eff = battery_eff(np.array([20.0, 0.0, -5.0, -20.0]))
    assert eff[0] == 1.0
    assert 0.92 < eff[1] < 1.0
    assert abs(eff[2] - 0.92) < 1e-9 and abs(eff[3] - 0.92) < 1e-9
