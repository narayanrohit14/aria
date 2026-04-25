from __future__ import annotations

import os
import json
import math
from pathlib import Path
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
import mlflow
import mlflow.xgboost


ML_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = ML_DIR / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "fraud_classifier.pkl"
MLRUNS_DIR = ML_DIR / "mlruns"
FEATURE_IMPORTANCE_PATH = ARTIFACTS_DIR / "feature_importance.png"
THRESHOLD_PATH = ARTIFACTS_DIR / "optimal_threshold.json"
PREDICTION_THRESHOLD = 0.35


def train_fraud_classifier(X, y, experiment_name: str = "fraud-classifier", run_name: str | None = None) -> dict:
    # Lazy imports — only needed during training, not inference
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    X = pd.DataFrame(X).copy()
    y = pd.Series(y).astype(int).copy()
    positive_count = int((y == 1).sum())
    negative_count = int((y == 0).sum())
    raw_weight = negative_count / positive_count if positive_count else 1.0
    scale_pos_weight = math.sqrt(raw_weight)

    params = {
        "n_estimators": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "scale_pos_weight": scale_pos_weight,
        "eval_metric": "aucpr",
        "early_stopping_rounds": 20,
        "random_state": 42,
    }
    n_folds = 5

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    MLRUNS_DIR.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(MLRUNS_DIR.as_uri())
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(params)
        mlflow.log_param("n_samples", len(X))
        mlflow.log_param("n_fraud_cases", positive_count)
        mlflow.log_param("n_folds", n_folds)
        mlflow.log_param("prediction_threshold", PREDICTION_THRESHOLD)
        fold_metrics = {
            "f1": [],
            "precision": [],
            "recall": [],
            "roc_auc": [],
        }
        fold_thresholds = []
        skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

        for train_idx, test_idx in skf.split(X, y):
            X_train = X.iloc[train_idx]
            y_train = y.iloc[train_idx]
            X_test = X.iloc[test_idx]
            y_test = y.iloc[test_idx]

            fold_positive_count = int((y_train == 1).sum())
            fold_negative_count = int((y_train == 0).sum())
            fold_raw_weight = fold_negative_count / fold_positive_count if fold_positive_count else 1.0
            fold_scale_pos_weight = math.sqrt(fold_raw_weight)

            fold_model = XGBClassifier(
                **{
                    **params,
                    "scale_pos_weight": fold_scale_pos_weight,
                }
            )
            fold_model.fit(
                X_train,
                y_train,
                eval_set=[(X_test, y_test)],
                verbose=False,
            )

            fold_probabilities = fold_model.predict_proba(X_test)[:, 1]
            thresholds = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]
            best_thresh = 0.3
            best_f1 = 0.0
            for threshold in thresholds:
                candidate_predictions = (fold_probabilities >= threshold).astype(int)
                candidate_f1 = f1_score(y_test, candidate_predictions, zero_division=0)
                if candidate_f1 > best_f1:
                    best_f1 = candidate_f1
                    best_thresh = threshold

            fold_thresholds.append(best_thresh)
            fold_predictions = (fold_probabilities >= best_thresh).astype(int)
            fold_metrics["f1"].append(f1_score(y_test, fold_predictions, zero_division=0))
            fold_metrics["precision"].append(
                precision_score(y_test, fold_predictions, zero_division=0)
            )
            fold_metrics["recall"].append(recall_score(y_test, fold_predictions, zero_division=0))
            fold_metrics["roc_auc"].append(roc_auc_score(y_test, fold_probabilities))

        cv_optimal_threshold_mean = float(np.mean(fold_thresholds)) if fold_thresholds else PREDICTION_THRESHOLD

        metrics = {
            "cv_f1_mean": float(np.mean(fold_metrics["f1"])),
            "cv_f1_std": float(np.std(fold_metrics["f1"], ddof=0)),
            "cv_precision_mean": float(np.mean(fold_metrics["precision"])),
            "cv_precision_std": float(np.std(fold_metrics["precision"], ddof=0)),
            "cv_recall_mean": float(np.mean(fold_metrics["recall"])),
            "cv_recall_std": float(np.std(fold_metrics["recall"], ddof=0)),
            "cv_roc_auc_mean": float(np.mean(fold_metrics["roc_auc"])),
            "cv_roc_auc_std": float(np.std(fold_metrics["roc_auc"], ddof=0)),
            "fraud_rate": float(y.mean()),
            "n_samples": int(len(X)),
            "n_fraud_cases": int(positive_count),
            "n_folds": n_folds,
            "cv_optimal_threshold_mean": cv_optimal_threshold_mean,
        }

        mlflow.log_metrics(metrics)
        final_model = XGBClassifier(
            **{
                key: value
                for key, value in params.items()
                if key != "early_stopping_rounds"
            }
        )
        final_model.fit(X, y, verbose=False)
        mlflow.xgboost.log_model(final_model, artifact_path="model")
        importance = pd.Series(
            final_model.feature_importances_,
            index=X.columns,
            name="importance",
        ).sort_values(ascending=False)
        fig, ax = plt.subplots(figsize=(10, 6))
        importance.plot(kind="bar", ax=ax, color="#111827")
        ax.set_title("Fraud Classifier Feature Importance")
        ax.set_xlabel("Feature")
        ax.set_ylabel("Importance")
        fig.tight_layout()
        fig.savefig(FEATURE_IMPORTANCE_PATH, dpi=200)
        plt.close(fig)

        THRESHOLD_PATH.write_text(
            json.dumps(
                {
                    "threshold": round(float(cv_optimal_threshold_mean), 4),
                    "cv_f1_mean": round(float(metrics["cv_f1_mean"]), 4),
                    "tuned_at": datetime.now().isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        mlflow.log_artifact(str(FEATURE_IMPORTANCE_PATH), artifact_path="plots")
        joblib.dump(final_model, MODEL_PATH)
        mlflow.log_artifact(str(MODEL_PATH), artifact_path="artifacts")
        mlflow.log_artifact(str(THRESHOLD_PATH), artifact_path="artifacts")

    return metrics


def load_fraud_classifier() -> tuple[XGBClassifier, float]:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Fraud classifier artifact not found at {MODEL_PATH}. Train the model first."
        )
    model = joblib.load(MODEL_PATH)
    threshold = PREDICTION_THRESHOLD
    if THRESHOLD_PATH.exists():
        threshold = float(json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))["threshold"])
    return model, threshold


def predict_fraud(model, threshold: float, transaction_features: dict) -> dict:
    feature_frame = pd.DataFrame([transaction_features])
    if hasattr(model, "feature_names_in_"):
        missing = [name for name in model.feature_names_in_ if name not in feature_frame.columns]
        if missing:
            raise ValueError(f"Missing required feature(s): {', '.join(missing)}")
        feature_frame = feature_frame.loc[:, model.feature_names_in_]

    fraud_probability = float(model.predict_proba(feature_frame)[0, 1])
    fraud_predicted = fraud_probability >= threshold

    if fraud_probability > 0.75 or fraud_probability < 0.15:
        confidence = "high"
    elif 0.3 <= fraud_probability <= 0.75:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "fraud_probability": fraud_probability,
        "fraud_predicted": bool(fraud_predicted),
        "confidence": confidence,
        "threshold_used": float(threshold),
    }
