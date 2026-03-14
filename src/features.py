from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FEATURES_DIR = PROJECT_ROOT / "data" / "features"
SPLITS_DIR = PROJECT_ROOT / "data" / "splits"


def load_clean_books() -> pd.DataFrame:
    """
    Load the cleaned book-level table produced in Stage 1.
    """
    path = PROCESSED_DIR / "books_clean.csv"
    return pd.read_csv(path)


def extract_primary_genre(genre_str: str) -> str:
    """
    Extract a primary genre label from the raw 'genre' string.

    The dataset stores multiple comma-separated genres in a single string.
    For interpretability and a compact feature space, we use the first
    non-empty genre as the primary label.
    """
    if not isinstance(genre_str, str):
        return "Unknown"
    parts = [g.strip() for g in genre_str.split(",") if g.strip()]
    if not parts:
        return "Unknown"
    return parts[0]


def split_genres(genre_str: str) -> list[str]:
    """
    Split the raw 'genre' string into a list of cleaned genre tokens.

    The dataset stores multiple comma-separated genres in a single string.
    This helper normalises whitespace and drops empty entries.
    """
    if not isinstance(genre_str, str):
        return []
    return [g.strip() for g in genre_str.split(",") if g.strip()]


def build_book_features(books: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Construct an interpretable feature matrix for books and the corresponding
    supervised target (book rating).

    Features include:
    - primary_genre one-hot indicators for the most frequent genres
    - bookformat one-hot indicators
    - pages (numeric)
    - ratings_count (from totalratings)
    - log_ratings_count
    - reviews
    """
    df = books.copy()

    # Target variable: observed average rating of the book
    target = df["rating"].astype(float)

    # Start from an empty feature frame indexed like the books table
    features = pd.DataFrame(index=df.index)

    # Genre features: primary genre (for imputation) and multi-hot indicators
    # based on all listed genres.
    if "genre" in df.columns:
        df["primary_genre"] = df["genre"].apply(extract_primary_genre)
        df["genre_list"] = df["genre"].apply(split_genres)

        # Count individual genre token frequencies across all books
        exploded = df["genre_list"].explode()
        genre_counts = exploded.value_counts()

        # Keep a manageable number of genre indicators (e.g., top 50)
        top_genres = genre_counts.head(50).index.tolist()

        for g in top_genres:
            col_name = f"genre_{g.replace(' ', '_')}"
            features[col_name] = df["genre_list"].apply(lambda lst: int(g in lst))

    # Basic numeric features
    # Pages: median-by-genre imputation and capping at 2000
    if "pages" in df.columns:
        pages = pd.to_numeric(df["pages"], errors="coerce")
        pages[pages == 0] = np.nan
        if "primary_genre" in df.columns:
            genre_medians = (
                pages.groupby(df["primary_genre"])
                .transform("median")
            )
            pages = pages.fillna(genre_medians)
        global_median = pages.median()
        pages = pages.fillna(global_median)
        pages = pages.clip(upper=2000)
        features["pages"] = pages

    if "totalratings" in df.columns:
        features["ratings_count"] = pd.to_numeric(df["totalratings"], errors="coerce").fillna(0)
        features["log_ratings_count"] = np.log1p(features["ratings_count"])

    if "reviews" in df.columns:
        features["reviews"] = pd.to_numeric(df["reviews"], errors="coerce").fillna(0)

    # Book format one-hot encoding (e.g., Hardcover, Paperback)
    if "bookformat" in df.columns:
        format_dummies = pd.get_dummies(df["bookformat"], prefix="format", dummy_na=False)
        features = pd.concat([features, format_dummies], axis=1)

    # Drop any columns that are entirely NaN to keep the matrix clean
    features = features.dropna(axis=1, how="all")

    return features, target


def create_splits(
    features: pd.DataFrame,
    target: pd.Series,
    val_fraction: float = 0.15,
    test_fraction: float = 0.15,
    random_state: int = 42,
) -> None:
    """
    Split the data into train, validation, and test sets and save them to disk.

    The splits are stratified only by random state (no special temporal logic),
    which is reasonable here because rows correspond to books, not time series.
    """
    SPLITS_DIR.mkdir(parents=True, exist_ok=True)

    # First, split off the test set
    test_size = test_fraction
    X_temp, X_test, y_temp, y_test = train_test_split(
        features,
        target,
        test_size=test_size,
        random_state=random_state,
    )

    # Then split the remaining into train and validation
    remaining_fraction = 1.0 - test_fraction
    val_size_relative = val_fraction / remaining_fraction

    X_train, X_val, y_train, y_val = train_test_split(
        X_temp,
        y_temp,
        test_size=val_size_relative,
        random_state=random_state,
    )

    # Save splits as CSV with both features and target
    train_df = X_train.copy()
    train_df["rating"] = y_train
    val_df = X_val.copy()
    val_df["rating"] = y_val
    test_df = X_test.copy()
    test_df["rating"] = y_test

    train_df.to_csv(SPLITS_DIR / "train.csv", index=False)
    val_df.to_csv(SPLITS_DIR / "val.csv", index=False)
    test_df.to_csv(SPLITS_DIR / "test.csv", index=False)


def main() -> None:
    """
    Stage 2 orchestration:
    - load cleaned book data
    - build interpretable book features
    - save book feature matrix
    - create train/validation/test splits for modeling
    """
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)

    books = load_clean_books()
    features, target = build_book_features(books)

    # Save the full feature matrix for reference
    features_with_target = features.copy()
    features_with_target["rating"] = target
    features_with_target.to_csv(FEATURES_DIR / "book_features.csv", index=False)

    # Create and save dataset splits
    create_splits(features, target)


if __name__ == "__main__":
    main()

