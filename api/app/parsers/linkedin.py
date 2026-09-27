# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

"""
LinkedIn data export parser.

The export is a flat directory of CSV files; the importer ships them unchanged
and the API classifies every file by its header row (files with an unknown
header are ignored):

  messages.csv      CONVERSATION ID,CONVERSATION TITLE,FROM,SENDER PROFILE URL,
                    TO,RECIPIENT PROFILE URLS,DATE,SUBJECT,CONTENT,FOLDER,
                    ATTACHMENTS
  Notes.csv         Connection First Name,Connection Last Name,Connection
                    Profile URL,Note,Created On,Edited On   (usually empty)
  Connections.csv   free-text preamble lines, then First Name,Last Name,URL,
                    Email Address,Company,Position,Connected On

Handling rules:
  - messages filed as spam (FOLDER=SPAM) are not imported
  - SUBJECT becomes a leading `Betreff:` line (subjects belong to a message,
    not to a thread - 29 conversations have more than one)
  - ATTACHMENTS are appended as `(Anhang: <url>)`
  - HTML (spinmails) is converted to plain text via app.parsers.common
  - LinkedIn writes the owner without umlauts ("Stefan Koelle"), OWN_NAME may
    have them -> all name comparisons use fold_name()

Dates: DATE is "2026-09-09 17:35:04 UTC", Connected On is "03 Jun 2025".

Thread ids:
  messages:       linkedin_<slug(titel|gegenüber)>_<sha1(konversations-id)[:8]>
  notes/contacts: linkedin-notiz-<slug(name)>
"""

import csv
import hashlib
import io
import re
from collections import Counter
from datetime import datetime, timezone

from app.parsers.common import (
    BulkParseResult,
    dedupe,
    fold_name,
    slugify,
    strip_html,
)

MSG_PREFIX = "linkedin_"
NOTE_PREFIX = "linkedin-notiz-"

# Header first cell -> file kind. Connections.csv starts with free-text
# preamble lines, so the header row has to be searched for.
_HEADER_KINDS = {
    "conversation id": "messages",
    "connection first name": "notes",
    "first name": "contacts",
}

# Placeholders LinkedIn uses instead of a name; they are useless as contact
# mappings (19 conversations would all map to "LinkedIn Member").
_GENERIC_NAMES = frozenset({"linkedin member", "linkedin for learning"})


def parse_linkedin_files(files: list[dict], own_name: str = "") -> BulkParseResult:
    """Parse raw LinkedIn CSV files.

    files: [{"path": "...", "content": "..."}]
    own_name: display name of the archive owner (from OWN_NAME). Used to find
    the counterpart of a conversation; when empty it is inferred as the sender
    with the most messages.
    """
    classified = [_read_table(f.get("content", "")) for f in files]
    kinds = {kind for kind, _ in classified}

    own = (own_name or "").strip()
    if not own and "messages" in kinds:
        own = _infer_own_name(data for kind, data in classified if kind == "messages")

    message_rows: list[dict] = []
    note_rows: list[dict] = []
    mappings: list[tuple[str, str]] = []

    for kind, data in classified:
        if kind == "messages":
            rows, block_mappings = _parse_messages(data, own)
            message_rows.extend(rows)
            mappings.extend(block_mappings)
        elif kind == "notes":
            rows, note_mappings = _parse_notes(data, own)
            note_rows.extend(rows)
            mappings.extend(note_mappings)
        elif kind == "contacts":
            rows, contact_mappings = _parse_contacts(data, own)
            note_rows.extend(rows)
            mappings.extend(contact_mappings)

    return BulkParseResult(
        messages=message_rows,
        notes=note_rows,
        mappings=dedupe(mappings),
        kinds=kinds,
        own_name=own,
    )


def _read_table(content: str) -> tuple[str, list[dict]]:
    """(kind, rows) of one CSV file; kind "unknown" for everything else.

    The header row is searched for instead of assumed to be row 0, because
    Connections.csv starts with free-text preamble lines.
    """
    parsed = list(csv.reader(io.StringIO(content)))
    for i, row in enumerate(parsed):
        if not row:
            continue
        kind = _HEADER_KINDS.get(row[0].strip().casefold())
        if not kind:
            continue
        header = [cell.strip() for cell in row]
        data = [
            {header[j]: (raw[j].strip() if j < len(raw) else "")
             for j in range(len(header))}
            for raw in parsed[i + 1:]
            if any(cell.strip() for cell in raw)
        ]
        return kind, data
    return "unknown", []


def _infer_own_name(data: list[dict]) -> str:
    senders: Counter[str] = Counter(
        row.get("FROM", "").strip() for row in data if row.get("FROM", "").strip()
    )
    return senders.most_common(1)[0][0] if senders else ""


