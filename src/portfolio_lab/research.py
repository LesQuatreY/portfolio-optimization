"""Shared research configuration and the one data-loading path used by every notebook.

config/research.yaml is the single source of truth. load_research_config() validates it
and builds the engine Config:

* Config.assets  = eligible universe + benchmark (everything that must be loaded);
* Config.eligible = the universe entries only (direct-allocation eligibility);
* investor constraints, estimators, risk profiles, leverage costs and the walk-forward
  protocol come from the same file, so both notebooks always agree.
"""
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
import hashlib
import json

import pandas as pd

from .assets import resolve_assets
from .config import Config, WalkForwardSettings, eligible_names
from .protocol import DEVELOPMENT_END, HOLDOUT_START, assert_dates_before_holdout

DEFAULT_CONFIG_PATH = Path("config/research.yaml")
ANALYSIS_WINDOWS = ("development", "research")
_SECTIONS = {"universe", "benchmark", "leverage", "leverage_costs", "rates", "holding_costs", "constraints",
             "estimation", "risk_profiles", "protocol", "walk_forward", "universe_variants", "method_variants"}


def find_project_dir(start: Path | None = None) -> Path:
    """Nearest ancestor containing config/research.yaml (works from notebooks/ or the root)."""
    start = Path.cwd() if start is None else Path(start)
    for candidate in (start, *start.resolve().parents):
        if (candidate / DEFAULT_CONFIG_PATH).exists():
            return candidate
    raise FileNotFoundError(f"No {DEFAULT_CONFIG_PATH} found above {start}.")


@dataclass(frozen=True)
class ResearchConfig:
    """Engine Config plus the research-protocol choices that are not engine parameters."""
    config: Config
    analysis_window: str
    # (label, assets excluded from direct allocation, leveraged underlyings used unleveraged)
    universe_variants: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...]
    # Where the investor bounds come from (free text, recorded in every registry entry).
    constraint_provenance: str = ""
    # (label, estimation overrides) for pre-registered method comparisons.
    method_variants: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = ()
    source: Path | None = None
    raw: Mapping = field(default_factory=dict, compare=False, repr=False)

    @property
    def eligible(self) -> list[str]:
        return eligible_names(self.config)

    @property
    def analysis_end(self) -> pd.Timestamp:
        """Exclusive end of the in-sample analysis window."""
        return pd.Timestamp(self.config.development_end if self.analysis_window == "development"
                            else self.config.end)

    def methods(self) -> dict[str, Config]:
        """Config of each pre-registered estimation-method variant (only estimation fields change)."""
        keys = {"expected_returns": "expected_return_method", "growth_drift": "growth_drift",
                "covariance": "covariance_method", "resampling_draws": "resampling_draws"}
        return {label: replace(self.config, **{keys[k]: (int(v) if k == "resampling_draws" else v)
                                               for k, v in overrides})
                for label, overrides in self.method_variants} or {"Référence": self.config}

    def variants(self) -> dict[str, dict[str, tuple[str, ...]]]:
        return {label: {"exclude": excluded, "unlevered": unlevered}
                for label, excluded, unlevered in self.universe_variants}

    def snapshot(self) -> dict:
        """JSON-serializable description of every research assumption (for experiment tracking)."""
        config = asdict(self.config)
        config.pop("cache_dir"), config.pop("output_dir")
        return {"config": json.loads(json.dumps(config, default=str)), "analysis_window": self.analysis_window,
                "constraint_provenance": self.constraint_provenance,
                "universe_variants": {k: {"exclude": list(e), "unlevered": list(u)}
                                      for k, e, u in self.universe_variants},
                "holdout_start": str(HOLDOUT_START.date())}

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.snapshot(), sort_keys=True).encode()).hexdigest()[:12]

    def describe(self) -> pd.DataFrame:
        """French, human-readable summary of the study configuration (notebook display)."""
        c = self.config
        wf = c.walk_forward
        leverage = ", ".join(f"{name} ×{factor:g}" for name, factor in c.leverage) or "aucun"
        caps = ", ".join(f"{n} ≤ {w:.0%}" for n, w in c.max_weights) or "aucune"
        floors = ", ".join(f"{n} ≥ {w:.0%}" for n, w in c.min_weights) or "aucun"
        rows = {
            "Actifs éligibles (allocation directe)": ", ".join(self.eligible),
            "Indice de référence passif": c.benchmark or "aucun",
            "Levier synthétique": leverage,
            "Frais annuels du produit à levier": f"{c.leverage_annual_fee:.2%} + (L−1) × taux de financement",
            "Poids maximum (contrainte investisseur)": caps,
            "Poids minimum (contrainte investisseur)": floors,
            "Origine des contraintes": self.constraint_provenance or "non renseignée",
            "Covariance / rendements espérés / dérive": (f"{c.covariance_method} / {c.expected_return_method} / "
                                                          f"{c.growth_drift}"),
            "Variantes de méthode pré-enregistrées": ", ".join(label for label, _ in self.method_variants) or "aucune",
            "Taux sans risque (Sharpe, EUR)": (f"série {c.risk_free_series}, point-in-time" if c.risk_free_series
                                               else f"constante {c.risk_free_rate:.2%}"),
            "Taux de financement du levier": (", ".join(f"{ccy} : {sid}" for ccy, sid in c.financing_series)
                                              + f" + écart {c.leverage_financing_spread:.2%}"
                                              if c.financing_series else f"constante {c.leverage_financing_rate:.2%}"),
            "Coûts de détention des indices": (", ".join(f"{n} {v:.2%}/an" for n, v in c.holding_costs)
                                               or "aucun"),
            "Profils de risque (plafonds de volatilité estimée)":
                ", ".join(f"{n} {v:.0%}" for n, v in c.targets),
            "Fin des données (exclusive)": c.end,
            "Fin de la période de développement (exclusive)": c.development_end,
            "Fenêtre d'analyse in-sample": ("développement (avant " + c.development_end + ")"
                                            if self.analysis_window == "development"
                                            else "recherche complète (avant " + c.end + ")"),
            "Walk-forward": (f"{wf.window}, {wf.train_years} ans d'apprentissage, années test "
                             f"{wf.first_test_year}–{wf.last_test_year}, rééquilibrage {wf.rebalance}, "
                             f"décalage de décision {wf.decision_lag_sessions} séance(s), "
                             f"coûts {wf.transaction_cost_bps:g} pb"),
            "Holdout final verrouillé": f"à partir du {HOLDOUT_START.date()} (inaccessible)",
        }
        return pd.DataFrame({"Valeur": rows}).rename_axis("Paramètre")


