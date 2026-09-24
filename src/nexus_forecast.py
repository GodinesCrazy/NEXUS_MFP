"""Build provisional 1/5/20-session forecasts from frozen v1.7 OOS artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from nexus_core.forecasting import (
    AnalogForecaster,
    PredictionLedger,
    business_session_age,
    evaluate_forecasts,
    forward_registration_allowed,
    prepare_price_frame,
)


ROOT = Path(__file__).resolve().parents[1]
MODEL_VERSION = "analog-v0.1-challenger"
HORIZONS = (1, 5, 20)


def latest_runtime_root(root: Path) -> Path:
    candidates = list((root / "runtime").glob("**/mfp3_output_v17/time_machine_daily.csv"))
    if not candidates:
        raise FileNotFoundError("No se encontró time_machine_daily.csv de v1.7")
    return max(candidates, key=lambda path: path.stat().st_mtime).parent.parent


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def run(runtime_root: Path) -> dict:
    source = runtime_root / "mfp3_output_v17" / "time_machine_daily.csv"
    output = runtime_root / "mfp3_forecasts"
    output.mkdir(parents=True, exist_ok=True)
    data_hash = file_sha256(source)
    raw = pd.read_csv(source)
    forecaster = AnalogForecaster()
    current_records = []
    evaluations = []
    walk_forward_frames = []

    print("FORECAST_PHASE load_source")
    for asset in ("QQQ", "ECH", "CPER"):
        frame = prepare_price_frame(raw[raw["asset"] == asset])
        if frame.empty:
            continue
        print(f"FORECAST_PHASE walk_forward {asset}")
        asset_evaluations = {}
        for horizon in HORIZONS:
            predictions = forecaster.walk_forward(frame, horizon)
            evaluation = evaluate_forecasts(predictions, source_point_in_time_verified=False)
            asset_evaluations[horizon] = evaluation
            if not predictions.empty:
                predictions.insert(0, "asset", asset)
                walk_forward_frames.append(predictions)
            evaluations.append({"asset": asset, "horizon_sessions": horizon, **evaluation.to_dict()})
            current = forecaster.predict(frame, len(frame) - 1, horizon)
            if current is None:
                continue
            as_of_value = frame.iloc[-1]["Date"]
            as_of = (
                as_of_value.tz_localize(timezone.utc)
                if as_of_value.tzinfo is None
                else as_of_value.tz_convert(timezone.utc)
            ).isoformat()
            current_records.append({
                "asset": asset,
                "as_of_utc": as_of,
                "horizon_sessions": horizon,
                "current_price": current.current_price,
                "p10": current.current_price * (1 + current.p10_return),
                "p50": current.current_price * (1 + current.p50_return),
                "p90": current.current_price * (1 + current.p90_return),
                "probability_positive": current.probability_positive,
                "oos_observations": evaluation.observations,
                "calibrated": evaluation.calibrated,
                "promoted": evaluation.promotion_allowed,
                "model_version": MODEL_VERSION,
                "data_sha256": data_hash,
                "neighbors": current.neighbors,
                "blockers": list(evaluation.blockers),
            })

    print("FORECAST_PHASE persist")
    if walk_forward_frames:
        pd.concat(walk_forward_frames, ignore_index=True).to_csv(
            output / "walk_forward_predictions.csv", index=False
        )
    pd.DataFrame(evaluations).to_csv(output / "evaluation.csv", index=False)
    newest_as_of = max(pd.Timestamp(record["as_of_utc"]) for record in current_records)
    registered_now = datetime.now(timezone.utc)
    source_age_sessions = business_session_age(newest_as_of, registered_now)
    forward_registration_eligible = forward_registration_allowed(newest_as_of, registered_now)
    ledger_name = (
        "prediction_ledger.jsonl"
        if forward_registration_eligible
        else "retrospective_prediction_ledger.jsonl"
    )
    registration_status = (
        "paper_forward_registered"
        if forward_registration_eligible
        else "retroactive_research_snapshot"
    )
    ledger_records = [dict(record, registration_status=registration_status) for record in current_records]
    ledger = PredictionLedger(output / ledger_name)
    appended = ledger.append(ledger_records)
    decision_forecasts = [
        {key: record[key] for key in (
            "asset", "as_of_utc", "horizon_sessions", "current_price", "p10", "p50", "p90",
            "probability_positive", "oos_observations", "calibrated", "promoted",
        )}
        for record in current_records if record["horizon_sessions"] == 20
    ]
    payload = {
        "model_version": MODEL_VERSION,
        "source": str(source),
        "source_sha256": data_hash,
        "source_point_in_time_verified": False,
        "paper_forward_only": forward_registration_eligible,
        "real_trading_enabled": False,
        "source_age_sessions": source_age_sessions,
        "forward_registration_eligible": forward_registration_eligible,
        "registration_status": registration_status,
        "ledger_file": ledger_name,
        "forecasts": decision_forecasts,
        "horizon_forecasts": current_records,
        "evaluations": evaluations,
        "ledger_records_appended": appended,
    }
    write_json_atomic(output / "latest.json", payload)
    print(
        f"FORECAST_COMPLETE assets={len(decision_forecasts)} appended={appended} "
        f"registration={registration_status}"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="NEXUS provisional paper forecast engine")
    parser.add_argument("--runtime-root", type=Path)
    args = parser.parse_args()
    runtime_root = args.runtime_root.resolve() if args.runtime_root else latest_runtime_root(ROOT)
    run(runtime_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
