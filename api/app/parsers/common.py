# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

"""Shared helpers of the CSV-based bulk parsers (XING, LinkedIn).

Everything that is not specific to one export format lives here: the result
type of a bulk parse, slug generation for thread ids, umlaut folding for
display names and the HTML-to-text conversion used by both platforms.
"""

import re
from html.parser import HTMLParser
from typing import NamedTuple

UMAP = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                      "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})

_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_BLOCK_TAGS = frozenset({"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4",
                         "blockquote", "section"})
_SKIP_TAGS = frozenset({"script", "style", "head", "title"})


class BulkParseResult(NamedTuple):
    messages: list[dict]             # rows for conversation threads (platform added by caller)
    notes: list[dict]                # rows for note/contact threads
    mappings: list[tuple[str, str]]  # (display_name, thread_id) for contact_mappings
    kinds: set[str]                  # file kinds present in the payload
    own_name: str                    # sender treated as "myself"


def fold_name(name: str) -> str:
    """Lowercase + umlaut folding: 'Stefan Kölle' == 'Stefan Koelle'.

    Exports do not agree on the spelling of the archive owner (LinkedIn has no
    umlauts, OWN_NAME may have them), so name comparisons use this.
    """
    return (name or "").translate(UMAP).casefold().strip()


def unique(values) -> list[str]:
    return list(dict.fromkeys(values))


def dedupe(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return list(dict.fromkeys(pairs))


def slugify(text: str, max_len: int = 40) -> str:
    text = (text or "").translate(UMAP).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len].strip("-") or "ohne-betreff"


class _HtmlToText(HTMLParser):
    """Converts the HTML fragments some exports store as message into text."""

    def __init__(self, base_url: str = ""):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self._links: list[tuple[str, int]] = []
        self._base_url = base_url

    def _absolute(self, href: str) -> str:
        if href.startswith("/") and self._base_url:
            return f"{self._base_url.rstrip('/')}{href}"
        return href

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
            return
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._links.append((href, len(self.parts)))
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            if self._skip:
                self._skip -= 1
            return
        if tag == "a" and self._links:
            href, start = self._links.pop()
            label = "".join(self.parts[start:]).strip()
            if href and href != label and not label.endswith(href):
                self.parts.append(f" ({self._absolute(href)})")
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def strip_html(text: str | None, base_url: str = "") -> str | None:
    """Plain text of an HTML message fragment.

    Tags are dropped, <br>/<p>/<div> become line breaks, entities are decoded,
    <script>/<style> content is removed and link targets are appended as
    `(https://...)`. Plain text is returned unchanged.
    """
    if not text or not _HTML_TAG.search(text):
        return text

    parser = _HtmlToText(base_url)
    try:
        parser.feed(text)
        parser.close()
    except (ValueError, AssertionError, EOFError, RecursionError, UnicodeDecodeError):
        return text  # unreadable markup: keep the original content

    plain = "".join(parser.parts).replace("\xa0", " ")
    plain = re.sub(r"[ \t]+", " ", plain)
    plain = re.sub(r" *\n *", "\n", plain)
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    return plain.strip() or None