def _parse_messages(data: list[dict], own: str) -> tuple[list[dict], list[tuple[str, str]]]:
    conversations: dict[str, list[dict]] = {}
    for row in data:
        if row.get("FOLDER", "").upper() == "SPAM":
            continue  # 9 spam messages, 7 conversations only exist because of them
        conv_id = row.get("CONVERSATION ID", "").strip()
        if conv_id:
            conversations.setdefault(conv_id, []).append(row)

    rows: list[dict] = []
    mappings: list[tuple[str, str]] = []

    for conv_id, conv_rows in conversations.items():
        participants: set[str] = set()
        for row in conv_rows:
            if row.get("FROM", "").strip():
                participants.add(row["FROM"].strip())
            participants.update(
                p.strip() for p in row.get("TO", "").split(",") if p.strip()
            )

        others = sorted(
            p for p in participants if not own or fold_name(p) != fold_name(own)
        )
        contact = others[0] if len(others) == 1 else None

        title = next(
            (r.get("CONVERSATION TITLE", "").strip() for r in conv_rows
             if r.get("CONVERSATION TITLE", "").strip()),
            "",
        )
        slug_source = title or (others[0] if len(others) == 1
                                else "-".join(others) or "gruppe")
        digest = hashlib.sha1(conv_id.encode("utf-8")).hexdigest()[:8]
        thread_id = f"{MSG_PREFIX}{slugify(slug_source)}_{digest}"
        participant_count = max(len(participants), 2)

        for row in conv_rows:
            timestamp_ms = _date_to_ms(row.get("DATE", ""))
            if timestamp_ms is None:
                continue
            rows.append({
                "thread_id": thread_id,
                "sender_name": row.get("FROM", "").strip() or "unknown",
                "timestamp_ms": timestamp_ms,
                "content": _compose(row),
                "message_type": "text",
                "reactions": None,
                "participant_count": participant_count,
            })

        if contact and _is_mappable(contact, own):
            mappings.append((contact, thread_id))

    return rows, mappings


def _compose(row: dict) -> str | None:
    """Betreff line + message text + attachments of one CSV row."""
    parts: list[str] = []
    subject = row.get("SUBJECT", "").strip()
    if subject:
        parts.append(f"Betreff: {subject}")
    body = strip_html(row.get("CONTENT", "").strip() or None)
    if body:
        parts.append(body)
    for url in re.split(r"\s+", row.get("ATTACHMENTS", "").strip()):
        if url.startswith("http"):
            parts.append(f"(Anhang: {url})")
    return "\n".join(parts) or None


def _parse_notes(data: list[dict], own: str) -> tuple[list[dict], list[tuple[str, str]]]:
    rows: list[dict] = []
    mappings: list[tuple[str, str]] = []

    for row in data:
        name = " ".join(
            part for part in (row.get("Connection First Name", "").strip(),
                              row.get("Connection Last Name", "").strip())
            if part
        )
        timestamp_ms = _date_to_ms(row.get("Created On", ""))
        if not name or timestamp_ms is None or not _is_mappable(name, own):
            continue

        thread_id = f"{NOTE_PREFIX}{slugify(name)}"
        rows.append({
            "thread_id": thread_id,
            "sender_name": name,
            "timestamp_ms": timestamp_ms,
            "content": strip_html(row.get("Note", "").strip() or None),
            "message_type": "text",
            "reactions": None,
            "participant_count": 2,
        })
        mappings.append((name, thread_id))

    return rows, mappings


def _parse_contacts(data: list[dict], own: str) -> tuple[list[dict], list[tuple[str, str]]]:
    """One synthetic message per connection: when did we connect, where
    does the person work, what is the profile URL."""
    rows: list[dict] = []
    mappings: list[tuple[str, str]] = []

    for row in data:
        name = " ".join(
            part for part in (row.get("First Name", "").strip(),
                              row.get("Last Name", "").strip())
            if part
        )
        timestamp_ms = _date_to_ms(row.get("Connected On", ""))
        if not name or timestamp_ms is None or not _is_mappable(name, own):
            continue

        connected = datetime.fromtimestamp(
            timestamp_ms / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d")
        parts = [f"Verbunden am {connected}"]
        for label, key in (("Firma", "Company"), ("Position", "Position"),
                           ("Profil", "URL"), ("E-Mail", "Email Address")):
            value = row.get(key, "").strip()
            if value:
                parts.append(f"{label}: {value}")

        thread_id = f"{NOTE_PREFIX}{slugify(name)}"
        rows.append({
            "thread_id": thread_id,
            "sender_name": name,
            "timestamp_ms": timestamp_ms,
            "content": "\n".join(parts),
            "message_type": "text",
            "reactions": None,
            "participant_count": 2,
        })
        mappings.append((name, thread_id))

    return rows, mappings


def _is_mappable(name: str, own: str) -> bool:
    """No mappings for myself and none for LinkedIn's placeholder names."""
    folded = fold_name(name)
    if own and folded == fold_name(own):
        return False
    return folded not in _GENERIC_NAMES


def _date_to_ms(value: str) -> int | None:
    value = (value or "").strip().removesuffix(" UTC").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d %b %Y", "%Y-%m-%d"):
        try:
            moment = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        return int(moment.timestamp() * 1000)
    return None
