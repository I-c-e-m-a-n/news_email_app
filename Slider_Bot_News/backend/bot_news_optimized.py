# -*- coding: utf-8 -*-
"""
bot_news_optimized.py
Performance-focused refactor of the original news fetch/summarize module.

Key improvements
- Replaced repeated NLTK calls with lightweight tokenization and cached resources
- Requests.Session with HTTP keep-alive + retries
- Parallel article fetching & summarization with ThreadPoolExecutor
- Early exits and safe fallbacks to avoid stalls
- Reduced per-call allocations; hoisted constants and compiled regexes
"""
from __future__ import annotations

# --- stdlib
import concurrent.futures as _fut
import dataclasses as _dc
import html
import os
import re
import time
import random
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin
from datetime import datetime
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo  # Py3.9+
except Exception:
    ZoneInfo = None  # fallback handled below

# --- third-party (already used by original file)
import requests
from bs4 import BeautifulSoup


# --- emails
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
import imaplib, email, threading
from email import policy
from email.header import decode_header
from email.utils import parseaddr
import socket
import re


# Optional: keep VADER if available (lazy import)
try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer as _VADER
    _have_vader = True
except Exception:
    _VADER = None  # type: ignore
    _have_vader = False

# --------------------
# Globals / constants
# --------------------
GNEWS_ENDPOINT = "https://gnews.io/api/v4/top-headlines"
DEFAULT_CATEGORIES = ("general")
DEFAULT_LANG = "en"
DEFAULT_COUNTRY = "sg"
NEWS_API_KEY = "5694941821caa13cba5d6c1d0cad4039"
GMAIL_USER = 'guruprasadnayak24@gmail.com'
GMAIL_PASS = 'qdqo byrz nhvo vlcq'
HELPER_USER = 'sliderhelper@gmail.com'



# Compile regexes once
_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_TAG_STRIP_RE = re.compile(r"<[^>]+>")


_ALIAS = {
    # common aliases -> IANA zones
    "usa": "America/New_York",
    "us": "America/New_York",
    "new york": "America/New_York", "nyc": "America/New_York",
    "est": "America/New_York", "edt": "America/New_York",
    "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles",
    "los angeles": "America/Los_Angeles", "la": "America/Los_Angeles",
    "chicago": "America/Chicago", "cst": "America/Chicago", "cdt": "America/Chicago",
    "denver": "America/Denver", "mst": "America/Denver", "mdt": "America/Denver",
    "london": "Europe/London", "uk": "Europe/London", "gmt": "Europe/London", "bst": "Europe/London",
    "paris": "Europe/Paris", "france": "Europe/Paris", "cet": "Europe/Paris", "cest": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "singapore": "Asia/Singapore", "sg": "Asia/Singapore", "sgt": "Asia/Singapore",
    "india": "Asia/Kolkata", "ist": "Asia/Kolkata",
    "dubai": "Asia/Dubai", "uae": "Asia/Dubai",
    "tokyo": "Asia/Tokyo", "japan": "Asia/Tokyo", "jst": "Asia/Tokyo",
    "sydney": "Australia/Sydney", "aest": "Australia/Sydney", "aedt": "Australia/Sydney",
    "utc": "UTC",
}


# Small, static stopword list (avoids heavy NLTK stopwords import at runtime)
_STOPWORDS = frozenset({
    "a","an","and","the","to","of","in","on","for","at","by","from","with","as",
    "is","are","was","were","be","been","being","that","this","it","its","if",
    "but","or","not","no","so","than","then","too","very","can","could","should",
    "would","may","might","will","shall","into","about","over","after","before",
    "up","down","out","off","only","just","also","more","most","other","some",
    "such","any","each","few","both","many","much","own","same"
})

# News Cache
_CACHE = {}


def resolve_timezone(tz_pref: str | None):
    """
    Accepts:
      - IANA names (e.g., 'America/New_York', 'Europe/London')
      - human aliases (e.g., 'usa', 'london', 'sg')
      - fixed offsets like '+05:30' or '-08:00'
    Returns a tzinfo usable in datetime.now(tz).
    """
    if not tz_pref:
        # default: Singapore
        if ZoneInfo: return ZoneInfo("Asia/Singapore")
        return timezone(timedelta(hours=8))  # fallback

    s = tz_pref.strip().lower()
    # alias → IANA
    s = _ALIAS.get(s, tz_pref)

    # try IANA
    if ZoneInfo:
        try:
            return ZoneInfo(s)
        except Exception:
            pass

    # try fixed offset like +HH:MM or -HH:MM
    m = re.match(r"^([+-])(\d{2}):(\d{2})$", s)
    if m:
        sign = 1 if m.group(1) == "+" else -1
        hh, mm = int(m.group(2)), int(m.group(3))
        return timezone(sign * timedelta(hours=hh, minutes=mm))

    # final fallback
    if ZoneInfo:
        return ZoneInfo("UTC")
    return timezone.utc

