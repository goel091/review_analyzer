"""
storage.py

Handles saving and loading results in both JSON and CSV formats.
Uses Pandas for the CSV output to keep things clean and inspectable.
"""

import json
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


def _flatten_for_csv(record: dict) -> dict:
    """
    Flatten a review record so it can be stored in a flat CSV row.

    Lists (pros, cons, chunks) are joined with a pipe delimiter.
    """
    flat = {
        "author": record.get("author", ""),
        "rating": record.get("rating"),
        "date": record.get("date", ""),
        "title": record.get("title", ""),
        "body": record.get("body", ""),
        "token_count": record.get("token_count"),
        "llm_sentiment": record.get("llm_sentiment", ""),
        "llm_score": record.get("llm_score"),
        "llm_summary": record.get("llm_summary", ""),
        "llm_pros": " | ".join(record.get("llm_pros") or []),
        "llm_cons": " | ".join(record.get("llm_cons") or []),
    }
    return flat


def save_json(records: list[dict], output_path: str) -> None:
    """Save the full records list (including nested fields) as pretty-printed JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Remove internal fields not useful to the end user
    clean_records = []
    for r in records:
        clean = {k: v for k, v in r.items() if k not in ("chunks", "full_text")}
        clean_records.append(clean)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean_records, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(records)} records to {path}")


def save_csv(records: list[dict], output_path: str) -> None:
    """Save a flattened version of the records as a CSV file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = [_flatten_for_csv(r) for r in records]
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding="utf-8-sig")  # utf-8-sig for Excel compatibility

    logger.info(f"Saved CSV with {len(df)} rows to {path}")


def load_json(input_path: str) -> list[dict]:
    """Load previously saved JSON results."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} records from {input_path}")
    return data


def to_dataframe(records: list[dict]) -> pd.DataFrame:
    """Convert records to a Pandas DataFrame (flattened view)."""
    rows = [_flatten_for_csv(r) for r in records]
    return pd.DataFrame(rows)
