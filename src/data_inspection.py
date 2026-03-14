from pathlib import Path
from typing import Dict

import pandas as pd

from data_loading import download_goodreads_dataset, load_raw_tables


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSPECTION_REPORT = PROJECT_ROOT / "results" / "data_inspection_report.txt"


def summarize_table(name: str, df: pd.DataFrame) -> str:
    """
    Build a human-readable summary for a single DataFrame, including:
    - shape
    - column names and dtypes
    - a small head() sample
    """
    lines: list[str] = []
    lines.append(f"=== TABLE: {name} ===")
    lines.append(f"Shape: {df.shape[0]} rows × {df.shape[1]} columns")
    lines.append("\nColumns and dtypes:")
    lines.append(df.dtypes.to_string())
    lines.append("\nSample rows (head):")
    lines.append(df.head(5).to_string())
    lines.append("\n\n")
    return "\n".join(lines)


def run_inspection() -> None:
    """
    Perform initial inspection of the Goodreads dataset:
    - load all tables
    - write a text report summarizing structure and key columns
    """
    dataset_path = download_goodreads_dataset()
    tables: Dict[str, pd.DataFrame] = load_raw_tables(dataset_path)

    INSPECTION_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with INSPECTION_REPORT.open("w", encoding="utf-8") as f:
        f.write("Goodreads Books 100K - Data Inspection Report\n\n")
        f.write(f"Dataset path: {dataset_path}\n")
        f.write(f"Discovered tables: {list(tables.keys())}\n\n")

        for name, df in tables.items():
            summary = summarize_table(name, df)
            f.write(summary)


if __name__ == "__main__":
    # Running this script will generate a text report under results/.
    run_inspection()