# Lazy, shared HTTP session with retries
def _make_session() -> requests.Session:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=64, pool_maxsize=64)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({
        "User-Agent": "bot_news_optimized/1.0 (+https://example.com)"
    })
    return s

_SESSION = _make_session()

# Optional VADER (constructed once)
_VADER_SIA = _VADER() if _have_vader else None

# -------- utils
def _fast_words(text: str) -> List[str]:
    # Lower + keep alnum and apostrophes
    return [w for w in _WORD_RE.findall(text.lower()) if w and w not in _STOPWORDS]

def _fast_sentences(text: str) -> List[str]:
    # Very light splitter; preserves original sentence text
    text = _TAG_STRIP_RE.sub("", text)
    text = html.unescape(text)
    sents = _SENT_SPLIT_RE.split(text.strip())
    # filter tiny fragments
    return [s.strip() for s in sents if len(s.strip().split()) >= 3]

def _hash(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode("utf-8", "ignore")).hexdigest()

# -------- sentiment
def analyze_sentiment(text: Optional[str]) -> Dict[str, float | str]:
    """Return VADER compound score and label. Falls back to neutral if VADER missing."""
    if not text:
        return {"compound": 0.0, "label": "neutral"}
    if _VADER_SIA is None:
        return {"compound": 0.0, "label": "neutral"}
    scores = _VADER_SIA.polarity_scores(text[:5000])  # cap to keep it fast
    comp = scores.get("compound", 0.0)
    label = "positive" if comp >= 0.05 else "negative" if comp <= -0.05 else "neutral"
    scores["label"] = label
    return scores

# -------- summarization (extractive, frequency-based)
def summarizeText(text: str, max_sentences: int = 15) -> str:
    if not text:
        return ""
    sentences = _fast_sentences(text)
    if not sentences:
        return ""

    words = _fast_words(text)
    if not words:
        return " ".join(sentences[:max_sentences])

    # term frequency
    freq: Dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    max_f = max(freq.values())
    for k in list(freq):
        freq[k] = freq[k] / max_f

    # score sentences
    scores: Dict[str, float] = {}
    for s in sentences:
        sw = _fast_words(s)
        if len(sw) < 3:
            continue
        scores[s] = sum(freq.get(w, 0.0) for w in sw)

    if not scores:
        return " ".join(sentences[:max_sentences])

    # pick top N by score, but return in original order for coherence
    top = sorted(sorted(scores, key=scores.get, reverse=True)[:max_sentences],
                 key=lambda s: sentences.index(s))
    return " ".join(top)

# -------- article fetch
@_dc.dataclass
class ArticleData:
    url: str
    title: str = ""
    source: str = ""
    description: str = ""
    text: str = ""
    sentiment: Optional[Dict[str, float | str]] = None
    summary: str = ""
    image: Optional[str] = None

def _extract_article_text(html_text: str) -> Tuple[str, Optional[str]]:
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "header", "footer", "nav", "aside", "form"]):
        tag.extract()

    # Try to find a lead image
    lead_img = None
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        lead_img = og.get("content")

    # Visible paragraphs of sane length
    paras: List[str] = []
    for p in soup.find_all("p"):
        t = p.get_text(" ", strip=True)
        if t and len(t.split()) >= 5:
            paras.append(t)
    text = "\n".join(paras)

    # fallback to article tags if <p> were scarce
    if len(paras) < 3:
        art = soup.find("article")
        if art:
            t = art.get_text(" ", strip=True)
            if t and len(t.split()) > len(text.split()):
                text = t
    return text, lead_img

def fetchArticle(url: str, timeout: float = 8.0) -> Dict[str, Optional[str]]:
    if url in _CACHE:
        return _CACHE[url]

    try:
        r = _SESSION.get(url, timeout=timeout)
        if r.status_code != 200:
            result = {"text": "", "image": None}
        else:
            text, image = _extract_article_text(r.text)
            result = {"text": text, "image": image}
    except Exception:
        result = {"text": "", "image": None}

    _CACHE[url] = result
    return result

