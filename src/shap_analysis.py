from __future__ import annotations

import re
import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import shap
except (AttributeError, ImportError) as e:
    if "_ARRAY_API" in str(e) or "numpy" in str(e).lower():
        print(
            "SHAP failed to import, often due to NumPy 2.x vs 1.x or OpenCV.\n"
            "Try: pip install \"numpy<2\" then re-run, or use a conda env with numpy<2.",
            file=sys.stderr,
        )
    raise

# XGBoost 3.x stores base_score as e.g. '[3.833711E0]' in the UBJSON dump; SHAP's
# TreeExplainer calls float() on it and fails. Patch the tree module's float so
# that string values in "[...]" form are parsed before conversion.
import shap.explainers._tree as _shap_tree

_orig_float = float

def _safe_float_for_shap(x):
    if isinstance(x, str):
        s = x.strip()
        if s.startswith("[") and s.endswith("]"):
            x = s[1:-1].strip()
    return _orig_float(x)


_shap_tree.float = _safe_float_for_shap

from model import load_dataset_splits, MODELS_DIR, RESULTS_DIR
from recommend import score_all_books, generate_personalised_recommendations
from synthetic_users import predefined_synthetic_users


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
FEATURES_DIR = DATA_DIR / "features"
SHAP_DIR = RESULTS_DIR / "shap"
SHAP_LOCAL_DIR = SHAP_DIR / "local"
SHAP_GLOBAL_DIR = SHAP_DIR / "global"


def _patch_xgb_base_score_for_shap(model):
    """
    Work around SHAP + XGBoost 3.x: XGBoost 3.0+ stores base_score as a string
    like '[3.833711E0]', which SHAP's TreeExplainer cannot parse.
    Patch the booster so SHAP can load the model.
    See: https://github.com/shap/shap/issues/4184
    """
    try:
        booster = model.get_booster()
    except Exception:
        return
    attrs = booster.attributes()
    if "base_score" not in attrs:
        return
    bs = attrs["base_score"]
    if not isinstance(bs, str) or "[" not in bs:
        return
    # Parse "[3.833711E0]" -> 3.833711
    cleaned = re.sub(r"\[|\]", "", bs).strip()
    try:
        value = float(cleaned)
        booster.set_attr(base_score=str(value))
    except (ValueError, TypeError):
        pass


def load_model_and_data():
    """
    Load the tuned XGBoost model and dataset splits.

    If you see NumPy 2.x / cv2 _ARRAY_API errors when importing shap, use an
    environment with numpy<2, e.g.:
        pip install "numpy<2"
    or use a fresh env with compatible versions.
    """
    model_path = MODELS_DIR / "xgb_tuned.joblib"
    if not model_path.exists():
        raise FileNotFoundError(
            f"Trained model not found at {model_path}. "
            "Run src/model.py first to train and save the model."
        )

    model = joblib.load(model_path)
    _patch_xgb_base_score_for_shap(model)
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = load_dataset_splits()
    return model, X_train, X_val, X_test, y_train, y_val, y_test


def compute_shap_values(model, X_background: pd.DataFrame, X_explain: pd.DataFrame) -> np.ndarray:
    """
    Compute SHAP values for a subset of the data using TreeExplainer.
    """
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_explain)
    return np.array(shap_values)


def save_global_plots(X_explain: pd.DataFrame, shap_values: np.ndarray) -> None:
    """
    Generate and save global SHAP plots (beeswarm and bar).
    """
    SHAP_GLOBAL_DIR.mkdir(parents=True, exist_ok=True)

    # Beeswarm plot
    plt.figure(figsize=(10, 6))
    shap.summary_plot(
        shap_values,
        X_explain,
        show=False,
        plot_type="dot",
        max_display=20,
    )
    plt.tight_layout()
    plt.savefig(SHAP_GLOBAL_DIR / "shap_summary_beeswarm.png", dpi=200)
    plt.close()

    # Bar plot of mean |SHAP|
    plt.figure(figsize=(8, 6))
    shap.summary_plot(
        shap_values,
        X_explain,
        show=False,
        plot_type="bar",
        max_display=20,
    )
    plt.tight_layout()
    plt.savefig(SHAP_GLOBAL_DIR / "shap_summary_bar.png", dpi=200)
    plt.close()


