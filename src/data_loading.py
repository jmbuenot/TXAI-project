import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple

import kagglehub
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"


def download_goodreads_dataset() -> Path:
    """
    Download the Goodreads Books 100K dataset using kagglehub (if not already downloaded)
    and return the local path where kagglehub stored the files.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # kagglehub manages its own cache; this call is idempotent
    path = kagglehub.dataset_download("mdhamani/goodreads-books-100k")

    # Record where and when the dataset was obtained for reproducibility
    metadata_path = RAW_DIR / "download_metadata.txt"
    with metadata_path.open("a", encoding="utf-8") as f:
        f.write(
            f"Downloaded via kagglehub from mdhamani/goodreads-books-100k at "
            f"{datetime.utcnow().isoformat()} UTC\n"
        )
        f.write(f"kagglehub path: {path}\n\n")

    return Path(path)


def _discover_csv_files(dataset_path: Path) -> Dict[str, Path]:
    """
    Discover CSV files in the kagglehub dataset directory and return a mapping
    from file stem (name without extension) to full path.
    """
    csv_files: Dict[str, Path] = {}
    for root, _dirs, files in os.walk(dataset_path):
        for name in files:
            if name.lower().endswith(".csv"):
                full_path = Path(root) / name
                csv_files[full_path.stem] = full_path
    return csv_files


def load_raw_tables(dataset_path: Path | None = None) -> Dict[str, pd.DataFrame]:
    """
    Load all CSV files from the Goodreads dataset into pandas DataFrames.

    Returns a dictionary keyed by table name (file stem).
    """
    if dataset_path is None:
        dataset_path = download_goodreads_dataset()

    csv_files = _discover_csv_files(dataset_path)
    tables: Dict[str, pd.DataFrame] = {}

    for name, path in csv_files.items():
        df = pd.read_csv(path)
        tables[name] = df

    return tables


def clean_and_save_core_tables(
    tables: Dict[str, pd.DataFrame],
    ratings_key: str = "ratings",
    books_key: str = "books",
) -> Tuple[pd.DataFrame | None, pd.DataFrame]:
    """
    Perform basic cleaning on the core ratings and books tables and save them
    into data/processed.

    This function assumes that the dataset contains at least:
    - a ratings-like table (user–book–rating)
    - a books-like table (book metadata)

    The exact column names may differ; adjust them here once you inspect the data.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    available_tables = list(tables.keys())

    # Try to locate books and ratings tables by explicit keys; if not found,
    # fall back to the only available table as books metadata.
    has_ratings = ratings_key in tables
    has_books = books_key in tables

    if not has_books:
        # Fallback: if there is exactly one table, treat it as books metadata.
        if len(available_tables) == 1:
            books_table_name = available_tables[0]
        else:
            raise KeyError(
                f"Could not locate a books table named '{books_key}' and there are "
                f"multiple tables available: {available_tables}. Please update "
                f"clean_and_save_core_tables with the correct table names."
            )
    else:
        books_table_name = books_key

    books = tables[books_table_name].copy()

    ratings = None
    if has_ratings:
        ratings = tables[ratings_key].copy()
        ratings = ratings.drop_duplicates()
        ratings = ratings.dropna()

        if "rating" in ratings.columns:
            ratings["rating"] = pd.to_numeric(ratings["rating"], errors="coerce")
            ratings = ratings.dropna(subset=["rating"])

    # Basic cleaning for books
    books = books.drop_duplicates()
    books = books.dropna(
        subset=[col for col in books.columns if col.lower() in {"title", "book_id", "id"}]
    )

    for col in ["title", "authors", "genres"]:
        if col in books.columns:
            books[col] = books[col].astype(str).str.strip()

    ratings_path = PROCESSED_DIR / "ratings_clean.csv"
    books_path = PROCESSED_DIR / "books_clean.csv"

    if ratings is not None:
        ratings.to_csv(ratings_path, index=False)
    books.to_csv(books_path, index=False)

    report_path = PROCESSED_DIR / "cleaning_report.txt"
    with report_path.open("w", encoding="utf-8") as f:
        f.write("Goodreads Books 100K - Cleaning Report\n")
        f.write(f"Generated at {datetime.utcnow().isoformat()} UTC\n\n")
        f.write(f"Available raw tables: {available_tables}\n")
        if ratings is not None:
            f.write(f"Ratings table name: {ratings_key}\n")
            f.write(f"Ratings shape after cleaning: {ratings.shape}\n")
        else:
            f.write(
                "No explicit ratings table was found. Only book-level metadata "
                "is available in this dataset, so user–book ratings are not "
                "yet represented as a separate table.\n"
            )
        f.write(f"Books table name: {books_table_name}\n")
        f.write(f"Books shape after cleaning: {books.shape}\n")

    return ratings, books


if __name__ == "__main__":
    """
    Example end-to-end run for Stage 1:
    - Download dataset
    - Load raw tables
    - Clean and save core tables
    """
    dataset_path = download_goodreads_dataset()
    raw_tables = load_raw_tables(dataset_path)
    clean_and_save_core_tables(raw_tables)

