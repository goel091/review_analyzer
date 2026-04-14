"""
main.py

Entry point for the Review Analyzer.

Usage:
    python main.py --url "https://www.bestbuy.com/site/..." [options]

Run `python main.py --help` for full usage.
"""

import argparse
import logging
import sys
import time
import random
from pathlib import Path

from scraper import scrape_reviews
from preprocessor import preprocess_all
from llm_client import analyze_chunked_review
from storage import save_json, save_csv, to_dataframe


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("run.log", encoding="utf-8"),
        ],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape product reviews and analyze them with an LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --url "https://www.bestbuy.com/site/sony-wh-1000xm5/6505727.p"
  python main.py --url "..." --output-dir results/ --verbose
  python main.py --url "..." --delay 2.5 --no-csv
        """,
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Full URL of the product page to scrape.",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to save results (default: ./output/).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Base delay in seconds between LLM API calls (default: 1.0).",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip saving the CSV file (only save JSON).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return parser.parse_args()


def run(url: str, output_dir: str, delay: float, save_csv_output: bool) -> None:
    logger = logging.getLogger(__name__)

    # --- Step 1: Scrape reviews ---
    logger.info(f"Starting scrape: {url}")
    raw_reviews = scrape_reviews(url)

    if not raw_reviews:
        logger.error(
            "No reviews were scraped. The page may require JavaScript rendering "
            "(try Selenium), or the site structure has changed."
        )
        sys.exit(1)

    logger.info(f"Scraped {len(raw_reviews)} raw reviews.")

    # --- Step 2: Preprocess ---
    logger.info("Preprocessing reviews...")
    processed_reviews = preprocess_all(raw_reviews)

    if not processed_reviews:
        logger.error("All reviews were empty after preprocessing. Nothing to analyze.")
        sys.exit(1)

    # --- Step 3: LLM analysis ---
    logger.info(f"Sending {len(processed_reviews)} reviews to LLM for analysis...")
    results = []

    for i, review in enumerate(processed_reviews, start=1):
        logger.info(f"Analyzing review {i}/{len(processed_reviews)} by {review.get('author', 'unknown')}...")

        analysis = analyze_chunked_review(review["chunks"])

        result = {
            **review,
            "llm_sentiment": analysis.get("sentiment"),
            "llm_score": analysis.get("score"),
            "llm_summary": analysis.get("summary"),
            "llm_pros": analysis.get("pros", []),
            "llm_cons": analysis.get("cons", []),
        }
        results.append(result)

        # Polite delay to avoid hammering the API
        if i < len(processed_reviews):
            sleep_time = delay + random.uniform(0.2, 0.8)
            time.sleep(sleep_time)

    # --- Step 4: Save output ---
    output_path = Path(output_dir)
    json_path = output_path / "reviews.json"
    csv_path = output_path / "reviews.csv"

    save_json(results, str(json_path))
    if save_csv_output:
        save_csv(results, str(csv_path))

    # --- Step 5: Print a quick summary to stdout ---
    df = to_dataframe(results)
    print("\n" + "=" * 60)
    print(f"  Analysis complete — {len(results)} reviews processed")
    print("=" * 60)

    sentiment_counts = df["llm_sentiment"].value_counts()
    for sentiment, count in sentiment_counts.items():
        print(f"  {sentiment.capitalize()}: {count}")

    valid_scores = df["llm_score"].dropna()
    if not valid_scores.empty:
        print(f"\n  Avg LLM Score: {valid_scores.mean():.1f} / 5")

    print(f"\n  Output saved to: {output_path.resolve()}/")
    print("=" * 60 + "\n")


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    run(
        url=args.url,
        output_dir=args.output_dir,
        delay=args.delay,
        save_csv_output=not args.no_csv,
    )


if __name__ == "__main__":
    main()
