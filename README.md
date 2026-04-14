# Review Analyzer

A Python application that scrapes product/book data from an e-commerce site,
preprocesses the text, and uses an OpenAI-compatible LLM to generate structured
sentiment analysis and summaries for each item.

---

## Chosen Product URL

```
https://books.toscrape.com/catalogue/category/books/mystery_3/index.html
```

**Why this URL?**
Books to Scrape (books.toscrape.com) is a sandbox site built specifically for
web scraping practice. It has clean HTML, no JavaScript rendering required,
no bot detection, and no rate limiting. This makes it ideal for demonstrating
a robust scraping + LLM pipeline without fighting anti-scraping measures.

Each book's description is treated as a "review" and sent to the LLM for
sentiment analysis and summarization.

---

## Project Structure

```
review_analyzer/
    main.py           - Entry point and orchestrator
    scraper.py        - Fetches and parses books from the product page
    preprocessor.py   - Cleans text and splits long content into chunks
    llm_client.py     - Sends content to OpenAI API and parses responses
    storage.py        - Saves results as JSON and CSV
    requirements.txt
    README.md
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/goel091/review-analyzer.git
cd review-analyzer
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Upgrade pip and install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Set your OpenAI API key

```powershell
# Windows PowerShell
$env:OPENAI_API_KEY="sk-your-key-here"

# Mac/Linux
export OPENAI_API_KEY="sk-your-key-here"
```

---

## Running the Application

### Basic usage

```powershell
python main.py --url "https://books.toscrape.com/catalogue/category/books/mystery_3/index.html"
```

### With options

```powershell
python main.py `
  --url "https://books.toscrape.com/catalogue/category/books/mystery_3/index.html" `
  --output-dir results/ `
  --delay 1.5 `
  --verbose
```

### All available flags

```
--url URL           Product/category page URL to scrape (required)
--output-dir DIR    Where to save output files (default: ./output/)
--delay SECONDS     Delay between LLM API calls (default: 1.0)
--no-csv            Skip CSV output, save JSON only
--verbose           Show debug-level logs
```

---

## Output

Two files are saved in the output directory:

### reviews.json

```json
[
  {
    "author": "books.toscrape.com",
    "rating": 4,
    "date": "N/A",
    "title": "Sharp Objects",
    "body": "A debut novel...",
    "token_count": 87,
    "llm_sentiment": "mixed",
    "llm_score": 3,
    "llm_summary": "Dark psychological thriller with a troubled protagonist.",
    "llm_pros": ["Gripping plot", "Strong character development"],
    "llm_cons": ["Disturbing themes", "Slow start"]
  }
]
```

### reviews.csv

A flat CSV version. Lists (pros, cons) are joined with a pipe delimiter.
Encoded as UTF-8 with BOM for Excel compatibility.

---

## Design Choices

### Scraping
- Uses requests + BeautifulSoup — no headless browser needed for this site
- Paginates automatically (up to 2 pages by default)
- Fetches each book's individual page for the full description
- Rotating user agents and randomized delays for polite crawling
- Retry logic with exponential backoff for transient network errors

### Preprocessing
- Strips non-ASCII characters, HTML entities, and URLs
- Token-aware chunking using tiktoken — reviews over 800 tokens are split
  at sentence boundaries to keep each API call within budget

### LLM Integration
- Structured JSON output prompt (sentiment, score, summary, pros, cons)
- Temperature 0.3 for consistent, parseable responses
- Handles RateLimitError with Retry-After header support
- Multi-chunk reviews are analyzed separately then merged

### Storage
- JSON preserves full nested structure
- CSV is flattened for easy viewing in Excel or pandas

---

## Limitations

1. books.toscrape.com has descriptions, not real customer reviews.
   For real reviews, Selenium + a site that permits scraping would be needed.
2. Pagination is capped at 2 pages. Remove the max_pages limit in scraper.py
   to scrape more.
3. Each book triggers one extra HTTP request for its description page.
   For large catalogues, this adds up.
