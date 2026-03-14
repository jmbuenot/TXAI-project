from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RESULTS_DIR = PROJECT_ROOT / "results"


def load_clean_data() -> tuple[pd.DataFrame | None, pd.DataFrame]:
    """
    Load the cleaned ratings and books tables produced by data_loading.clean_and_save_core_tables.
    If a ratings table is not available, returns (None, books).
    """
    books_path = PROCESSED_DIR / "books_clean.csv"
    ratings_path = PROCESSED_DIR / "ratings_clean.csv"

    books = pd.read_csv(books_path)

    ratings: pd.DataFrame | None
    if ratings_path.exists():
        ratings = pd.read_csv(ratings_path)
    else:
        ratings = None

    return ratings, books


def plot_rating_distribution(ratings: pd.DataFrame | None, books: pd.DataFrame) -> None:
    """
    Plot and save the overall distribution of ratings.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    source_df = ratings if ratings is not None and "rating" in ratings.columns else books

    if "rating" not in source_df.columns:
        return

    plt.figure(figsize=(6, 4))
    sns.histplot(source_df["rating"], bins=10, kde=False)
    plt.title("Distribution of Ratings")
    plt.xlabel("Rating")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "rating_distribution.png")
    plt.close()


def plot_long_tail(ratings: pd.DataFrame | None, books: pd.DataFrame) -> None:
    """
    Plot and save long-tail distributions:
    - number of ratings per user
    - number of ratings per book
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if ratings is not None and "user_id" in ratings.columns:
        counts_per_user = ratings.groupby("user_id")["rating"].count()
        plt.figure(figsize=(6, 4))
        sns.histplot(counts_per_user, bins=50)
        plt.xscale("log")
        plt.title("Ratings per User (log scale)")
        plt.xlabel("Ratings per user")
        plt.ylabel("Count of users")
        plt.tight_layout()
        plt.savefig(RESULTS_DIR / "ratings_per_user.png")
        plt.close()

    if "book_id" in books.columns:
        # With only book-level data, we can approximate "ratings per book"
        # using the total ratings count column if it exists.
        if "totalratings" in books.columns:
            counts_per_book = books["totalratings"]
        else:
            return
        plt.figure(figsize=(6, 4))
        sns.histplot(counts_per_book, bins=50)
        plt.xscale("log")
        plt.title("Ratings per Book (log scale)")
        plt.xlabel("Ratings per book")
        plt.ylabel("Count of books")
        plt.tight_layout()
        plt.savefig(RESULTS_DIR / "ratings_per_book.png")
        plt.close()


def compute_basic_statistics(ratings: pd.DataFrame | None, books: pd.DataFrame) -> None:
    """
    Compute and save basic descriptive statistics for later reference.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stats_path = RESULTS_DIR / "eda_summary.txt"

    num_users = None
    num_books = books.shape[0]

    if ratings is not None and "user_id" in ratings.columns:
        num_users = ratings["user_id"].nunique()

    if ratings is not None:
        num_ratings = len(ratings)
    elif "totalratings" in books.columns:
        num_ratings = int(books["totalratings"].sum())
    else:
        num_ratings = None

    max_possible_pairs = None
    sparsity = None
    if num_users is not None and num_books is not None and num_ratings is not None:
        max_possible_pairs = num_users * num_books
        if max_possible_pairs > 0:
            sparsity = 1.0 - (num_ratings / max_possible_pairs)

    with stats_path.open("w", encoding="utf-8") as f:
        f.write("Goodreads Books 100K - EDA Summary\n\n")
        f.write(f"Number of ratings: {num_ratings}\n")
        f.write(f"Number of unique users: {num_users}\n")
        f.write(f"Number of unique books: {num_books}\n")
        f.write(f"Max possible user–book pairs: {max_possible_pairs}\n")
        f.write(f"Approximate matrix sparsity: {sparsity}\n")


def plot_pages_histogram(books: pd.DataFrame) -> None:
    """
    Plot and save the distribution of raw pages values (before feature engineering).
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if "pages" not in books.columns:
        return

    pages = pd.to_numeric(books["pages"], errors="coerce")

    plt.figure(figsize=(6, 4))
    sns.histplot(pages, bins=50)
    plt.title("Distribution of Pages (raw)")
    plt.xlabel("Pages")
    plt.ylabel("Count of books")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "pages_distribution_raw.png")
    plt.close()


def main() -> None:
    """
    Run the full EDA pipeline for Stage 1:
    - load cleaned data
    - plot rating distributions and long-tail effects
    - compute basic statistics
    """
    ratings, books = load_clean_data()
    plot_rating_distribution(ratings, books)
    plot_long_tail(ratings, books)
    compute_basic_statistics(ratings, books)
    plot_pages_histogram(books)


if __name__ == "__main__":
    main()

