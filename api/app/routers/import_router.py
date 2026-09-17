# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.db import get_db
from app.models import Message
from app.schemas import RawThreadPayload, ImportResult
from app.parsers.instagram import parse_instagram_thread
from app.parsers.facebook import parse_facebook_thread

router = APIRouter(prefix="/import", dependencies=[Depends(verify_api_key)])


@router.post("/instagram", response_model=ImportResult)
def import_instagram(payload: RawThreadPayload, db: Session = Depends(get_db)):
    parsed = parse_instagram_thread(payload.thread_id, payload.raw_json)
    return _persist(db, "instagram", payload.thread_id, parsed)


@router.post("/facebook", response_model=ImportResult)
def import_facebook(payload: RawThreadPayload, db: Session = Depends(get_db)):
    parsed = parse_facebook_thread(payload.thread_id, payload.raw_json)
    return _persist(db, "facebook", payload.thread_id, parsed)


def _persist(db: Session, platform: str, thread_id: str, parsed: list[dict]) -> ImportResult:
    for item in parsed:
        db.add(Message(platform=platform, **item))
    db.commit()
    return ImportResult(rows_inserted=len(parsed), thread_id=thread_id)
