# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

"""Persistence for bulk CSV imports (XING, LinkedIn).

Shared by POST /import/<platform> and import_test.py, so both use exactly the
same delete-by-prefix rules. The thread_id prefixes are the only thing that
tells conversations (`<platform>_...`) apart from contact notes
(`<platform>-notiz-...`), so every prefix must be passed with autoescape=True:
without it the `_` of `linkedin_` is a SQL LIKE wildcard and would also match
`linkedin-notiz-...` (and delete the contact notes with the conversations).
"""

from sqlalchemy.orm import Session

from app.models import ContactMapping, Message
from app.parsers.common import BulkParseResult


def store_bulk(db: Session, platform: str, result: BulkParseResult) -> tuple[int, int]:
    """(Re-)import the parsed files of one platform.

    Only the file kinds present in the payload are replaced: a payload without
    the messages CSV leaves the conversations untouched, and vice versa.
    Returns (rows_inserted, threads).
    """
    if "messages" in result.kinds:
        db.query(Message).filter(
            Message.platform == platform,
            Message.thread_id.startswith(f"{platform}_", autoescape=True),
        ).delete(synchronize_session=False)

    if result.kinds & {"notes", "contacts"}:
        db.query(Message).filter(
            Message.platform == platform,
            Message.thread_id.startswith(f"{platform}-notiz-", autoescape=True),
        ).delete(synchronize_session=False)

    rows = result.messages + result.notes
    for item in rows:
        db.add(Message(platform=platform, **item))

    _store_mappings(db, platform, result.mappings)
    db.commit()

    return len(rows), len({row["thread_id"] for row in rows})


def _store_mappings(db: Session, platform: str, mappings: list[tuple[str, str]]):
    """Create missing contact_mappings so /conversation finds the threads of a
    platform by contact name, even when a thread only contains messages I
    sent myself."""
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
        db.add(ContactMapping(display_name=display_name, thread_id=thread_id, platform=platform))
        existing.add((display_name, thread_id))
