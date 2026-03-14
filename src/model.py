from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPLITS_DIR = PROJECT_ROOT / "data" / "splits"
MODELS_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "results"


def _load_split(name: str) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Load a split CSV and return (X, y) where y is the rating column.
    """
    path = SPLITS_DIR / f"{name}.csv"
    df = pd.read_csv(path)
    if "rating" not in df.columns:
        raise ValueError(f"'rating' column not found in {path}")
    y = df["rating"].astype(float)
    X = df.drop(columns=["rating"])
    return X, y


def load_dataset_splits() -> Tuple[Tuple[pd.DataFrame, pd.Series], Tuple[pd.DataFrame, pd.Series], Tuple[pd.DataFrame, pd.Series]]:
    """
    Convenience wrapper to load train, validation, and test splits.
    """
    X_train, y_train = _load_split("train")
    X_val, y_val = _load_split("val")
    X_test, y_test = _load_split("test")
    return (X_train, y_train), (X_val, y_val), (X_test, y_test)


@dataclass
class Metrics:
    rmse: float
    mae: float
    r2: float


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Metrics:
    """
    Compute RMSE, MAE, and R² for regression predictions.
    """
    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    return Metrics(rmse=rmse, mae=mae, r2=r2)


def baseline_global_mean(y_train: pd.Series, X_eval: pd.DataFrame, y_eval: pd.Series) -> Metrics:
    """
    Baseline model: always predict the global mean rating from the training set.
    """
    mean_rating = float(y_train.mean())
    y_pred = np.full(shape=len(X_eval), fill_value=mean_rating, dtype=float)
    return compute_metrics(y_eval.values, y_pred)


def train_xgb_regressor(X_train: pd.DataFrame, y_train: pd.Series, X_val: pd.DataFrame, y_val: pd.Series) -> Tuple[XGBRegressor, Metrics]:
    """
    Train an XGBoost regressor with a small, sensible configuration and
    evaluate it on the validation set.
    """
    model = XGBRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        objective="reg:squarederror",
        tree_method="hist",
        random_state=42,
        n_jobs=-1,
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    y_val_pred = model.predict(X_val)
    val_metrics = compute_metrics(y_val.values, y_val_pred)
    return model, val_metrics


def tune_simple_xgb(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> Tuple[XGBRegressor, Metrics, Dict[str, float]]:
    """
    Very small manual hyperparameter search over a few candidate settings.
    This keeps tuning lightweight while still exploring a couple of choices.
    """
    candidates = [
        {"max_depth": 4, "learning_rate": 0.1, "n_estimators": 300},
        {"max_depth": 6, "learning_rate": 0.05, "n_estimators": 500},
        {"max_depth": 8, "learning_rate": 0.05, "n_estimators": 700},
    ]

    best_model: XGBRegressor | None = None
    best_metrics: Metrics | None = None
    best_params: Dict[str, float] | None = None

    for params in candidates:
        model = XGBRegressor(
            n_estimators=params["n_estimators"],
            learning_rate=params["learning_rate"],
            max_depth=params["max_depth"],
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            objective="reg:squarederror",
            tree_method="hist",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        y_val_pred = model.predict(X_val)
        metrics = compute_metrics(y_val.values, y_val_pred)

        if best_metrics is None or metrics.rmse < best_metrics.rmse:
            best_model = model
            best_metrics = metrics
            best_params = params

    assert best_model is not None and best_metrics is not None and best_params is not None
    return best_model, best_metrics, best_params


def run_full_experiment() -> None:
    """
    Stage 3 orchestration:
    - load dataset splits
    - compute baseline metrics
    - train initial XGBoost model
    - perform lightweight hyperparameter tuning
    - evaluate best model on the test set
    - save model and metrics to disk
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    (X_train, y_train), (X_val, y_val), (X_test, y_test) = load_dataset_splits()

    # Baseline on validation set
    baseline_metrics = baseline_global_mean(y_train, X_val, y_val)

    # Initial XGBoost model on validation
    initial_model, initial_val_metrics = train_xgb_regressor(X_train, y_train, X_val, y_val)

    # Lightweight hyperparameter tuning
    tuned_model, tuned_val_metrics, tuned_params = tune_simple_xgb(X_train, y_train, X_val, y_val)

    # Final evaluation on the held-out test set using the tuned model
    y_test_pred = tuned_model.predict(X_test)
    test_metrics = compute_metrics(y_test.values, y_test_pred)

    # Save tuned model
    model_path = MODELS_DIR / "xgb_tuned.joblib"
    joblib.dump(tuned_model, model_path)

    # Write a concise results report
    report_path = RESULTS_DIR / "model_evaluation.md"
    with report_path.open("w", encoding="utf-8") as f:
        f.write("# Model Evaluation\n\n")
        f.write("## Baseline (global mean) — validation set\n\n")
        f.write(f"- RMSE: {baseline_metrics.rmse:.4f}\n")
        f.write(f"- MAE:  {baseline_metrics.mae:.4f}\n")
        f.write(f"- R²:   {baseline_metrics.r2:.4f}\n\n")

        f.write("## Initial XGBoost model — validation set\n\n")
        f.write(f"- RMSE: {initial_val_metrics.rmse:.4f}\n")
        f.write(f"- MAE:  {initial_val_metrics.mae:.4f}\n")
        f.write(f"- R²:   {initial_val_metrics.r2:.4f}\n\n")

        f.write("## Tuned XGBoost model — validation set\n\n")
        f.write(f"- RMSE: {tuned_val_metrics.rmse:.4f}\n")
        f.write(f"- MAE:  {tuned_val_metrics.mae:.4f}\n")
        f.write(f"- R²:   {tuned_val_metrics.r2:.4f}\n\n")

        f.write("Best tuned hyperparameters:\n\n")
        for k, v in tuned_params.items():
            f.write(f"- {k}: {v}\n")

        f.write("\n## Tuned XGBoost model — test set\n\n")
        f.write(f"- RMSE: {test_metrics.rmse:.4f}\n")
        f.write(f"- MAE:  {test_metrics.mae:.4f}\n")
        f.write(f"- R²:   {test_metrics.r2:.4f}\n")


if __name__ == "__main__":
    run_full_experiment()

