# Technical debt register

Per Roadmap.md §5: every conscious shortcut logged here with owner + sunset milestone.
Debt items block the milestone after their sunset.

## gradient_energy backend package

1. **`charging.optimize()` still scales ~1.5x per +4 candidates; `reachable()` is the
   residual hot spot.**
   During the final whole-branch review of the gradient_energy engine plan, a perf
   finding against `optimize()` was fixed (charge-curve interpolation was vectorized,
   ~1.4x measured speedup on a 25-candidate/600km case), but the fix's own re-review
   found the root cause was misdiagnosed: the real hot spot is `charging.py`'s
   `reachable()`, which rebuilds a boolean mask over the full route sample array on
   every DP edge (57k calls, ~1s of ~1.2s total at 25 candidates on a 12,001-sample
   route). No consumer exists yet (`app.*` isn't built), so nothing is blocked today.
   Owner: engine. Sunset: before any charging UI ships with route lengths or candidate
   counts materially larger than the current test fixtures (600km / 25 stations).

2. **`test_optimize_perf_budget_many_candidates`'s 2.0s budget has thin headroom.**
   Measured ~0.82s on the dev machine — only ~2.4x margin, versus the package's other
   perf test which targets a 4x CI margin. Risk of flaking on a slower CI runner.
   Owner: engine. Sunset: fix if/when it flakes in CI, or preemptively before CI is
   set up for this package.
