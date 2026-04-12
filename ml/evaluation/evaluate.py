import json
from pathlib import Path

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
EVALUATION_REPORT_PATH = ARTIFACTS_DIR / "evaluation_report.json"


def run_evaluation(metrics: dict) -> dict:
    return metrics


def print_evaluation_summary(metrics: dict):
    print("============================================")
    print("  ARIA Fraud Classifier - Evaluation Report")
    print("============================================")
    print(f"  Samples:              {metrics['n_samples']:,}")
    print(
        f"  Fraud cases:          {metrics['n_fraud_cases']:,}  "
        f"({metrics['fraud_rate'] * 100:.2f}%)"
    )
    print(f"  CV Folds:             {metrics['n_folds']}")
    print("")
    print("  Cross-Validation Results (mean ± std):")
    print(
        f"  F1 Score:       {metrics['cv_f1_mean']:.2f} ± {metrics['cv_f1_std']:.2f}"
    )
    print(
        f"  Precision:      {metrics['cv_precision_mean']:.2f} ± {metrics['cv_precision_std']:.2f}"
    )
    print(
        f"  Recall:         {metrics['cv_recall_mean']:.2f} ± {metrics['cv_recall_std']:.2f}"
    )
    print(
        f"  ROC-AUC:        {metrics['cv_roc_auc_mean']:.2f} ± {metrics['cv_roc_auc_std']:.2f}"
    )
    print("============================================")


def save_evaluation_report(metrics, path):
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)


if __name__ == "__main__":
    with EVALUATION_REPORT_PATH.open("r", encoding="utf-8") as handle:
        metrics = json.load(handle)
    print_evaluation_summary(metrics)
