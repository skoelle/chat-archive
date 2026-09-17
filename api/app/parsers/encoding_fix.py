# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

"""
Meta often serves special characters/emoji incorrectly encoded in takeout
JSON: UTF-8 bytes get misinterpreted as Latin-1 and re-escaped. Affects both
reference projects (instagram-to-sqlite, Facebook-Message-Parser), which do
not implement this fix.
"""


def fix_mojibake(text: str | None) -> str | None:
    if text is None:
        return None
    try:
        return text.encode("latin1").decode("utf8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text  # already correctly encoded, or not a mojibake case
