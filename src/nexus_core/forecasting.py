"""Leakage-resistant empirical forecasts for the NEXUS paper research layer."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


FEATURE_COLUMNS = ("ret5", "ret20", "ret60", "vol20", "ensemble_p_up")


@dataclass(frozen=True)
class EmpiricalForecast:
    position: int
    horizon: int
    current_price: float
    p10_return: float
    p50_return: float
    p90_return: float
    probability_positive: float
    neighbors: int
    baseline_p50_return: float


@dataclass(frozen=True)
class ForecastEvaluation:
    observations: int
    interval_coverage: float
    directional_accuracy: float
    brier_score: float
    median_mae: float
    baseline_median_mae: float
    median_mae_skill: float
    calibrated: bool
    promotion_allowed: bool
    blockers: tuple[str, ...]

    def to_dict(self) -> dict:
        value = asdict(self)
        value["blockers"] = list(self.blockers)
        return value


def prepare_price_frame(rows: pd.DataFrame) -> pd.DataFrame:
    """Create features known at each row using trailing prices only."""
    required = {"Date", "price_usd"}
    missing = required.difference(rows.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    frame = rows.copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["price_usd"] = pd.to_numeric(frame["price_usd"], errors="coerce")
    frame["ensemble_p_up"] = pd.to_numeric(
        frame.get("ensemble_p_up", pd.Series(index=frame.index, dtype=float)),
        errors="coerce",
    ).fillna(0.5)
    frame = frame.dropna(subset=["Date", "price_usd"])
    frame = frame[frame["price_usd"] > 0].sort_values("Date")
    frame = frame.drop_duplicates("Date", keep="last").reset_index(drop=True)
    returns = frame["price_usd"].pct_change()
    frame["ret5"] = frame["price_usd"].pct_change(5)
    frame["ret20"] = frame["price_usd"].pct_change(20)
    frame["ret60"] = frame["price_usd"].pct_change(60)
    frame["vol20"] = returns.rolling(20).std() * math.sqrt(252)
    return frame


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    order = np.argsort(values)
    ordered_values = values[order]
    ordered_weights = weights[order]
    cumulative = np.cumsum(ordered_weights)
    cutoff = quantile * cumulative[-1]
    return float(ordered_values[min(np.searchsorted(cumulative, cutoff), len(values) - 1)])


class AnalogForecaster:
    """Nearest historical analogs with labels strictly matured by decision time."""

    def __init__(self, minimum_history: int = 252, neighbors: int = 100):
        if minimum_history < 60 or neighbors < 20:
            raise ValueError("minimum_history or neighbors is too small")
        self.minimum_history = minimum_history
        self.neighbors = neighbors

    def predict(self, frame: pd.DataFrame, position: int, horizon: int) -> EmpiricalForecast | None:
        if horizon < 1 or position >= len(frame) or position < self.minimum_history:
            return None
        current = frame.loc[position, list(FEATURE_COLUMNS)].to_numpy(dtype=float)
        if not np.isfinite(current).all():
            return None

        # A candidate at j is legal only when its outcome at j+h is known by position.
        candidate_end = position - horizon
        candidate_positions = np.arange(60, candidate_end + 1)
        if len(candidate_positions) < self.minimum_history - 60:
            return None
        candidate_features = frame.loc[candidate_positions, list(FEATURE_COLUMNS)].to_numpy(dtype=float)
        start_prices = frame.loc[candidate_positions, "price_usd"].to_numpy(dtype=float)
        end_prices = frame.loc[candidate_positions + horizon, "price_usd"].to_numpy(dtype=float)
        labels = end_prices / start_prices - 1.0
        valid = np.isfinite(candidate_features).all(axis=1) & np.isfinite(labels)
        candidate_features, labels = candidate_features[valid], labels[valid]
        if len(labels) < max(40, self.neighbors // 2):
            return None

        center = np.median(candidate_features, axis=0)
        scale = np.median(np.abs(candidate_features - center), axis=0) * 1.4826
        scale = np.where(scale > 1e-8, scale, 1.0)
        distances = np.sqrt(np.mean(((candidate_features - current) / scale) ** 2, axis=1))
        count = min(self.neighbors, len(labels))
        nearest = np.argpartition(distances, count - 1)[:count]
        neighbor_labels = labels[nearest]
        weights = 1.0 / np.maximum(distances[nearest], 0.05)
        probability_positive = float(np.average(neighbor_labels > 0, weights=weights))
        return EmpiricalForecast(
            position=position,
            horizon=horizon,
            current_price=float(frame.loc[position, "price_usd"]),
            p10_return=_weighted_quantile(neighbor_labels, weights, 0.10),
            p50_return=_weighted_quantile(neighbor_labels, weights, 0.50),
            p90_return=_weighted_quantile(neighbor_labels, weights, 0.90),
            probability_positive=probability_positive,
            neighbors=count,
            baseline_p50_return=float(np.median(labels)),
        )

    def walk_forward(self, frame: pd.DataFrame, horizon: int) -> pd.DataFrame:
        records = []
        for position in range(self.minimum_history, len(frame) - horizon):
            forecast = self.predict(frame, position, horizon)
            if forecast is None:
                continue
            actual = float(frame.loc[position + horizon, "price_usd"] / forecast.current_price - 1)
            record = asdict(forecast)
            record.update({
                "date": frame.loc[position, "Date"],
                "outcome_date": frame.loc[position + horizon, "Date"],
                "actual_return": actual,
            })
            records.append(record)
        return pd.DataFrame(records)


def evaluate_forecasts(
    predictions: pd.DataFrame,
    source_point_in_time_verified: bool,
    minimum_oos: int = 252,
) -> ForecastEvaluation:
    blockers: list[str] = []
    observations = len(predictions)
    if not observations:
        return ForecastEvaluation(0, 0, 0, 1, 0, 0, 0, False, False, ("no_oos_predictions",))
    actual = predictions["actual_return"].to_numpy(float)
    p10 = predictions["p10_return"].to_numpy(float)
    p50 = predictions["p50_return"].to_numpy(float)
    p90 = predictions["p90_return"].to_numpy(float)
    probability = predictions["probability_positive"].to_numpy(float)
    baseline = predictions["baseline_p50_return"].to_numpy(float)
    coverage = float(np.mean((actual >= p10) & (actual <= p90)))
    accuracy = float(np.mean((p50 >= 0) == (actual >= 0)))
    brier = float(np.mean((probability - (actual > 0)) ** 2))
    mae = float(np.mean(np.abs(actual - p50)))
    baseline_mae = float(np.mean(np.abs(actual - baseline)))
    skill = 1 - mae / baseline_mae if baseline_mae > 0 else 0.0
    if observations < minimum_oos:
        blockers.append("insufficient_oos_observations")
    if not 0.70 <= coverage <= 0.90:
        blockers.append("interval_coverage_outside_gate")
    if brier > 0.25:
        blockers.append("brier_score_above_gate")
    if accuracy < 0.51:
        blockers.append("directional_accuracy_below_gate")
    if skill <= 0:
        blockers.append("no_median_mae_skill_vs_baseline")
    calibrated = not blockers
    if not source_point_in_time_verified:
        blockers.append("source_history_not_point_in_time_certified")
    # Historical evaluation is necessary but paper-forward repetition is still pending.
    blockers.append("paper_forward_evidence_pending")
    return ForecastEvaluation(
        observations, coverage, accuracy, brier, mae, baseline_mae, skill,
        calibrated, False, tuple(dict.fromkeys(blockers)),
    )


class PredictionLedger:
    """Append-only, idempotent registration of forecasts before outcomes exist."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @staticmethod
    def prediction_id(payload: dict) -> str:
        identity = {
            key: payload.get(key)
            for key in ("asset", "as_of_utc", "horizon_sessions", "model_version")
        }
        raw = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    def append(self, payloads: Iterable[dict]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    existing.add(json.loads(line)["prediction_id"])
                except (KeyError, ValueError, TypeError):
                    continue
        added = 0
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            for payload in payloads:
                record = dict(payload)
                record["prediction_id"] = self.prediction_id(record)
                if record["prediction_id"] in existing:
                    continue
                record["registered_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                record["outcome"] = None
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                existing.add(record["prediction_id"])
                added += 1
        return added


def business_session_age(as_of: datetime | pd.Timestamp, now: datetime | pd.Timestamp) -> int:
    """Approximate market-session age without pretending to know exchange holidays."""
    start = pd.Timestamp(as_of)
    end = pd.Timestamp(now)
    if start.tzinfo is not None:
        start = start.tz_convert("UTC").tz_localize(None)
    if end.tzinfo is not None:
        end = end.tz_convert("UTC").tz_localize(None)
    if end.normalize() <= start.normalize():
        return 0
    return max(0, len(pd.bdate_range(start.normalize(), end.normalize())) - 1)


def forward_registration_allowed(
    as_of: datetime | pd.Timestamp,
    now: datetime | pd.Timestamp,
    maximum_age_sessions: int = 1,
) -> bool:
    """Require a non-future source recent enough to be a genuine forward record."""
    source = pd.Timestamp(as_of)
    registered = pd.Timestamp(now)
    if source.tzinfo is None:
        source = source.tz_localize("UTC")
    else:
        source = source.tz_convert("UTC")
    if registered.tzinfo is None:
        registered = registered.tz_localize("UTC")
    else:
        registered = registered.tz_convert("UTC")
    return source <= registered and business_session_age(source, registered) <= maximum_age_sessions
