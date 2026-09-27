# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

"""
XING data export (Datenauskunft) parser.

The export is an HTML bundle with CSV files below data/:

  data/messages-backend/files/<hash>.csv      sent/received messages
  data/network-inquiry/files/<hash>.csv       contact notes + contact dates

Messages CSV (no header row, exactly 6 columns per row):

  conversation row:  Betreff, timestamp, "Teilnehmer1,Teilnehmer2", "", "", ""
  message row:       "", "", "", Absender, timestamp, Inhalt

A conversation row starts a new block, every following message row belongs to
that block until the next conversation row. Multi-line contents are quoted, so
the file must be read with a real CSV reader.

  data/network-inquiry/files/*.csv (with header row):
  notes:     "Name","Erstellt am","Text der Notiz"
  contacts:  "Name","Kontakt bestätigt am"

Timestamps look like "2014-06-19 06:32:37 UTC" (always UTC).

XING exports clean UTF-8, so app.parsers.encoding_fix is deliberately not
applied here (a latin1 -> utf8 round trip would corrupt valid text).
Messages that XING stored as HTML (event invitations, newsletters) are
converted to plain text by strip_html().

Thread ids:
  messages:  xing_<slug(betreff)>_<sha1(teilnehmer|betreff|zeitstempel)[:8]>
  notes:     xing-notiz-<slug(name)>

slugify(), dedupe() and strip_html() are shared with the LinkedIn parser and
live in app.parsers.common.
"""

import csv
import hashlib
import io
from collections import Counter
from datetime import datetime, timezone

from app.parsers.common import (
    BulkParseResult,
    dedupe,
    slugify,
    unique,
)
from app.parsers.common import (
    strip_html as _strip_html,
)

MSG_PREFIX = "xing_"
NOTE_PREFIX = "xing-notiz-"

# Result type is shared with the other bulk parsers (LinkedIn).
XingParseResult = BulkParseResult


def parse_xing_files(files: list[dict], own_name: str = "") -> BulkParseResult:
    """Parse raw XING CSV files.

    files: [{"path": "...", "content": "..."}]
    own_name: display name of the archive owner (from OWN_NAME). Used to find
    the counterpart of a conversation; when empty it is inferred as the sender
    with the most messages.
    """
    classified = [(_classify(f.get("content", "")), f.get("content", "")) for f in files]
    kinds = {kind for kind, _ in classified}

    own = (own_name or "").strip()
    if not own and "messages" in kinds:
        own = _infer_own_name(content for kind, content in classified if kind == "messages")

    message_rows: list[dict] = []
    note_rows: list[dict] = []
    mappings: list[tuple[str, str]] = []

    for kind, content in classified:
        if kind == "messages":
            rows, block_mappings = _parse_messages(content, own)
            message_rows.extend(rows)
            mappings.extend(block_mappings)
        elif kind == "notes":
            rows, note_mappings = _parse_notes(content)
            note_rows.extend(rows)
            mappings.extend(note_mappings)
        elif kind == "contacts":
            rows, note_mappings = _parse_contacts(content)
            note_rows.extend(rows)
            mappings.extend(note_mappings)

    # Never map a contact to myself: the notes CSV contains a row named like
    # the archive owner and OWN_NAME may be misconfigured.
    if own:
        mappings = [(name, thread_id) for name, thread_id in mappings if name != own]

    return BulkParseResult(
        messages=message_rows,
        notes=note_rows,
        mappings=dedupe(mappings),
        kinds=kinds,
        own_name=own,
    )


def _classify(content: str) -> str:
    header = next(csv.reader(io.StringIO(content)), None)
    if header == ["Name", "Erstellt am", "Text der Notiz"]:
        return "notes"
    if header == ["Name", "Kontakt bestätigt am"]:
        return "contacts"
    return "messages"


def _infer_own_name(contents) -> str:
    senders: Counter[str] = Counter()
    for content in contents:
        for row in csv.reader(io.StringIO(content)):
            if len(row) >= 6 and row[3].strip() and not (row[0].strip() or row[1].strip() or row[2].strip()):
                senders[row[3].strip()] += 1
    return senders.most_common(1)[0][0] if senders else ""