def _mapping(raw, name: str) -> dict:
    value = raw.get(name) or {}
    if not isinstance(value, Mapping):
        raise ValueError(f"research config: '{name}' must be a mapping.")
    return dict(value)


def parse_research_config(raw: Mapping, project_dir: Path = Path("."), source: Path | None = None,
                          catalogue=None) -> ResearchConfig:
    """Validate a parsed YAML mapping and build the ResearchConfig (no file or network access)."""
    if not isinstance(raw, Mapping):
        raise ValueError("research config must be a mapping.")
    unknown = set(raw) - _SECTIONS
    if unknown:
        raise ValueError(f"research config: unknown sections {sorted(unknown)}.")
    universe = {str(k): str(v) for k, v in _mapping(raw, "universe").items()}
    if not universe:
        raise ValueError("research config: the universe needs at least one eligible asset.")
    benchmark = _mapping(raw, "benchmark")
    assets = dict(universe)
    benchmark_name = None
    if benchmark:
        if set(benchmark) != {"name", "symbol"}:
            raise ValueError("research config: benchmark needs exactly 'name' and 'symbol'.")
        benchmark_name, symbol = str(benchmark["name"]), str(benchmark["symbol"])
        if benchmark_name in assets and assets[benchmark_name] != symbol:
            raise ValueError(f"research config: benchmark '{benchmark_name}' conflicts with the universe symbol.")
        if benchmark_name not in assets and symbol in assets.values():
            raise ValueError("research config: the benchmark symbol is already in the universe under another name.")
        assets.setdefault(benchmark_name, symbol)
    leverage = {str(k): float(v) for k, v in _mapping(raw, "leverage").items() if float(v) != 1}
    costs = _mapping(raw, "leverage_costs")
    rates = _mapping(raw, "rates")
    constraints = _mapping(raw, "constraints")
    estimation = _mapping(raw, "estimation")
    protocol = _mapping(raw, "protocol")
    wf = _mapping(raw, "walk_forward")
    profiles = _mapping(raw, "risk_profiles")
    holding = {str(k): float(v) for k, v in _mapping(raw, "holding_costs").items()}
    for name, mapping in (("leverage_costs", costs), ("constraints", constraints), ("estimation", estimation),
                          ("protocol", protocol), ("rates", rates)):
        allowed = {"leverage_costs": {"annual_fee"},
                   "constraints": {"max_weights", "min_weights", "provenance"},
                   "estimation": {"covariance", "expected_returns", "growth_drift"},
                   "protocol": {"study_end", "development_end", "analysis_window"},
                   "rates": {"risk_free", "financing_base", "financing_spread"}}[name]
        if set(mapping) - allowed:
            raise ValueError(f"research config: unknown keys in '{name}': {sorted(set(mapping) - allowed)}. "
                             "Rates are set in 'rates' (risk_free, financing_base, financing_spread).")
    # Economically distinct roles: the investor-currency risk-free reference (Sharpe) and the base rate
    # of leverage financing in each product currency, plus a spread. Each is a constant or a FRED series.
    from .rates import RateSpec
    risk_free = RateSpec.parse(rates.get("risk_free", 0.))
    base = rates.get("financing_base", 0.)
    base = {str(k): RateSpec.parse(v) for k, v in base.items()} if isinstance(base, Mapping) else \
        {ccy: RateSpec.parse(base) for ccy in ("USD", "EUR")}
    spread = float(rates.get("financing_spread", 0.))
    constant_financing = [spec.constant for spec in base.values() if spec.constant is not None]
    if constant_financing and len(constant_financing) != len(base):
        raise ValueError("research config: financing_base must be all constants or all series.")
    analysis_window = protocol.get("analysis_window", "development")
    if analysis_window not in ANALYSIS_WINDOWS:
        raise ValueError(f"research config: analysis_window must be one of {ANALYSIS_WINDOWS}.")
    settings = WalkForwardSettings(**wf)
    project_dir = Path(project_dir)
    config = Config(
        assets=resolve_assets(assets, catalogue=catalogue), eligible=tuple(universe), benchmark=benchmark_name,
        leverage=tuple(leverage.items()),
        leverage_annual_fee=float(costs.get("annual_fee", 0.)),
        leverage_financing_rate=(constant_financing[0] + spread) if constant_financing else 0.,
        leverage_financing_spread=spread,
        risk_free_series=risk_free.series,
        financing_series=tuple((ccy, spec.series) for ccy, spec in base.items() if spec.series is not None),
        holding_costs=tuple(holding.items()),
        max_weights=tuple((str(k), v) for k, v in (constraints.get("max_weights") or {}).items()),
        min_weights=tuple((str(k), v) for k, v in (constraints.get("min_weights") or {}).items()),
        covariance_method=estimation.get("covariance", "ledoit_wolf"),
        expected_return_method=estimation.get("expected_returns", "sample"),
        growth_drift=estimation.get("growth_drift", "sample"),
        risk_free_rate=risk_free.constant if risk_free.constant is not None else 0.,
        targets=tuple((str(k), float(v)) for k, v in profiles.items()) or Config.__dataclass_fields__[
            "targets"].default,
        end=str(protocol.get("study_end", HOLDOUT_START.date().isoformat())),
        development_end=str(protocol.get("development_end", DEVELOPMENT_END.date().isoformat())),
        walk_forward=settings,
        cache_dir=project_dir / ".cache/market", output_dir=project_dir / "outputs")
    variants = []
    for label, spec in _mapping(raw, "universe_variants").items():
        # A list = exclusions; a mapping may also name leveraged underlyings to use unleveraged.
        if isinstance(spec, Mapping):
            if set(spec) - {"exclude", "unlevered"}:
                raise ValueError(f"research config: variant '{label}' accepts only 'exclude' and 'unlevered'.")
            excluded = tuple(str(name) for name in (spec.get("exclude") or []))
            unlevered = tuple(str(name) for name in (spec.get("unlevered") or []))
        else:
            excluded, unlevered = tuple(str(name) for name in (spec or [])), ()
        not_levered = [name for name in unlevered if name not in leverage]
        if not_levered:
            raise ValueError(f"research config: variant '{label}' unlevers {not_levered}, which have no leverage.")
        missing = [name for name in excluded if name not in universe]
        if missing:
            raise ValueError(f"research config: variant '{label}' excludes {missing}, not in the universe.")
        if len(excluded) >= len(universe):
            raise ValueError(f"research config: variant '{label}' leaves no eligible asset.")
        variants.append((str(label), excluded, unlevered))
    methods = []
    for label, overrides in _mapping(raw, "method_variants").items():
        overrides = dict(overrides or {})
        if set(overrides) - {"expected_returns", "growth_drift", "covariance", "resampling_draws"}:
            raise ValueError(f"research config: method '{label}' may only override estimation keys.")
        methods.append((str(label), tuple(sorted((str(k), str(v)) for k, v in overrides.items()))))
    provenance = str(constraints.get("provenance", "")).strip()
    if (config.max_weights or config.min_weights) and not provenance:
        raise ValueError("research config: investor constraints need a 'provenance' note (who set them, when, "
                         "and whether validation results had been seen).")
    research = ResearchConfig(config, analysis_window, tuple(variants), provenance, tuple(methods), source, raw)
    research.methods()  # validate every method configuration now
    return research


