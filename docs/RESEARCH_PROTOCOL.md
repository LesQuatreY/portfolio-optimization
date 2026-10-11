# Research protocol: controlling model-selection overfitting

The walk-forward makes each fitted portfolio out of sample with respect to its own weights. It does
**not** protect against the researcher choosing, among many configurations, the one whose 2013-2019
result looks best. That selection is itself a fit to the validation years.

## Decisions that currently select among alternatives

| Decision | Current state | How it was made | Overfitting exposure |
|---|---|---|---|
| Eligible universe (7 assets) | Apple, Nasdaq 100, MSCI World, S&P 500, Dow Jones, Gold, Coca-Cola | Researcher choice, partly with hindsight (Apple, Nasdaq) | High: hindsight selection bias, not removable by any protocol |
| Leverage | Nasdaq 100 x2 | Researcher choice | Medium |
| Investor caps | Gold <= 10%, Apple <= 40% | Investor-declared preferences, formally confirmed in phase 3 after the phase 1-2 validation results had been viewed | Treated as policy, not tuned; their 2013-2019 evaluation is not independent of those earlier looks |
| Estimators | Ledoit-Wolf covariance, sample mean | Fixed before the 2013-2019 protocol existed; Bayes-Stein was compared once on data now locked | Medium |
| Financial assumptions | historical EUR risk-free and USD financing rates, 0.4% spread, index holding costs, 10 bp costs | Set in phase 3 from data quality and instrument facts (docs/DATA_AUDIT.md), never from results | Low |
| Risk profiles | 15/20/30/40/50% estimated-volatility ceilings | Fixed before validation | Low (a fixed menu, all reported) |
| Rebalancing / costs / lag | annual, 10 bp, 1 session | Fixed a priori on economic grounds before measuring | Low |
| Universe variants | 4, listed in research.yaml | Listed before their results | Low to medium (4 looks) |
| Rolling vs expanding | rolling primary, expanding as a check | Fixed a priori | Low |

None of these is chosen automatically by the code, and there is no "best portfolio" output.

## Decision taxonomy

| Kind | Where it lives | Registry category | Rule |
|---|---|---|---|
| Investor-defined constraints | `constraints` in research.yaml (+ `provenance`, mandatory) | new configuration; `decision_log` shows the change | legitimate at any time; never tuned on results; the validation of a changed preference is not a fresh test |
| Financial modelling assumptions | `rates`, `holding_costs`, `leverage_costs`, costs | correction (when a fix) | justified by instrument facts, never by performance |
| Fixed baseline methods | `walk_forward`, `estimation`, `risk_profiles` | baseline | changed only through a recorded correction or a pre-registered test |
| Pre-registered hypotheses | registry call with `hypothesis` | pre-registered | written before the run; all outcomes kept |
| Exploratory experiments | registry call | exploratory | cannot justify a selection without a fresh test |
| Methodological bug fixes | code + registry rerun | correction | applied whatever the effect on results |
| Final model selection | registry call with the criterion as `hypothesis` | selection | criterion declared before looking; no automatic winner in the code |

## Rules

1. **Corrections versus elective changes.** A change motivated by a demonstrable error (timing,
   accounting, inconsistent assumptions, data defects) is a correction: it is applied regardless of
   its effect on results, and the rerun "supersedes" the earlier registry entry. Anything else
   (assets, objective, estimator, constraint, leverage, profile, window, costs) is elective.
2. **Pre-register elective changes.** Before running, write the candidate set and the hypothesis in
   the registry call (`category="pre-registered"`, `hypothesis=...`) or in this file. Report every
   candidate, including those that disappoint.
3. **Decide the selection criterion before looking.** The investor inspects a menu of risk levels
   rather than one winner. When an allocation must be retained, the recommended framework is, in
   order: (a) investable under the investor's constraints; (b) maximum drawdown compatible with the
   investor's reference (about -50%) in the in-sample implemented backtest and in the walk-forward,
   remembering that neither bounds the future; (c) among those, CAGR relative to the constrained equal
   weight, required to hold in the leave-one-year-out table and under the expanding-window check;
   (d) concentration (effective number of assets) and fold-to-fold weight stability as tie-breakers;
   (e) default to the constrained equal weight when no policy passes (b)-(c) robustly. Record the
   criterion as a `selection` entry before applying it. Never pick by the highest observed 2013-2019
   CAGR alone.
4. **Count the looks.** The registry counts distinct configurations evaluated on 2013-2019. Treat
   the best of K configurations as optimistically biased; the bias grows with K and with the
   similarity between candidates' validation performance.
5. **Previously inspected results.** The 2013-2019 results recorded so far are known. They may be
   described but must not be used to justify an elective change (e.g. "Sans Or" looked better, so
   remove gold) without a new, independent test.
6. **Final evaluation.** The 2020+ holdout stays locked; it is already partially exposed, so even a
   one-shot use of it would be a weak confirmation. A prospective record (paper portfolio from the
   date a policy is frozen) is the only fully clean test.

## Is nested walk-forward needed now?

Not at this stage. Nested validation is the right tool when a *data-driven* selection step is part of
the strategy (for example, picking the risk profile or estimator each year from its recent
performance). Today no such step exists: every policy is a fixed rule re-estimated on training data,
and the researcher-level choices above are controlled by rules 1-5. If an automatic selection rule
is introduced, it must be run inside each training window (inner walk-forward on the training years
only) so that the outer 2013-2019 results remain out of sample. Alternatively, a multiple-testing
adjustment (e.g. a deflated Sharpe ratio or White's reality check across the K registered
configurations) can quantify the selection bias.
