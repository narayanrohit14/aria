from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mlflow

from ml.evaluation.evaluate import (
    EVALUATION_REPORT_PATH,
    print_evaluation_summary,
    run_evaluation,
    save_evaluation_report,
)
from ml.features.feature_engineering import build_feature_matrix
from ml.models.fraud_classifier import MLRUNS_DIR, load_fraud_classifier, train_fraud_classifier
from ml.models.risk_scorer import compute_transaction_risk_score, save_risk_scorer_metadata


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full ARIA ML training pipeline.")
    parser.add_argument(
        "--experiment-name",
        default="aria-fraud-detection",
        help="MLflow experiment name.",
    )
    parser.add_argument(
        "--run-name",
        default=datetime.now().strftime("%Y-%m-%d-%H%M"),
        help="MLflow run name.",
    )
    return parser.parse_args()


def _risk_level_percentages(scores):
    high = float((scores >= 65).mean() * 100)
    medium = float(((scores >= 35) & (scores < 65)).mean() * 100)
    low = float((scores < 35).mean() * 100)
    return high, medium, low


def main() -> int:
    args = _parse_args()

    try:
        mlflow.set_tracking_uri(MLRUNS_DIR.as_uri())

        print("Loading and engineering features...")
        X, y = build_feature_matrix()
        print(f"Feature matrix shape: {X.shape}")
        print(f"Fraud rate: {y.mean():.4f}")

        print("Training fraud classifier...")
        metrics = train_fraud_classifier(
            X,
            y,
            experiment_name=args.experiment_name,
            run_name=args.run_name,
        )
        print(metrics)

        print("Computing risk scores...")
        model, threshold = load_fraud_classifier()
        risk_scores = compute_transaction_risk_score(X)
        print(
            "Risk score summary: "
            f"mean={risk_scores.mean():.2f}, "
            f"min={risk_scores.min():.2f}, "
            f"max={risk_scores.max():.2f}"
        )
        print(f"Loaded deployment threshold: {threshold:.4f}")

        pct_high, pct_medium, pct_low = _risk_level_percentages(risk_scores)
        save_risk_scorer_metadata(
            {
                "computed_at": datetime.now(timezone.utc).isoformat(),
                "total_scored": int(len(risk_scores)),
                "mean_score": float(risk_scores.mean()),
                "pct_high_risk": pct_high,
                "pct_medium_risk": pct_medium,
                "pct_low_risk": pct_low,
            }
        )

        print("Running evaluation...")
        evaluation_metrics = run_evaluation(metrics)
        print_evaluation_summary(evaluation_metrics)
        save_evaluation_report(evaluation_metrics, EVALUATION_REPORT_PATH)

        print("✅ Training complete.")
        print("Model artifacts saved to ml/artifacts/")
        print("MLflow UI: run 'mlflow ui' in the ml/ directory")
        return 0
    except Exception as exc:
        print(f"Training pipeline failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
