"""
llm_client.py

Handles all interactions with the OpenAI-compatible API.
Supports sentiment analysis and summarization with retry logic,
exponential backoff on rate limits, and token-aware chunking.
"""

import os
import time
import logging
from typing import Optional
from openai import OpenAI, RateLimitError, APIConnectionError, APIStatusError

logger = logging.getLogger(__name__)

# Load API key from environment — never hardcoded
_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise EnvironmentError(
        "OPENAI_API_KEY environment variable is not set. "
        "Please export it before running the application."
    )

client = OpenAI(api_key=_api_key)

MODEL = "gpt-3.5-turbo"

SYSTEM_PROMPT = (
    "You are a concise product review analyst. "
    "Given a customer review, return a JSON object with exactly these keys:\n"
    "  - sentiment: one of 'positive', 'negative', or 'mixed'\n"
    "  - score: an integer from 1 (very negative) to 5 (very positive)\n"
    "  - summary: a 1–2 sentence plain-English summary of the review's key points\n"
    "  - pros: a list of up to 3 short bullet points (things the reviewer liked)\n"
    "  - cons: a list of up to 3 short bullet points (things the reviewer disliked)\n\n"
    "Return only valid JSON. No markdown, no extra text."
)


def _call_api(
    user_message: str,
    max_retries: int = 4,
    base_delay: float = 1.5,
) -> Optional[str]:
    """
    Send a message to the API and return the response text.

    Handles:
    - RateLimitError: backs off using the Retry-After header if present
    - APIConnectionError: retries with exponential backoff
    - APIStatusError: retries for 5xx, gives up on 4xx (except 429)
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,  # Lower temperature = more consistent, structured output
                max_tokens=400,
            )
            return response.choices[0].message.content

        except RateLimitError as e:
            # Try to respect the Retry-After header; fall back to exponential backoff
            retry_after = getattr(e, "retry_after", None)
            wait = retry_after if retry_after else base_delay * (2 ** attempt)
            logger.warning(f"Rate limited. Waiting {wait:.1f}s before retry {attempt}/{max_retries}.")
            time.sleep(wait)

        except APIConnectionError as e:
            wait = base_delay * (2 ** attempt)
            logger.warning(f"Connection error (attempt {attempt}): {e}. Retrying in {wait:.1f}s.")
            time.sleep(wait)

        except APIStatusError as e:
            if e.status_code >= 500:
                wait = base_delay * (2 ** attempt)
                logger.warning(f"Server error {e.status_code} (attempt {attempt}). Retrying in {wait:.1f}s.")
                time.sleep(wait)
            else:
                logger.error(f"Client-side API error {e.status_code}: {e.message}. Not retrying.")
                return None

        except Exception as e:
            logger.error(f"Unexpected error during API call: {e}")
            return None

    logger.error(f"Exhausted {max_retries} retries. Returning None.")
    return None


def analyze_review(review_text: str) -> dict:
    """
    Send a single review text to the LLM and parse the structured response.

    Returns a dict with keys: sentiment, score, summary, pros, cons.
    Falls back to a default structure if parsing fails.
    """
    import json

    prompt = f"Review:\n\n{review_text}"
    raw_response = _call_api(prompt)

    if not raw_response:
        return {
            "sentiment": "unknown",
            "score": None,
            "summary": "Analysis unavailable (API error).",
            "pros": [],
            "cons": [],
        }

    try:
        result = json.loads(raw_response)
        # Validate required keys
        for key in ("sentiment", "score", "summary", "pros", "cons"):
            if key not in result:
                result[key] = None
        return result
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON. Storing raw response as summary.")
        return {
            "sentiment": "unknown",
            "score": None,
            "summary": raw_response.strip(),
            "pros": [],
            "cons": [],
        }


def analyze_chunked_review(chunks: list[str]) -> dict:
    """
    For reviews that were split into multiple chunks, analyze each chunk
    and merge the results into a single coherent response.

    Merging strategy:
    - Score: average of all chunk scores (rounded)
    - Sentiment: majority vote; ties go to 'mixed'
    - Summary: combined sentence from all chunk summaries
    - Pros/Cons: union of all chunks (deduplicated)
    """
    if len(chunks) == 1:
        return analyze_review(chunks[0])

    results = [analyze_review(chunk) for chunk in chunks]

    # Filter out failed analyses
    valid = [r for r in results if r["score"] is not None]

    if not valid:
        return {
            "sentiment": "unknown",
            "score": None,
            "summary": "Analysis unavailable.",
            "pros": [],
            "cons": [],
        }

    # Score: average
    avg_score = round(sum(r["score"] for r in valid) / len(valid))

    # Sentiment: majority vote
    from collections import Counter
    sentiment_counts = Counter(r["sentiment"] for r in valid if r["sentiment"] != "unknown")
    if sentiment_counts:
        top_sentiment, top_count = sentiment_counts.most_common(1)[0]
        # If it's a tie between positive and negative, call it mixed
        if top_count == 1 and len(sentiment_counts) > 1:
            top_sentiment = "mixed"
    else:
        top_sentiment = "mixed"

    # Summary: join all
    summaries = [r["summary"] for r in valid if r.get("summary")]
    combined_summary = " ".join(summaries)

    # Pros / cons: deduplicate
    all_pros = list(dict.fromkeys(p for r in valid for p in (r.get("pros") or [])))
    all_cons = list(dict.fromkeys(c for r in valid for c in (r.get("cons") or [])))

    return {
        "sentiment": top_sentiment,
        "score": avg_score,
        "summary": combined_summary,
        "pros": all_pros[:3],
        "cons": all_cons[:3],
    }