def load_research_config(project_dir: Path | None = None, path: Path | None = None) -> ResearchConfig:
    import yaml
    project_dir = find_project_dir() if project_dir is None else Path(project_dir)
    path = project_dir / DEFAULT_CONFIG_PATH if path is None else Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return parse_research_config(raw, project_dir, path)


@dataclass
class ResearchStudy:
    """Loaded, EUR-normalized research data (always before the holdout) and its configuration."""
    research: ResearchConfig
    data: object
    prices: pd.DataFrame
    leverage_diagnostics: pd.DataFrame
    rates: object = None

    def config_for(self, prices: pd.DataFrame) -> Config:
        """The study Config with the risk-free rate averaged over the dates of `prices` (in-sample use)."""
        if self.rates is None:
            return self.config
        return replace(self.config, risk_free_rate=self.rates.mean_risk_free(prices.index))

    @property
    def config(self) -> Config:
        return self.research.config

    def analysis_prices(self) -> pd.DataFrame:
        """In-sample analysis window (development period by default)."""
        return self.prices.loc[self.prices.index < self.research.analysis_end]

    def development_prices(self) -> pd.DataFrame:
        return self.prices.loc[self.prices.index < pd.Timestamp(self.config.development_end)]

    def reference_covariance(self, assets=None) -> pd.DataFrame:
        """Fixed Ledoit-Wolf covariance of the development period (before validation), used to measure
        exposure changes in risk units independently of each fold's own estimate."""
        from .covariance import estimate_covariance
        from .returns import simple_returns
        dev = self.development_prices()
        dev = dev if assets is None else dev[list(assets)]
        return estimate_covariance(simple_returns(dev), "ledoit_wolf", self.config.trading_days).matrix


