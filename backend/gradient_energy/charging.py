"""Charge-stop optimizer: DP over (candidate, arrival-SoC) states (EnergyEngine.md §6).

The DP is a DAG relaxation: candidates are sorted by position and edges only ever go
forward (start -> candidate, candidate_i -> candidate_j>i, candidate -> destination).
Each reachable (candidate, arrival-SoC%) state stores the cheapest cumulative cost *and*
the full list of stops that produced it. Storing whole partial plans (candidate count is
tiny, <= a few hundred) sidesteps parent-pointer reconstruction entirely; the brief
explicitly permits this simplification since correctness and the tests are the contract.
"""
from __future__ import annotations

import numpy as np

from gradient_energy.types import (
    ChargerCandidate,
    ChargeStop,
    ChargingPlan,
    EnergyResult,
    VehicleSpec,
)

SOC_STEP = 5.0          # departure grid step (%)


def _curve_kw(vehicle: VehicleSpec, soc: float) -> float:
    """Charge power (kW) the vehicle accepts at a given SoC, linearly interpolated."""
    socs = [p[0] for p in vehicle.charge_curve]
    kws = [p[1] for p in vehicle.charge_curve]
    return float(np.interp(soc, socs, kws))


def charge_minutes(vehicle: VehicleSpec, from_soc: float, to_soc: float,
                   station_kw: float) -> float:
    """Minutes to charge from `from_soc` to `to_soc`, integrating 1 % SoC steps.

    Per step the accepted power is min(curve(soc), station_kw); time for the step is
    (energy for 1 % of usable capacity) / power.
    """
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
    """Least-cost charge plan, an empty-stops plan if none is needed, or None if infeasible.

    Cost of a stop = alpha*(charge_min + wait) + beta*cost_eur + gamma*(1/reliability - 1).
    SoC is never allowed to dip below `reserve_soc` anywhere along the route; final arrival
    must be >= `min_arrival_soc`.
    """
    usable_wh = vehicle.usable_kwh * 1000.0 * vehicle.degradation_factor
    # cum_wh[i] = battery energy (Wh) consumed from the start up to route sample i.
    cum_wh = np.concatenate(([0.0], np.cumsum(result.e_wh[:-1])))
    end_m = float(route_s_m[-1])

    def soc_drop_pct(from_m: float, to_m: float) -> float:
        e = float(np.interp(to_m, route_s_m, cum_wh) - np.interp(from_m, route_s_m, cum_wh))
        return e / usable_wh * 100.0

    def reachable(from_m: float, soc: float, to_m: float) -> float | None:
        """Arrival SoC at `to_m`, or None if SoC dips below reserve anywhere en route."""
        mask = (route_s_m >= from_m) & (route_s_m <= to_m)
        base = float(np.interp(from_m, route_s_m, cum_wh))
        if np.any(mask):
            along = soc - (cum_wh[mask] - base) / usable_wh * 100.0
            if float(along.min()) < reserve_soc:
                return None
        arr = soc - soc_drop_pct(from_m, to_m)
        if arr < reserve_soc:
            return None
        return arr

    # --- Direct arrival with no charging (optimal when feasible: cost 0) ---------------
    direct = reachable(0.0, start_soc, end_m)
    if direct is not None and direct >= min_arrival_soc:
        return ChargingPlan(stops=(), arrival_soc=float(direct),
                            total_charge_min=0.0, total_cost=0.0)

    # Candidates strictly along the route, ordered by position.
    cands = sorted((c for c in candidates if 0.0 < c.position_m < end_m),
                   key=lambda c: c.position_m)

    # DP state: (candidate index, arrival SoC rounded to 1%) -> (cost, stops, arrival).
    State = tuple[float, tuple[ChargeStop, ...], float]
    best: dict[tuple[int, int], State] = {}

    def offer(key: tuple[int, int], cand: State) -> None:
        cur = best.get(key)
        if cur is None or cand[0] < cur[0]:
            best[key] = cand

    # Seed: reach each candidate directly from the start.
    for i, c in enumerate(cands):
        arr = reachable(0.0, start_soc, c.position_m)
        if arr is not None:
            offer((i, int(round(arr))), (0.0, (), arr))

    final: State | None = None

    def consider_final(cost: float, stops: tuple[ChargeStop, ...], arrival: float) -> None:
        nonlocal final
        if arrival >= min_arrival_soc and (final is None or cost < final[0]):
            final = (cost, stops, arrival)

    # Relax states in candidate order (edges only go to strictly later candidates, so all
    # predecessors of index i are finalized by the time we process index i).
    for i in range(len(cands)):
        c = cands[i]
        for (si, _), (cost_here, stops_here, arr_soc) in list(best.items()):
            if si != i:
                continue
            start_lvl = np.ceil(max(arr_soc, reserve_soc) / SOC_STEP) * SOC_STEP
            for dep in np.arange(start_lvl, max_charge_soc + 1e-9, SOC_STEP):
                dep = float(dep)
                if dep <= arr_soc + 1e-9:
                    continue
                minutes = charge_minutes(vehicle, arr_soc, dep, c.power_kw)
                energy_kwh = (dep - arr_soc) / 100.0 * vehicle.usable_kwh * vehicle.degradation_factor
                eur = energy_kwh * c.price_per_kwh + c.session_fee
                step_cost = (alpha_min * (minutes + c.expected_wait_min)
                             + beta_eur * eur
                             + gamma_rel * (1.0 / max(c.reliability, 1e-3) - 1.0))
                total = cost_here + step_cost
                stop = ChargeStop(
                    station_id=c.station_id, position_m=c.position_m,
                    arrival_soc=float(arr_soc), departure_soc=dep,
                    duration_min=float(minutes), cost=float(eur),
                    expected_wait_min=c.expected_wait_min,
                )
                new_stops = (*stops_here, stop)

                arr_end = reachable(c.position_m, dep, end_m)
                if arr_end is not None:
                    consider_final(total, new_stops, arr_end)

                for j in range(i + 1, len(cands)):
                    arr_j = reachable(c.position_m, dep, cands[j].position_m)
                    if arr_j is not None:
                        offer((j, int(round(arr_j))), (total, new_stops, arr_j))

    if final is None:
        return None
    cost, stops, arrival = final
    return ChargingPlan(
        stops=stops, arrival_soc=float(arrival),
        total_charge_min=float(sum(s.duration_min for s in stops)),
        total_cost=float(sum(s.cost for s in stops)),
    )
