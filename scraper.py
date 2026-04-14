"""
scraper.py

Scrapes product reviews from books.toscrape.com
This site is built for scraping practice - no blocks, no JS rendering needed.
Target: https://books.toscrape.com/catalogue/category/books/mystery_3/index.html
"""

import time
import random
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

BASE_URL = "https://books.toscrape.com"

RATING_MAP = {
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
}


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    }


def fetch_page(url, retries=3, delay=2.0):
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=get_headers(), timeout=15)
            response.raise_for_status()
            logger.info("Fetched %s (attempt %d)", url, attempt)
            return response.text
        except requests.exceptions.HTTPError as e:
            logger.warning("HTTP error on attempt %d: %s", attempt, e)
        except requests.exceptions.ConnectionError as e:
            logger.warning("Connection error on attempt %d: %s", attempt, e)
        except requests.exceptions.Timeout:
            logger.warning("Timeout on attempt %d for %s", attempt, url)
        except requests.exceptions.RequestException as e:
            logger.error("Unexpected request error: %s", e)
            break

        sleep_time = delay * (2 ** (attempt - 1)) + random.uniform(0.5, 1.5)
        logger.info("Retrying in %.1fs...", sleep_time)
        time.sleep(sleep_time)

    logger.error("Failed to fetch %s after %d attempts.", url, retries)
    return None


def get_book_description(book_url):
    """
    Fetch the individual book page and extract the description.
    This serves as our 'review text' since books.toscrape has descriptions not reviews.
    """
    html = fetch_page(book_url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    desc_tag = soup.select_one("#product_description ~ p")
    if desc_tag:
        return desc_tag.get_text(strip=True)
    return ""


def parse_books_page(html, base_catalogue_url):
    """
    Parse a listing page from books.toscrape.com.
    Each book becomes a 'review' with rating, title, price, and description.
    """
    soup = BeautifulSoup(html, "lxml")
    books = soup.select("article.product_pod")
    reviews = []

    for book in books:
        try:
            title_tag = book.select_one("h3 > a")
            title = title_tag["title"] if title_tag else "Unknown"

            # Rating is stored as a word class e.g. class="star-rating Three"
            rating_tag = book.select_one("p.star-rating")
            rating_word = rating_tag["class"][1] if rating_tag else "One"
            rating = RATING_MAP.get(rating_word, 0)

            price_tag = book.select_one("p.price_color")
            price = price_tag.get_text(strip=True) if price_tag else "N/A"

            # Build the full URL to the individual book page
            relative_href = title_tag["href"].replace("../", "") if title_tag else ""
            book_url = base_catalogue_url + relative_href

            logger.info("Fetching description for: %s", title)
            description = get_book_description(book_url)

            # Polite delay between individual book fetches
            time.sleep(random.uniform(0.5, 1.2))

            if description:
                reviews.append({
                    "author": "books.toscrape.com",
                    "rating": rating,
                    "date": "N/A",
                    "title": title,
                    "body": description,
                    "price": price,
                    "source_url": book_url,
                })

        except Exception as e:
            logger.warning("Skipping one book due to parse error: %s", e)
            continue

    logger.info("Parsed %d books from page.", len(reviews))
    return reviews


def scrape_reviews(url):
    """
    Main entry point. Accepts a books.toscrape.com category URL.
    Scrapes books from that page (and the next page if available).

    Example URL:
        https://books.toscrape.com/catalogue/category/books/mystery_3/index.html
    """
    # Determine the base catalogue URL for resolving relative links
    if "category" in url:
        # Category pages: links are relative to /catalogue/
        base_catalogue_url = BASE_URL + "/catalogue/"
    else:
        base_catalogue_url = BASE_URL + "/catalogue/"

    all_reviews = []
    current_url = url
    pages_scraped = 0
    max_pages = 2  # Limit to 2 pages so it runs in a reasonable time

    while current_url and pages_scraped < max_pages:
        logger.info("Scraping page %d: %s", pages_scraped + 1, current_url)
        html = fetch_page(current_url)
        if not html:
            break

        reviews = parse_books_page(html, base_catalogue_url)
        all_reviews.extend(reviews)
        pages_scraped += 1

        # Check for a "next" button
        soup = BeautifulSoup(html, "lxml")
        next_btn = soup.select_one("li.next > a")
        if next_btn and pages_scraped < max_pages:
            # next page URL is relative to the current page's directory
            current_dir = current_url.rsplit("/", 1)[0] + "/"
            current_url = current_dir + next_btn["href"]
            time.sleep(random.uniform(1.0, 2.0))
        else:
            break

    logger.info("Scraping complete. Total books collected: %d", len(all_reviews))

    if not all_reviews:
        logger.warning("No books were scraped. Check the URL and try again.")

    return all_reviews