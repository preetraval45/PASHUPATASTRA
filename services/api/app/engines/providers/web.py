"""Sati AI's reach beyond its own knowledge base: passages fetched from the open web at question time.

The project's own models do the work; the web only supplies text. Sources fetch candidate documents,
Brahmacharini's passage ranker (`sati.webqa`, served as trees) orders their passages, and the answer
quotes the best one with its link, so nothing is said that a cited page does not say (rule 1). Until a
ranker is exported, the hand-set score in `pashupatastra.webread` orders them.

Sources are named in PASHU_WEB_SOURCES:

* `wikipedia` — the MediaWiki search API, introductions of the top articles (CC BY-SA 4.0).
* `searxng` — a self-hosted SearXNG metasearch instance at PASHU_WEB_SEARCH_URL, which queries the
  general web engines; the top result pages are fetched and their text extracted. Self-hosted keeps it
  vendor-neutral and runnable on-prem.

Everything fetched is untrusted text: it is quoted, never followed.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

from pashupatastra.webread import (  # noqa: F401  (re-exported for the provider and tests)
    Document,
    candidates,
    query_terms,
    quality,
    scorer,
    subject,
    wikipedia,
)
from pashupatastra.webread import get as _get

RANKER = Path(__file__).resolve().parents[2] / "sati_models" / "brahmacharini_ranker.json"


def public(url: str) -> bool:
    """Only https pages on public addresses are fetched: a search result must never reach an internal one."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return False
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parts.hostname, 443)}
    except OSError:
        return False
    return bool(addresses) and all(ipaddress.ip_address(a.split("%")[0]).is_global for a in addresses)


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "template"}
    BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "td", "dd", "div", "section", "article", "br", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth, self.parts, self.title, self._in_title = 0, [], "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.depth:
            self.parts.append(data)


def page_text(html: str) -> tuple[str, str]:
    parser = _Text()
    parser.feed(html)
    lines = (" ".join(line.split()) for line in "".join(parser.parts).split("\n"))
    # Menus and buttons are short lines; prose is what answers.
    return " ".join(parser.title.split()), "\n".join(line for line in lines if len(line) > 60)


def _page(result: dict) -> Document | None:
    url = result.get("url", "")
    if not public(url):
        return None
    try:
        raw = _get(url)
    except Exception:
        return None
    title, text = page_text(raw.decode("utf-8", errors="replace"))
    if len(text) < 200:
        return None
    host = urllib.parse.urlsplit(url).hostname or ""
    return Document(result.get("title") or title, url, text[:40_000], host.removeprefix("www."))


def searxng(question: str, base: str, limit: int = 4) -> list[Document]:
    raw = _get(f"{base.rstrip('/')}/search", {"q": question, "format": "json", "safesearch": 1})
    results = [r for r in json.loads(raw.decode("utf-8")).get("results", []) if r.get("url")][:limit]
    with ThreadPoolExecutor(max_workers=limit) as pool:
        pages = [d for d in pool.map(_page, results) if d]
    snippets = [Document(r.get("title", ""), r["url"], r.get("content", ""), urllib.parse.urlsplit(r["url"]).hostname or "")
                for r in results if len(r.get("content", "")) > 80]
    return pages or snippets


@lru_cache(maxsize=512)
def fetch(question: str, sources: tuple[str, ...], search_url: str | None) -> tuple[Document, ...]:
    found: list[Document] = []
    for name in sources:
        try:
            if name == "wikipedia":
                found += wikipedia(question)
            elif name == "searxng" and search_url:
                found += searxng(question, search_url)
        except Exception:
            continue  # one unreachable source must not silence the others
    return tuple(found)


@lru_cache
def ranker() -> dict | None:
    return json.loads(RANKER.read_text(encoding="utf-8")) if RANKER.exists() else None


@dataclass(frozen=True)
class Match:
    score: float
    coverage: float
    title_fit: float
    doc: Document
    text: str


def rank(question: str, documents: tuple[Document, ...]) -> list[Match]:
    score = scorer(ranker())
    found = [Match(round(score(f), 4), f["coverage"], f["title_fit"], doc, text)
             for doc, text, f in candidates(question, documents)]
    found.sort(key=lambda m: -m.score)
    return found
