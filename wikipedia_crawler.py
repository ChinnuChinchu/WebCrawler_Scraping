"""Small, rate-limited crawler that uses Wikipedia's official API."""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

USER_AGENT = "LearningWikipediaCrawler/1.0 (educational project; rate-limited)"
HOST = "en.wikipedia.org"
API_URL = f"https://{HOST}/w/api.php"


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headings: list[str] = []
        self.paragraphs: list[str] = []
        self._tag: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag in {"p", "h2", "h3"}:
            self._tag, self._chunks = tag, []

    def handle_endtag(self, tag) -> None:
        if tag != self._tag:
            return
        text = re.sub(r"\s+", " ", "".join(self._chunks)).strip()
        if text:
            (self.paragraphs if tag == "p" else self.headings).append(text)
        self._tag, self._chunks = None, []

    def handle_data(self, data) -> None:
        if self._tag:
            self._chunks.append(data)


def canonical_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != HOST or not parsed.path.startswith("/wiki/"):
        return None
    title = parsed.path.removeprefix("/wiki/")
    if not title or ":" in title:
        return None
    return urlunparse(("https", HOST, f"/wiki/{title}", "", "", ""))


def fetch_article(url: str) -> tuple[dict[str, object], set[str]]:
    title = urlparse(url).path.removeprefix("/wiki/")
    params = urlencode({"action": "parse", "page": title, "prop": "text|links", "format": "json", "formatversion": "2", "maxlag": "5"})
    request = Request(f"{API_URL}?{params}", headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        raise ValueError(payload["error"].get("info", "Wikipedia API error"))
    page = payload["parse"]
    parser = TextParser()
    parser.feed(page["text"])
    record = {"url": url, "title": page["title"], "headings": parser.headings, "text": " ".join(parser.paragraphs)}
    links = {f"https://{HOST}/wiki/{quote(link['title'].replace(' ', '_'))}" for link in page.get("links", []) if link.get("ns") == 0 and link.get("exists", True)}
    return record, links


def write_outputs(records: list[dict[str, object]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "wikipedia_pages.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "wikipedia_pages.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["url", "title", "headings", "text"])
        writer.writeheader()
        for row in records:
            writer.writerow({**row, "headings": " | ".join(row["headings"])})


def crawl(start_url: str, max_pages: int, delay: float, output_dir: Path) -> int:
    start = canonical_url(start_url)
    if not start:
        raise ValueError("Use an https://en.wikipedia.org/wiki/ article URL.")
    queue, seen, records = deque([start]), set(), []
    while queue and len(records) < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            print(f"Fetching {len(records) + 1}/{max_pages}: {url}")
            record, links = fetch_article(url)
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            print(f"Skipping ({error}): {url}")
            continue
        records.append(record)
        queue.extend(link for link in sorted(links) if link not in seen)
        time.sleep(delay)
    write_outputs(records, output_dir)
    print(f"Saved {len(records)} pages to {output_dir.resolve()}")
    return len(records)


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--start", default="https://en.wikipedia.org/wiki/Web_scraping")
    cli.add_argument("--max-pages", type=int, default=5)
    cli.add_argument("--delay", type=float, default=1.0)
    cli.add_argument("--output", type=Path, default=Path("outputs"))
    args = cli.parse_args()
    crawl(args.start, args.max_pages, args.delay, args.output)
