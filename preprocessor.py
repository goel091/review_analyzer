import re
import logging
import tiktoken

logger = logging.getLogger(__name__)

ENCODING_MODEL = "gpt-3.5-turbo"
MAX_TOKENS_PER_CHUNK = 800


def clean_text(text):
    if not text:
        return ""
    text = text.replace("xc3xa9", "e")
    text = text.replace("xc3xa8", "e")
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^\x09\x0A\x20-\x7E]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def count_tokens(text):
    try:
        enc = tiktoken.encoding_for_model(ENCODING_MODEL)
        return len(enc.encode(text))
    except Exception as e:
        logger.warning("tiktoken failed: %s", e)
        return len(text.split())


def chunk_text(text, max_tokens=MAX_TOKENS_PER_CHUNK):
    if count_tokens(text) <= max_tokens:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current_chunk = []
    current_tokens = 0
    for sentence in sentences:
        st = count_tokens(sentence)
        if current_tokens + st > max_tokens:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_tokens = st
        else:
            current_chunk.append(sentence)
            current_tokens += st
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks


def preprocess_review(review):
    cleaned_body = clean_text(review.get("body", ""))
    cleaned_title = clean_text(review.get("title", ""))
    full_text = (cleaned_title + ". " + cleaned_body).strip(". ") if cleaned_title else cleaned_body
    result = dict(review)
    result["body"] = cleaned_body
    result["title"] = cleaned_title
    result["full_text"] = full_text
    result["token_count"] = count_tokens(full_text)
    result["chunks"] = chunk_text(full_text)
    return result


def preprocess_all(reviews):
    processed = []
    for r in reviews:
        p = preprocess_review(r)
        if p["body"]:
            processed.append(p)
    logger.info("Preprocessing complete: %d/%d reviews retained.", len(processed), len(reviews))
    return processed
