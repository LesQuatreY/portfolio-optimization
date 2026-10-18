"""Fixed targets, fractional total-return units and exact self-financing; no fetching.

Research is never written to or imported. Real panels require a validated, pinned local
catalog entry for EVERY asset. Synthetic panels must explicitly declare their nature.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import numpy as np
import pandas as pd
import yaml

from .guard import ArtifactSpec, CutoffViolation, HARD_CUTOFF, ResearchGuard
from .settings import load_settings

ROOT = Path(__file__).resolve().parents[3]
DEVELOPMENT_START = pd.Timestamp("2014-10-01")
MODES = {"monthly": "Mensuel", "annual": "Annuel", "buy_hold": "Achat-conservation"}


class DataUnavailable(ValueError):
    """No fallback, interpolation or change of weights is permitted."""


def _date(value):
    try:
        stamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Date invalide.") from exc
    if pd.isna(stamp) or stamp.tz is not None or stamp != stamp.normalize():
        raise ValueError("Dates journalières sans fuseau requises.")
    if stamp > HARD_CUTOFF:
        raise CutoffViolation("La période TEST est verrouillée.")
    return stamp


def _number(value, label):
    if isinstance(value, (bool, str)) or not isinstance(value, (int, float, np.number)) or not math.isfinite(value):
        raise ValueError(f"{label} doit être un nombre fini.")
    return float(value)


@dataclass(frozen=True)
class PortfolioSpec:
    name: str
    weights: Mapping[str, float]
    rebalance: str = "monthly"
    initial_capital: float = 100000.0
    cost_bps: float = 0.0
    start: str = "2014-10-01"
    end: str = "2023-12-29"
    currency: str = "EUR"
    schema_version: int = 1

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 120:
            raise ValueError("Nom requis (120 caractères maximum).")
        if type(self.schema_version) is not int or self.schema_version != 1 or self.currency != "EUR":
            raise ValueError("Version ou devise non prise en charge.")
        if self.rebalance not in MODES:
            raise ValueError("Fréquence de rééquilibrage inconnue.")
        if not isinstance(self.weights, Mapping) or not self.weights:
            raise ValueError("Sélectionnez au moins un actif.")
        weights = {}
        for asset, value in self.weights.items():
            if not isinstance(asset, str) or not asset or len(asset) > 80:
                raise ValueError("Identifiant d'actif invalide.")
            weight = _number(value, "Poids")
            if not 0 < weight <= 1:
                raise ValueError("Chaque actif sélectionné doit avoir un poids strictement positif.")
            weights[asset] = weight
        if abs(math.fsum(weights.values()) - 1) > 1e-10:
            raise ValueError("La somme des poids doit être égale à 100 %.")
        capital = _number(self.initial_capital, "Capital")
        cost = _number(self.cost_bps, "Frais")
        if capital <= 0 or not 0 <= cost < 10000:
            raise ValueError("Capital positif et frais compris entre 0 et 10 000 pb exclus requis.")
        start, end = _date(self.start), _date(self.end)
        if start < DEVELOPMENT_START:
            raise ValueError("La fenêtre V2.1 commence au 01/10/2014.")
        if start >= end:
            raise ValueError("La fin doit suivre le début.")
        object.__setattr__(self, "weights", MappingProxyType(dict(sorted(weights.items()))))
        object.__setattr__(self, "initial_capital", capital)
        object.__setattr__(self, "cost_bps", cost)
        object.__setattr__(self, "start", start.strftime("%Y-%m-%d"))
        object.__setattr__(self, "end", end.strftime("%Y-%m-%d"))

    def to_dict(self):
        return {"schema_version": self.schema_version, "name": self.name, "weights": dict(self.weights),
                "rebalance": self.rebalance, "initial_capital": self.initial_capital,
                "cost_bps": self.cost_bps, "start": self.start, "end": self.end, "currency": self.currency}

    @property
    def identity(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Clé JSON dupliquée.")
        out[key] = value
    return out


def load_spec(path: Path) -> PortfolioSpec:
    # Specifications are not datasets. Never open arbitrary Research files from this API.
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()) or path.parent != (ROOT / "config/v2/portfolios").resolve():
        raise ValueError("Chargement réservé au dossier config/v2/portfolios du Lab.")
    if path.suffix.lower() != ".json" or path.stat().st_size > 64000:
        raise ValueError("Configuration JSON uniquement, 64 Ko maximum.")
    return PortfolioSpec(**json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs))


def save_spec(spec: PortfolioSpec, folder: Path | None = None) -> Path:
    """Content-addressed portable JSON; no overwriting and no arbitrary UI destination."""
    folder = Path(folder or ROOT / "config/v2/portfolios").resolve()
    # Only a dedicated Lab folder is writable; no destination in Research is possible.
    allowed = (ROOT / "config/v2/portfolios").resolve()
    if not folder.is_relative_to(ROOT.resolve()) or folder != allowed:
        raise ValueError("Enregistrement réservé au dossier config/v2/portfolios du Lab.")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{spec.identity}.json"
    payload = json.dumps(spec.to_dict(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if load_spec(path).identity != spec.identity:
            raise ValueError("Conflit de configuration ; fichier conservé.")
    else:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    return path


def load_catalog(path: Path | None = None) -> dict:
    path = Path(path or ROOT / "config/v2/custom_assets.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data["schema_version"] != 1:
        raise ValueError("Version de catalogue inconnue.")
    return data["assets"]


def availability(spec: PortfolioSpec, catalog: dict) -> list[str]:
    missing = []
    for asset in spec.weights:
        item = catalog.get(asset)
        if item is None:
            missing.append(f"{asset} : actif absent du catalogue")
        elif item.get("status") != "validated":
            missing.append(f"{item['label']} : {item.get('reason', 'validation incomplète')}")
    return missing


def _index_guard(index):
    if not isinstance(index, pd.DatetimeIndex) or index.empty or index.tz is not None or index.hasnans:
        raise ValueError("Calendrier journalier explicite requis.")
    if index.max() > HARD_CUTOFF:
        raise CutoffViolation("Observation après le 29/12/2023 interdite.")
    if index.has_duplicates or not index.is_monotonic_increasing or not index.equals(index.normalize()):
        raise ValueError("Séances uniques, normalisées et triées requises.")


@dataclass(frozen=True)
class PricePanel:
    prices: pd.DataFrame
    provenance: Mapping
    synthetic: bool = False
    currency: str = "EUR"
    sessions: pd.DatetimeIndex | None = None


def load_validated_panel(spec: PortfolioSpec, catalog: dict | None = None) -> PricePanel:
    """Opt-in local artifacts only, using the existing integrity/cutoff guard unchanged.

    Catalog entries must pin a safe local source and calendar/clock/dividend audit.
    No entry ships as validated. No raw or mixed TEST source is ever discovered here.
    """
    catalog = load_catalog() if catalog is None else catalog
    blocked = availability(spec, catalog)
    if blocked:
        raise DataUnavailable("Simulation historique indisponible :\n" + "\n".join(blocked))
    settings = load_settings(ROOT)
    provenance, pieces = {}, []
    for asset in spec.weights:
        item = catalog[asset]
        required = ("sha256", "path", "calendar", "clock", "dividends", "source", "independent_check",
                    "calendar_path", "calendar_sha256")
        if not all(item.get(key) for key in required) or item.get("currency") != "EUR":
            raise DataUnavailable(f"{asset} : provenance, EUR ou contrôles manquants.")
        # Sources are confined to the Lab data directory, not a Research discovery mechanism.
        root = ROOT / "data/v2_1"
        guard = ResearchGuard(root, [ArtifactSpec(asset, item["path"], item["sha256"])])
        # Defense in depth: refuse any pointer into protected Research, including a symlink root.
        if not root.resolve().is_relative_to(ROOT.resolve()) or root.resolve().is_relative_to(settings.research_root.resolve()):
            raise DataUnavailable("Source locale isolée requise.")
        if Path(item["path"]).suffix.lower() not in (".csv", ".parquet"):
            raise DataUnavailable("CSV ou parquet uniquement pour les niveaux.")
        frame = guard.load(asset)
        if "Date" in frame.columns:
            frame = frame.set_index("Date")
        if list(frame.columns) != ["level"]:
            raise DataUnavailable(f"{asset} : colonne level unique requise.")
        frame.index = pd.DatetimeIndex(frame.index)
        _index_guard(frame.index)
        pieces.append(frame.loc[spec.start:spec.end, "level"].rename(asset))
        provenance[asset] = dict(item)
    # No automatic intersection or filling: the approved common calendar must already match.
    if any(not pieces[0].index.equals(s.index) for s in pieces[1:]):
        raise DataUnavailable("Calendriers différents : alignement causal à valider avant simulation.")
    clocks = {(catalog[a]["calendar"], catalog[a]["clock"]) for a in spec.weights}
    if len(clocks) != 1:
        raise DataUnavailable("Calendrier et convention d'information communs requis.")
    item = catalog[next(iter(spec.weights))]
    if len({(catalog[a]["calendar_path"], catalog[a]["calendar_sha256"]) for a in spec.weights}) != 1:
        raise DataUnavailable("Un même calendrier vérifié est requis.")
    calendar_guard = ResearchGuard(ROOT / "data/v2_1", [ArtifactSpec(
        "sessions", item["calendar_path"], item["calendar_sha256"])])
    dates = calendar_guard.load("sessions")
    if list(dates.columns) != ["Date"]:
        raise DataUnavailable("Calendrier : une colonne Date uniquement.")
    sessions = pd.DatetimeIndex(pd.to_datetime(dates["Date"]))
    _index_guard(sessions)
    sessions = sessions[(sessions >= _date(spec.start)) & (sessions <= _date(spec.end))]
    return PricePanel(pd.concat(pieces, axis=1), provenance, sessions=sessions)


def to_eur(values: pd.Series, currency: str, usd_per_eur: pd.Series | None = None) -> pd.Series:
    """Quote-direction convention audited in V1; timestamps must already be causal."""
    _index_guard(values.index)
    if currency == "EUR":
        out = values.copy()
    elif currency == "USD" and usd_per_eur is not None:
        _index_guard(usd_per_eur.index)
        rates = usd_per_eur.reindex(values.index)
        if rates.isna().any() or not np.isfinite(rates).all() or (rates <= 0).any():
            raise DataUnavailable("Change EUR/USD manquant ou invalide ; aucun remplissage.")
        out = values / rates
    else:
        raise ValueError("Conversion non prise en charge.")
    if not np.isfinite(out).all() or (out <= 0).any():
        raise DataUnavailable("Niveaux invalides.")
    return out


@dataclass(frozen=True)
class BacktestResult:
    spec: PortfolioSpec
    ledger: pd.DataFrame
    holdings: pd.DataFrame
    trades: pd.DataFrame
    prices: pd.DataFrame
    provenance: dict
    synthetic: bool

    @property
    def weights(self):
        return self.holdings.mul(self.prices).div(self.ledger["nav"], axis=0)

    def metadata(self):
        return {"portfolio": self.spec.to_dict(), "identity": self.spec.identity,
                "synthetic": self.synthetic, "currency": "EUR", "provenance": self.provenance,
                "engine_version": 1,
                "prices_sha256": hashlib.sha256(pd.util.hash_pandas_object(
                    self.prices, index=True).values.tobytes()).hexdigest(),
                "execution": "fixed_target_fractional_basket_common_close_v1",
                "tax_net_cagr": None, "cash_interest": 0, "final_liquidation": False,
                "turnover": "sum(abs(traded_notional))/pretrade_nav; initial purchase included"}


def simulate(spec: PortfolioSpec, panel: PricePanel) -> BacktestResult:
    """Ideal fractional basket at a shared close, targets fixed before the session.

    No same-day signal: schedule and target fractions are fixed ex ante. Fill units depend
    on the common execution price (ideal value-based basket, no share rounding/slippage).
    Every asset/FX level must be synchronized by the data audit BEFORE entering here.
    No fills, missing-asset replacements or implicit calendar intersections occur.
    """
    prices = panel.prices
    _index_guard(prices.index)  # before inspecting market values
    if panel.sessions is None:
        raise DataUnavailable("Calendrier attendu explicite requis.")
    _index_guard(panel.sessions)
    if not prices.index.equals(panel.sessions):
        raise DataUnavailable("Séances manquantes ou supplémentaires par rapport au calendrier validé.")
    if panel.currency != "EUR":
        raise ValueError("Le moteur exige des niveaux de rendement total en EUR.")
    assets = list(spec.weights)
    if prices.columns.has_duplicates or set(prices.columns) != set(assets):
        raise DataUnavailable("Tous les actifs sélectionnés sont requis, sans substitution.")
    if not panel.synthetic:
        for asset in assets:
            p = panel.provenance.get(asset, {})
            if p.get("status") != "validated" or not all(p.get(k) for k in
                    ("sha256", "source", "independent_check", "dividends", "calendar", "clock")):
                raise DataUnavailable("Provenance validée requise pour chaque série réelle.")
        if len({(panel.provenance[a]["calendar"], panel.provenance[a]["clock"]) for a in assets}) != 1:
            raise DataUnavailable("Convention temporelle commune requise.")
    if prices.index[0] != _date(spec.start) or prices.index[-1] != _date(spec.end) or len(prices) < 2:
        raise DataUnavailable("Les bornes exactes de la simulation doivent être couvertes.")
    prices = prices.loc[:, assets].astype(float).copy()
    if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any().any():
        raise DataUnavailable("Prix manquant, nul ou invalide : aucun remplissage autorisé.")
    target = np.array([spec.weights[a] for a in assets])
    held = np.zeros(len(assets))
    cash = spec.initial_capital
    rate = spec.cost_bps / 10000
    ledger, holdings, trades = [], [], []
    last_period = None
    for i, (date, row) in enumerate(prices.iterrows()):
        price = row.to_numpy()
        old_values = held * price
        before = float(old_values.sum() + cash)
        period = (date.year, date.month) if spec.rebalance == "monthly" else date.year
        execute = i == 0 or (spec.rebalance != "buy_hold" and period != last_period)
        fee, notional = 0.0, 0.0
        if execute:
            # Unique root v + c*sum(|w*v-old_values|) = pretrade wealth.
            # Strictly increasing for c<1; bisection is exact to floating precision.
            lo, hi = 0.0, before
            for _ in range(100):
                mid = (lo + hi) / 2
                if mid + rate * np.abs(target * mid - old_values).sum() > before:
                    hi = mid
                else:
                    lo = mid
            after = (lo + hi) / 2
            new_held = target * after / price
            delta = new_held - held
            notionals = delta * price
            fee = float(rate * np.abs(notionals).sum())
            notional = float(np.abs(notionals).sum())
            cash = float(before - (new_held * price).sum() - fee)
            if abs(cash) > 1e-9 * max(1, before):
                raise ArithmeticError("Comptabilité non autofinancée.")
            # Numerical residual only; never financed externally.
            for asset, qty, amount in zip(assets, delta, notionals):
                if abs(amount) > 1e-10:
                    trades.append((date, asset, float(qty), float(amount), abs(float(amount)) * rate))
            held = new_held
        nav = float((held * price).sum() + cash)
        ledger.append((date, before, nav, cash, fee, notional, notional / before, execute))
        holdings.append(held.copy())
        last_period = period
    book = pd.DataFrame(ledger, columns=["Date", "pretrade_nav", "nav", "cash", "cost", "notional",
                                         "turnover", "rebalance"]).set_index("Date")
    tx = pd.DataFrame(trades, columns=["Date", "asset", "quantity", "notional", "cost"])
    return BacktestResult(spec, book, pd.DataFrame(holdings, index=prices.index, columns=assets), tx,
                          prices, {k: dict(v) for k, v in panel.provenance.items()}, panel.synthetic)