# -------- news
def _gnews_request(api_key: str, category: str, max_items: int = 10, country: str | None = None) -> List[dict]:
    params = {
        "token": api_key,
        "lang": DEFAULT_LANG,
        "topic": category,
        "max": max_items,
    }
    if country:
        params["country"] = country
    r = _SESSION.get(GNEWS_ENDPOINT, params=params, timeout=6.0)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("articles", []) or []

def getNews(
    api_key: str,
    categories: Tuple[str, ...] = DEFAULT_CATEGORIES,
    per_category: int = 8,
    fetch_full: int = 12,
    parallel_workers: int = 12,
    country: str | None = None,
) -> List[dict]:
    """
    Fetch headlines across categories, then fetch/summarize top N articles in parallel.

    api_key: GNews API key
    per_category: max headlines to pull per category (cheap)
    fetch_full: number of distinct article URLs to download+summarize (expensive)
    """
    t0 = time.perf_counter()
    headlines: List[dict] = []
    seen_urls = set()

    # 1) Pull headlines (lightweight)
    for cat in categories:
        try:
            items = _gnews_request(api_key, cat, per_category, country=country)
            for it in items:
                url = it.get("url") or ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                headlines.append(it)
        except Exception:
            continue

    # 2) Choose a subset to fully fetch (unique URLs)
    # chosen = headlines[:fetch_full]
    chosen = headlines

    # 3) Concurrently fetch + process
    out: List[dict] = []
    def _work(item: dict) -> Optional[dict]:
        url = item.get("url") or ""
        title = item.get("title") or "No Title"
        source = (item.get("source") or {}).get("name") or "Unknown"
        desc = item.get("description") or ""

        art = fetchArticle(url)
        text = art.get("text") or desc or title
        sent = analyze_sentiment(text)
        summ = summarizeText(text, max_sentences=3)

        return {
            "title": title,
            "source": source,
            "summary": summ,
            "text": text,
            "url": url,
            "sentiment": sent,
        }

    with _fut.ThreadPoolExecutor(max_workers=parallel_workers) as ex:
        for res in ex.map(_work, chosen):
            if res:
                out.append(res)

    # 4) If something failed, still return at least headlines
    if not out and headlines:
        for it in headlines[:max(5, fetch_full)]:
            out.append({
                "title": it.get("title") or "No Title",
                "source": (it.get("source") or {}).get("name") or "Unknown",
                "summary": it.get("description") or "",
                "url": it.get("url") or "",
                "sentiment": {"compound": 0.0, "label": "neutral"},
            })

    # Optional: sort by (source, title) for determinism
    out.sort(key=lambda d: (d["source"], _hash(d["title"])))

    return out


def sendMailSingle(recipient: str, name: str, subject: str, body: str = "", html: str | None = None) -> bool:
    """
    Sends a single email (plain or plain+HTML) via Gmail SMTP over SSL.
    - Uses multipart/alternative (correctly renders HTML while keeping a text fallback)
    - Adds a small footer once
    - Short timeouts; concise error handling
    Returns True on success, False otherwise.
    """
    footer = "\n\nThis email was sent by Slider Bot."
    body = (body or "").rstrip() + footer

    msg = EmailMessage()
    msg["From"] = formataddr(("Slider Bot", HELPER_USER))
    msg["To"] = recipient
    msg["Subject"] = subject

    # multipart/alternative if html present; otherwise plain only
    msg.set_content(f"Hello {name},\n\n{body}")
    if html:
        # Provide a text fallback; keep HTML minimal to reduce size
        msg.add_alternative(
            f"""\
                <!doctype html>
                <html><body>
                <p>Hello {name},</p>
                {html}
                <p style="margin-top:16px;color:#666;font-size:12px">This email was sent by Slider Bot.</p>
                </body></html>
                """,
                            subtype="html",
                        )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.send_message(msg)
        # print(f"{name}'s Email sent successfully!")
        return True
    except Exception as e:
        print(f"Failed to send email to {recipient}: {e}")
        return False

_HTML_TAG_RE = re.compile(r"<[^>]+>")

def _decode_hdr(raw_val: str | None) -> str:
    if not raw_val:
        return ""
    parts = decode_header(raw_val)
    out = []
    for val, enc in parts:
        try:
            if isinstance(val, bytes):
                out.append(val.decode(enc or "utf-8", errors="ignore"))
            else:
                out.append(val)
        except Exception:
            out.append(str(val))
    return " ".join(out).strip()

