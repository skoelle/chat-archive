# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

"""Persistence for XING bulk imports.

Shared by POST /import/xing and import_test.py, so both use exactly the same
delete-by-prefix rules. The thread_id prefixes are the only thing that tells
conversations (`xing_...`) apart from contact notes (`xing-notiz-...`).
"""

from sqlalchemy.orm import Session

from app.models import ContactMapping, Message
from app.parsers.xing import MSG_PREFIX, NOTE_PREFIX, XingParseResult


def store_xing(db: Session, result: XingParseResult) -> tuple[int, int]:
    """(Re-)import the parsed XING files and return (rows_inserted, threads).

    Only the file kinds present in the payload are replaced: a payload without
    the messages CSV leaves the conversations untouched, and vice versa.
    """
    if "messages" in result.kinds:
        db.query(Message).filter(
            Message.platform == "xing",
            Message.thread_id.startswith(MSG_PREFIX, autoescape=True),
        ).delete(synchronize_session=False)

    if result.kinds & {"notes", "contacts"}:
        db.query(Message).filter(
            Message.platform == "xing",
            Message.thread_id.startswith(NOTE_PREFIX, autoescape=True),
        ).delete(synchronize_session=False)

    rows = result.messages + result.notes
    for item in rows:
        db.add(Message(platform="xing", **item))

    _store_mappings(db, result.mappings)
    db.commit()

    return len(rows), len({row["thread_id"] for row in rows})


def _store_mappings(db: Session, mappings: list[tuple[str, str]]):
    """Create missing contact_mappings so /conversation finds XING threads by
    contact name, even when a thread only contains messages I sent myself."""
    if not mappings:
        return

    thread_ids = sorted({thread_id for _, thread_id in mappings})
    existing = {
        (display_name, thread_id)
        for display_name, thread_id in
        db.query(ContactMapping.display_name, ContactMapping.thread_id)
        .filter(ContactMapping.thread_id.in_(thread_ids))
        .all()
    }

    for display_name, thread_id in mappings:
        if (display_name, thread_id) in existing:
            continue
        db.add(ContactMapping(display_name=display_name, thread_id=thread_id, platform="xing"))
        existing.add((display_name, thread_id))