def _parse_messages(content: str, own: str) -> tuple[list[dict], list[tuple[str, str]]]:
    blocks: list[dict] = []
    current: dict | None = None

    for row in csv.reader(io.StringIO(content)):
        if len(row) < 6:
            continue
        if row[0].strip() or row[1].strip() or row[2].strip():
            current = {
                "subject": row[0].strip(),
                "started_at": row[1].strip(),
                "participants": [p.strip() for p in row[2].split(",") if p.strip()],
                "messages": [],
            }
            blocks.append(current)
        else:
            if current is None:  # defensive: message before any conversation row
                current = {"subject": "", "started_at": "", "participants": [], "messages": []}
                blocks.append(current)
            current["messages"].append(row)

    rows: list[dict] = []
    mappings: list[tuple[str, str]] = []
    seen_threads: set[str] = set()

    for block in blocks:
        if not block["messages"]:
            continue  # 11 empty conversations in the export

        thread_id = _block_thread_id(block)
        participant_count = _participant_count(block["participants"])
        contact = _counterpart(block, own)

        for row in block["messages"]:
            timestamp_ms = _ts_to_ms(row[4])
            if timestamp_ms is None:
                continue
            rows.append({
                "thread_id": thread_id,
                "sender_name": row[3].strip() or "unknown",
                "timestamp_ms": timestamp_ms,
                "content": strip_html(row[5].strip() or None),
                "message_type": "text",
                "reactions": None,
                "participant_count": participant_count,
            })

        if contact and thread_id not in seen_threads:
            mappings.append((contact, thread_id))
            seen_threads.add(thread_id)

    return rows, mappings


def _parse_notes(content: str) -> tuple[list[dict], list[tuple[str, str]]]:
    rows: list[dict] = []
    mappings: list[tuple[str, str]] = []

    for i, row in enumerate(csv.reader(io.StringIO(content))):
        if i == 0 and row[:3] == ["Name", "Erstellt am", "Text der Notiz"]:
            continue
        if len(row) < 3:
            continue
        name, created, text = row[0].strip(), row[1].strip(), row[2].strip()
        timestamp_ms = _ts_to_ms(created)
        if not name or timestamp_ms is None:
            continue

        thread_id = f"{NOTE_PREFIX}{slugify(name)}"
        rows.append({
            "thread_id": thread_id,
            "sender_name": name,
            "timestamp_ms": timestamp_ms,
            "content": strip_html(text or None),
            "message_type": "text",
            "reactions": None,
            "participant_count": 2,
        })
        mappings.append((name, thread_id))

    return rows, mappings


def _parse_contacts(content: str) -> tuple[list[dict], list[tuple[str, str]]]:
    rows: list[dict] = []
    mappings: list[tuple[str, str]] = []

    for i, row in enumerate(csv.reader(io.StringIO(content))):
        if i == 0 and row[:2] == ["Name", "Kontakt bestätigt am"]:
            continue
        if len(row) < 2:
            continue
        name, confirmed = row[0].strip(), row[1].strip()
        timestamp_ms = _ts_to_ms(confirmed)
        if not name or timestamp_ms is None:
            continue  # 71 contacts without confirmation date

        thread_id = f"{NOTE_PREFIX}{slugify(name)}"
        rows.append({
            "thread_id": thread_id,
            "sender_name": name,
            "timestamp_ms": timestamp_ms,
            "content": f"Kontakt bestätigt am {confirmed.replace(' UTC', '')}",
            "message_type": "text",
            "reactions": None,
            "participant_count": 2,
        })
        mappings.append((name, thread_id))

    return rows, mappings


def _block_thread_id(block: dict) -> str:
    key = "|".join([
        ";".join(block["participants"]),
        block["subject"],
        block["started_at"],
    ])
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return f"{MSG_PREFIX}{slugify(block['subject'])}_{digest}"


def _participant_count(participants: list[str]) -> int | None:
    if not participants:
        return None
    # XING drops deactivated contacts from the participant list, so a single
    # name still means a 1:1 conversation.
    return 2 if len(participants) == 1 else len(participants)


def _counterpart(block: dict, own: str) -> str | None:
    """Name of the contact the conversation belongs to, None if unknown."""
    participants = block["participants"]
    if len(participants) > 2:
        return None  # group conversation, no single contact

    others = [p for p in participants if p != own]
    if len(others) == 1:
        return others[0]

    # Participant list only contains myself: fall back to the other sender.
    other_senders = unique(
        row[3].strip() for row in block["messages"] if row[3].strip() and row[3].strip() != own
    )
    if len(other_senders) == 1:
        return other_senders[0]
    return None


def _ts_to_ms(value: str) -> int | None:
    value = (value or "").strip().removesuffix(" UTC").strip()
    if not value:
        return None
    try:
        moment = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(moment.timestamp() * 1000)


def strip_html(text: str | None) -> str | None:
    """Plain text of a XING message.

    XING stores some messages as HTML (event invitations, newsletters,
    forwarded mails) - see app.parsers.common.strip_html for the rules. Link
    targets that start with "/" are resolved against www.xing.com.
    """
    return _strip_html(text, base_url="https://www.xing.com")