def _extract_body(msg: email.message.Message) -> tuple[str, str]:
    """
    Return (text_body, html_body_or_empty). Prefers text/plain; falls back to HTML (stripped for snippet).
    """
    text_body, html_body = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            ctype = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            try:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                content = payload.decode(charset, errors="ignore")
            except Exception:
                content = ""
            if ctype == "text/plain" and not text_body:
                text_body = content
            elif ctype == "text/html" and not html_body:
                html_body = content
    else:
        try:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            text_body = payload.decode(charset, errors="ignore")
        except Exception:
            text_body = ""

    return text_body, html_body

def _html_to_text(html: str) -> str:
    # ultra-light sanitizer; enough for snippet fallback
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
    html = _HTML_TAG_RE.sub(" ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def fetch_and_email_news(
    recipient: str,
    name: str,
    params: list[str],
    *,
    api_key: str,
    per_category: int = 8,
    fetch_full: int = 12,
    parallel_workers: int = 12,
    timezone_pref: str | None = None, 
) -> bool:
    """
    Example:
      fetch_and_email_news("Jon@gmail.com","Jon",["us","general","technology"], api_key=NEWS_API_KEY)

    Behavior:
      - If first element is a 2-letter code, treat as country (e.g., 'us','sg','gb').
      - Remaining elements are categories/topics.
      - Builds a clean plain+HTML body and sends via sendMailSingle(...).
    """
    # --- parse params into (country, categories)
    country = None
    cats = list(params or [])
    if cats and isinstance(cats[0], str) and len(cats[0]) == 2:
        country = cats.pop(0).lower()
    categories = tuple(cats) if cats else ("general", "technology", "business")

    # --- fetch
    items = getNews(
        api_key=api_key,
        categories=categories,
        per_category=per_category,
        fetch_full=fetch_full,
        parallel_workers=parallel_workers,
        country=country,
    )

     # --- timezone-aware subject
    tz = resolve_timezone(timezone_pref)
    now = datetime.now(tz)
    subject = f"News Summary by Slider Bot at: {now.strftime('%Y-%m-%d %H:%M %Z')}"

    # --- bodies
    if not items:
        plain = "No news items were returned for your request."
        html = "<p>No news items were returned for your request.</p>"
    else:
        # plain
        header_bits = []
        if country:
            header_bits.append(f"country={country.upper()}")
        if categories:
            header_bits.append("topics=" + ", ".join(categories))
        lines = []
        if header_bits:
            lines.append("Filters: " + " | ".join(header_bits))
            lines.append("")
        for i, a in enumerate(items, 1):
            title   = a.get("title", "Untitled")
            source  = a.get("source", "Unknown")
            url     = a.get("url", "")
            summary = (a.get("summary") or "").strip()
            lines.append(f"{i}. [{source}] {title}")
            if summary:
                lines.append(f"   - {summary}")
            if url:
                lines.append(f"   {url}")
            lines.append("")
        plain = "\n".join(lines).strip()

        # html
        def esc(s: str) -> str:
            return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        items_html = []
        for i, a in enumerate(items, 1):
            title   = esc(a.get("title","Untitled"))
            source  = esc(a.get("source","Unknown"))
            url     = a.get("url") or "#"
            summary = esc((a.get("summary") or "").strip())
            items_html.append(
                f'''<li style="margin-bottom:12px">
                        <div><strong>[{source}]</strong> <a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></div>
                        <div style="color:#444;margin-top:4px;line-height:1.4">{summary}</div>
                    </li>'''
)
        filters_html = []
        if country:
            filters_html.append(f"<span>country=<b>{country.upper()}</b></span>")
        if categories:
            filters_html.append("<span>topics=<b>"+", ".join(categories)+"</b></span>")
        html = f"""\
<!doctype html>
<html>
  <body style="font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:14px;color:#111;line-height:1.5">
    {'<p>'+ ' | '.join(filters_html) +'</p>' if filters_html else ''}
    <ol style="padding-left:18px;margin:0">
      {''.join(items_html)}
    </ol>
  </body>
</html>
"""

    # --- send
    return sendMailSingle(recipient=recipient, name=name, subject=subject, body=plain, html=html)

# fetch_and_email_news("guruprasadnayak24@gmail.com", "Guru", ["us","general","nation", "business"], api_key=NEWS_API_KEY)
fetch_and_email_news("guruprasadnayak24@gmail.com", "Guru", ["sg","general","nation", "business"], api_key=NEWS_API_KEY)