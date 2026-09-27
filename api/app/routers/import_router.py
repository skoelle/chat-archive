# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.bulk_store import store_bulk
from app.config import settings
from app.db import get_db
from app.models import Message
from app.parsers.facebook import parse_facebook_thread
from app.parsers.facebook_e2ee import parse_facebook_e2ee_thread
from app.parsers.instagram import parse_instagram_thread
from app.parsers.linkedin import parse_linkedin_files
from app.parsers.xing import parse_xing_files
from app.schemas import ImportResult, RawCsvPayload, RawThreadPayload

router = APIRouter(prefix="/import", dependencies=[Depends(verify_api_key)])


@router.post("/instagram", response_model=ImportResult)
def import_instagram(payload: RawThreadPayload, db: Session = Depends(get_db)):
    parsed = parse_instagram_thread(payload.thread_id, payload.raw_json)
    return _persist(db, "instagram", payload.thread_id, parsed)


@router.post("/facebook", response_model=ImportResult)
def import_facebook(payload: RawThreadPayload, db: Session = Depends(get_db)):
    parsed = parse_facebook_thread(payload.thread_id, payload.raw_json)
    return _persist(db, "facebook", payload.thread_id, parsed)


@router.post("/facebook-e2ee", response_model=ImportResult)
def import_facebook_e2ee(payload: RawThreadPayload, db: Session = Depends(get_db)):
    parsed = parse_facebook_e2ee_thread(payload.thread_id, payload.raw_json)
    return _persist(db, "facebook-e2ee", payload.thread_id, parsed)


@router.post("/xing", response_model=ImportResult)
def import_xing(payload: RawCsvPayload, db: Session = Depends(get_db)):
    """Bulk import of a XING data export (messages CSV + network-inquiry CSVs).

    Only the file kinds present in the payload are replaced: conversations
    live in threads prefixed `xing_`, contact notes in `xing-notiz-`.
    """
    result = parse_xing_files(
        [f.model_dump() for f in payload.files],
        own_name=settings.own_name,
    )
    rows, threads = store_bulk(db, "xing", result)
    return ImportResult(rows_inserted=rows, thread_id="xing", threads=threads)


@router.post("/linkedin", response_model=ImportResult)
def import_linkedin(payload: RawCsvPayload, db: Session = Depends(get_db)):
    """Bulk import of a LinkedIn data export (messages.csv + Notes.csv +
    Connections.csv; every other CSV in the payload is ignored).

    Only the file kinds present in the payload are replaced: conversations
    live in threads prefixed `linkedin_`, contact notes in `linkedin-notiz-`.
    Spam messages (FOLDER=SPAM) are dropped by the parser.
    """
    result = parse_linkedin_files(
        [f.model_dump() for f in payload.files],
        own_name=settings.own_name,
    )
    rows, threads = store_bulk(db, "linkedin", result)
    return ImportResult(rows_inserted=rows, thread_id="linkedin", threads=threads)


def _persist(db: Session, platform: str, thread_id: str, parsed: list[dict]) -> ImportResult:
    db.query(Message).filter(
        Message.platform == platform,
        Message.thread_id == thread_id,
    ).delete()
    for item in parsed:
        db.add(Message(platform=platform, **item))
    db.commit()
    return ImportResult(rows_inserted=len(parsed), thread_id=thread_id)