def build_rates(config: Config, provider=None):
    """Rates object for a Config (FRED series fetched before the study end; constants otherwise)."""
    from .rates import RateSpec, load_rates
    risk_free = RateSpec(series=config.risk_free_series) if config.risk_free_series else \
        RateSpec(constant=config.risk_free_rate)
    financing = {ccy: RateSpec(series=sid) for ccy, sid in config.financing_series} or \
        {ccy: RateSpec(constant=config.leverage_financing_rate - config.leverage_financing_spread)
         for ccy in ("USD", "EUR")}
    if provider is None and (config.risk_free_series or config.financing_series):
        from .data import FREDProvider
        provider = FREDProvider(config.cache_dir / "fred")
    return load_rates(risk_free, financing, config.end, provider)


def load_research_study(research: ResearchConfig | None = None, provider=None, rate_provider=None) -> ResearchStudy:
    """The single data path of both notebooks: load, convert to EUR, add synthetic leverage, then
    deduct index holding costs. Rates are point in time and stop before the study end."""
    from .data import load_market_data
    from .leverage import add_leverage
    from .returns import apply_holding_costs
    research = load_research_config() if research is None else research
    config = research.config
    data = load_market_data(config, provider)
    rates = build_rates(config, rate_provider)
    prices, diagnostics = add_leverage(data.common, data.native, data.fx, config, rates=rates)
    prices = apply_holding_costs(prices, config.holding_costs, config.calendar_days_per_year)
    assert_dates_before_holdout(prices.index, "Research prices")
    return ResearchStudy(research, data, prices, diagnostics, rates)


# French display labels of return classifications (catalogue values stay in English).
_RETURN_TYPES_FR = {"Adjusted price": "Cours ajusté (dividendes bruts réinvestis)",
                    "Gross Return": "Indice rendement total, dividendes bruts",
                    "Net Total Return": "Indice rendement total, dividendes nets",
                    "Price Return": "Prix seul (sans revenu)", "Total Return": "Rendement total"}


def instrument_table(study: "ResearchStudy") -> pd.DataFrame:
    """French data-quality summary: what each series represents and how it is made investable."""
    config = study.config
    costs, eligible = dict(config.holding_costs), set(eligible_names(config))
    rows = []
    for asset in config.assets:
        role = ("éligible" if asset.name in eligible else "") + (
            " + référence passive" if asset.name == config.benchmark else "")
        rows.append({"Actif": asset.name, "Rôle": role.strip(" +") or "chargé seulement",
                     "Symbole": asset.symbol, "Nature de la série": _RETURN_TYPES_FR.get(asset.return_type,
                                                                                         asset.return_type),
                     "Devise": asset.currency,
                     "Coût de détention ajouté": f"{costs[asset.name]:.2%}/an" if asset.name in costs else "—",
                     "Limite connue (catalogue)": asset.limitation or "—"})
    for name, factor in config.leverage:
        rows.append({"Actif": f"{name} x{factor:g}", "Rôle": "éligible (remplace le sous-jacent)",
                     "Symbole": "synthétique", "Nature de la série": f"Levier quotidien ×{factor:g} reconstruit",
                     "Devise": next(a.currency for a in config.assets if a.name == name),
                     "Coût de détention ajouté": (f"{config.leverage_annual_fee:.2%} + (L−1) × (taux court "
                                                  f"historique + {config.leverage_financing_spread:.2%})"),
                     "Limite connue (catalogue)": "Approximation : écart de suivi, swaps et fiscalité non modélisés."})
    return pd.DataFrame(rows).set_index("Actif")