def save_local_plots(X_explain: pd.DataFrame, shap_values: np.ndarray, y_pred: np.ndarray) -> None:
    """
    Generate local SHAP waterfall plots for a few high-prediction examples.
    """
    SHAP_LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    # Select a handful of instances with high predicted ratings
    explain_df = X_explain.copy()
    explain_df["predicted_rating"] = y_pred

    top_examples = explain_df.sort_values("predicted_rating", ascending=False).head(5)
    feature_names = X_explain.columns.tolist()

    for idx in top_examples.index:
        x_row = X_explain.loc[idx]
        shap_row = shap_values[list(X_explain.index).index(idx)]

        shap.plots.waterfall(
            shap.Explanation(
                values=shap_row,
                base_values=np.mean(y_pred),
                data=x_row.values,
                feature_names=feature_names,
            ),
            max_display=15,
            show=False,
        )
        plt.tight_layout()
        out_path = SHAP_LOCAL_DIR / f"waterfall_example_{idx}.png"
        plt.savefig(out_path, dpi=200)
        plt.close()


def explain_personalised_user_recommendations(
    model,
    user_id: str,
    top_n: int = 5,
) -> None:
    """
    Generate local SHAP explanations for the top-N personalised
    recommendations of a given synthetic user.

    This aligns with the project scope by explaining *why* specific
    user–book recommendations are made (for simulated user profiles).
    """
    # Load full feature matrix to map books to model inputs
    features_path = FEATURES_DIR / "book_features.csv"
    features_df = pd.read_csv(features_path)
    if "rating" not in features_df.columns:
        raise ValueError("Expected 'rating' column in book_features.csv")
    X_full = features_df.drop(columns=["rating"])

    # Score all books and generate personalised recommendations for the user
    scored_books = score_all_books()
    scored_books["row_id"] = np.arange(len(scored_books))

    users = predefined_synthetic_users()
    if user_id not in users:
        raise ValueError(f"Unknown synthetic user_id '{user_id}'")
    user = users[user_id]

    personalised_top = generate_personalised_recommendations(
        scored_books,
        user,
        top_n=top_n,
    )

    # Extract the corresponding feature rows for the recommended books
    if "row_id" not in personalised_top.columns:
        raise ValueError(
        "Expected 'row_id' column in personalised recommendations. "
        "Ensure recommend.generate_personalised_recommendations preserves it."
        )

    row_ids = personalised_top["row_id"].astype(int).tolist()
    X_explain = X_full.iloc[row_ids]

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_explain)

    # Save a waterfall plot for each recommended book
    SHAP_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    feature_names = X_explain.columns.tolist()

    base_values = model.predict(X_explain).mean()
    for rank, (idx, x_row, shap_row) in enumerate(
        zip(row_ids, X_explain.itertuples(index=False), shap_values),
        start=1,
    ):
        shap.plots.waterfall(
            shap.Explanation(
                values=np.array(shap_row),
                base_values=base_values,
                data=np.array(x_row),
                feature_names=feature_names,
            ),
            max_display=15,
            show=False,
        )
        plt.tight_layout()
        out_path = SHAP_LOCAL_DIR / f"user_{user_id}_rank{rank}_book_{idx}.png"
        plt.savefig(out_path, dpi=200)
        plt.close()


def main() -> None:
    """
    Stage 5 orchestration:
    - load model and data
    - compute SHAP values on a representative subset of the test set
      (global behaviour)
    - generate global SHAP plots
    - generate local SHAP plots for generic high-scoring books
    - generate local SHAP plots for the top-N personalised
      recommendations of a synthetic user (user–book explanations)
    """
    SHAP_DIR.mkdir(parents=True, exist_ok=True)

    model, X_train, _X_val, X_test, _y_train, _y_val, _y_test = load_model_and_data()

    # Use a subset of the test set for global SHAP analysis
    sample_size = min(1000, len(X_test))
    X_explain = X_test.sample(n=sample_size, random_state=42)

    shap_values = compute_shap_values(model, X_train, X_explain)

    # Global plots
    save_global_plots(X_explain, shap_values)

    # Local plots for top-predicted examples within the explained subset
    y_pred = model.predict(X_explain)
    save_local_plots(X_explain, shap_values, y_pred)

    # Explanations for specific (synthetic) user–book recommendations
    explain_personalised_user_recommendations(model, user_id="fantasy_fan", top_n=5)


if __name__ == "__main__":
    main()

