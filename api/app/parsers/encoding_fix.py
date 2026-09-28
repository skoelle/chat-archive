# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

"""
Meta often serves special characters/emoji incorrectly encoded in takeout
JSON: UTF-8 bytes get misinterpreted as Latin-1 and re-escaped. Affects both
reference projects (instagram-to-sqlite, Facebook-Message-Parser), which do
not implement this fix.

The recovered string is also normalized to NFC. Meta's takeout stores names
in decomposed form (u + combining diaeresis instead of a precomposed ü),
which would otherwise split one person into two: fold_name() cannot fold the
combining sequence, LIKE does not match it either (utf8mb4_general_ci does
not normalize), so the same contact would show up twice in /contacts/top and
be missed by /conversation.

This module is only used by the Instagram/Facebook parsers. The XING/LinkedIn
exports are clean UTF-8 and must never be passed through here (the latin1
round trip would corrupt them).
"""

import unicodedata


def fix_mojibake(text: str | None) -> str | None:
    if text is None:
        return None
    try:
        text = text.encode("latin1").decode("utf8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass  # already correctly encoded, or not a mojibake case
    return unicodedata.normalize("NFC", text)
