from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from features import split_genres, extract_primary_genre
from synthetic_users import SyntheticUser, predefined_synthetic_users


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FEATURES_DIR = PROJECT_ROOT / "data" / "features"
MODELS_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "results"


def load_books_and_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load the cleaned books table and the engineered feature matrix.

    Assumes that `book_features.csv` was built from `books_clean.csv` in the
    same row order, so indices are aligned.
    """
    books_path = PROCESSED_DIR / "books_clean.csv"
    features_path = FEATURES_DIR / "book_features.csv"

    books = pd.read_csv(books_path)
    features = pd.read_csv(features_path)

    if len(books) != len(features):
        raise ValueError(
            f"books_clean ({len(books)}) and book_features ({len(features)}) "
            "have different lengths; they are expected to be row-aligned."
        )

    return books, features


def load_trained_model():
    """
    Load the tuned XGBoost model saved in Stage 3.
    """
    model_path = MODELS_DIR / "xgb_tuned.joblib"
    if not model_path.exists():
        raise FileNotFoundError(
            f"Trained model not found at {model_path}. "
            "Run src/model.py first to train and save the model."
        )
    return joblib.load(model_path)


def score_all_books() -> pd.DataFrame:
    """
    Use the trained model to predict ratings for all books in the dataset.

    Returns a DataFrame with the original book metadata plus a
    `predicted_rating` column.
    """
    books, features = load_books_and_features()
    # book_features.csv contains the engineered features and the target rating
    # as the last column. We drop the true rating to obtain X.
    if "rating" not in features.columns:
        raise ValueError(
            "Expected 'rating' column in book_features.csv. "
            "Ensure features.main() saved features_with_target correctly."
        )

    X = features.drop(columns=["rating"])
    model = load_trained_model()
    preds = model.predict(X)

    scored = books.copy()
    scored["predicted_rating"] = preds

    # Convenience columns for analysis
    if "genre" in scored.columns:
        scored["primary_genre"] = scored["genre"].apply(extract_primary_genre)
        scored["genre_list"] = scored["genre"].apply(split_genres)

    return scored


def compute_genre_match(genre_list, genre_weights: dict[str, float]) -> float:
    """
    Compute a simple genre-match score between a book's genres and a
    synthetic user's genre preferences.
    """
    if not isinstance(genre_list, list):
        return 0.0
    score = 0.0
    for g in genre_list:
        score += genre_weights.get(g, 0.0)
    return score


def apply_length_preference(pages: float | int | None, length_preference: str) -> float:
    """
    Compute a small adjustment based on the user's length preference.
    """
    if pages is None:
        return 0.0
    try:
        pages_val = float(pages)
    except (TypeError, ValueError):
        return 0.0

    if length_preference == "short":
        # Prefer books shorter than ~350 pages.
        if pages_val < 250:
            return 0.3
        if pages_val < 400:
            return 0.1
        if pages_val > 600:
            return -0.2
    elif length_preference == "long":
        # Prefer books longer than ~350 pages.
        if pages_val > 600:
            return 0.3
        if pages_val > 350:
            return 0.1
        if pages_val < 200:
            return -0.2

    return 0.0


def generate_personalised_recommendations(
    scored_books: pd.DataFrame,
    user: SyntheticUser,
    top_n: int = 10,
    alpha_genre: float = 0.3,
    alpha_length: float = 0.1,
) -> pd.DataFrame:
    """
    Generate a personalised top-N list for a synthetic user by re-ranking
    globally scored books using their genre and length preferences.
    """
    df = scored_books.copy()

    if "genre_list" not in df.columns:
        df["genre_list"] = df["genre"].apply(split_genres) if "genre" in df.columns else [[] for _ in range(len(df))]

    # Compute preference-based adjustments
    df["genre_match"] = df["genre_list"].apply(lambda gl: compute_genre_match(gl, user.genre_weights))
    df["length_adjustment"] = df["pages"].apply(lambda p: apply_length_preference(p, user.length_preference) if "pages" in df.columns else 0.0)

    df["personalised_score"] = (
        df["predicted_rating"]
        + alpha_genre * df["genre_match"]
        + alpha_length * df["length_adjustment"]
    )

    cols_to_keep = [
        "title",
        "author",
        "rating",
        "predicted_rating",
        "personalised_score",
        "genre_match",
        "length_adjustment",
        "totalratings",
        "primary_genre",
        "pages",
        "row_id",
    ]
    available_cols = [c for c in cols_to_keep if c in df.columns]

    df_sorted = df.sort_values("personalised_score", ascending=False)
    top = df_sorted.loc[:, available_cols].head(top_n).copy()
    top.insert(0, "rank", np.arange(1, len(top) + 1))
    return top


def generate_global_recommendations(scored_books: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """
    Generate a global top-N list of books ranked by predicted rating.

    Since the current dataset lacks user-level interactions, this acts as a
    non-personalised recommender: the same top-N list is recommended to
    any user.
    """
    cols_to_keep = [
        "title",
        "author",
        "rating",
        "predicted_rating",
        "totalratings",
        "primary_genre",
        "pages",
    ]
    available_cols = [c for c in cols_to_keep if c in scored_books.columns]

    top = (
        scored_books
        .sort_values("predicted_rating", ascending=False)
        .reset_index(drop=True)
        .loc[:, available_cols]
        .head(top_n)
    )
    top.insert(0, "rank", np.arange(1, len(top) + 1))
    return top


def recommendation_quality_checks(scored_books: pd.DataFrame, top: pd.DataFrame) -> None:
    """
    Perform simple sanity and diversity checks on the global recommendations and
    write a short markdown summary to results/recommendation_quality.md.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / "recommendation_quality.md"

    # Correlation between predicted rating and popularity / true rating
    corr_pred_true = float(
        scored_books["predicted_rating"].corr(scored_books["rating"])
        if "rating" in scored_books.columns
        else np.nan
    )
    corr_pred_pop = float(
        scored_books["predicted_rating"].corr(scored_books["totalratings"])
        if "totalratings" in scored_books.columns
        else np.nan
    )

    # Genre diversity in top-N list
    genre_counts = (
        top["primary_genre"].value_counts()
        if "primary_genre" in top.columns
        else pd.Series(dtype=int)
    )
    top_genre = genre_counts.index[0] if len(genre_counts) > 0 else None
    top_genre_share = (
        float(genre_counts.iloc[0] / genre_counts.sum())
        if len(genre_counts) > 0
        else np.nan
    )

    # Popularity comparison: top-N vs overall
    mean_totalratings_all = float(scored_books["totalratings"].mean()) if "totalratings" in scored_books.columns else np.nan
    mean_totalratings_top = float(top["totalratings"].mean()) if "totalratings" in top.columns else np.nan

    with report_path.open("w", encoding="utf-8") as f:
        f.write("# Recommendation Quality Checks\n\n")
        f.write("## Correlations\n\n")
        f.write(f"- Correlation between predicted rating and true rating: {corr_pred_true:.4f}\n")
        f.write(f"- Correlation between predicted rating and popularity (`totalratings`): {corr_pred_pop:.4f}\n\n")

        f.write("## Genre diversity in top-N list\n\n")
        if len(genre_counts) > 0:
            f.write("Primary-genre distribution among top-N recommendations:\n\n")
            for genre, count in genre_counts.items():
                f.write(f"- {genre}: {count}\n")
            f.write("\n")
            f.write(f"Most frequent primary genre in top-N: {top_genre} "
                    f"({top_genre_share * 100:.1f}% of top-N)\n\n")
        else:
            f.write("Primary-genre information not available for the top-N list.\n\n")

        f.write("## Popularity bias\n\n")
        f.write(
            "Comparison of mean `totalratings` (a proxy for popularity) for "
            "all books vs. only the top-N recommended books:\n\n"
        )
        f.write(f"- Mean `totalratings` for all books: {mean_totalratings_all:.2f}\n")
        f.write(f"- Mean `totalratings` for top-N books: {mean_totalratings_top:.2f}\n")


def main(top_n: int = 20) -> None:
    """
    Stage 4 orchestration:
    - score all books with the trained model
    - generate a global top-N recommendation list
    - run simple quality checks on the recommendations
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    scored_books = score_all_books()

    # Global (non-personalised) recommendations
    global_top = generate_global_recommendations(scored_books, top_n=top_n)
    sample_path = RESULTS_DIR / "sample_recommendations.csv"
    global_top.to_csv(sample_path, index=False)
    recommendation_quality_checks(scored_books, global_top)

    # Personalised recommendations for predefined synthetic users
    users = predefined_synthetic_users()
    for user_id, user in users.items():
        user_top = generate_personalised_recommendations(scored_books, user, top_n=top_n)
        out_path = RESULTS_DIR / f"personalised_recommendations_{user_id}.csv"
        user_top.to_csv(out_path, index=False)


if __name__ == "__main__":
    main()

