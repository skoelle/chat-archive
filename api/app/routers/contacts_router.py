# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.config import settings
from app.db import get_db
from app.models import ContactMapping, Message
from app.parsers.common import fold_name

router = APIRouter(prefix="/contacts", dependencies=[Depends(verify_api_key)])


class ContactMappingCreate(BaseModel):
    display_name: str
    thread_id: str
    platform: Optional[str] = None


class ContactMappingOut(BaseModel):
    id: int
    display_name: str
    thread_id: str
    platform: str | None

    class Config:
        from_attributes = True


class ContactInteractionOut(BaseModel):
    name: str
    message_count: int


@router.get("/top", response_model=list[ContactInteractionOut])
def top_contacts(
    platform: Optional[str] = None,
    limit: int = Query(50, le=1000),
    db: Session = Depends(get_db),
):
    """Contacts ranked by the number of messages they sent me in 1:1 chats.

    Only direct chats (participant_count == 2) and only received messages are
    counted (my own messages are excluded). Sender names are resolved via
    contact_mappings (thread_id -> display_name), so a nickname like "mareikija"
    shows up as its real name. Names that fold to the same value (umlaut/case)
    are merged and the most frequent spelling is shown.
    """
    query = db.query(
        Message.thread_id,
        Message.sender_name,
        func.count(Message.id).label("message_count"),
    ).filter(
        Message.participant_count == 2,
    ).group_by(Message.thread_id, Message.sender_name)
    if platform:
        query = query.filter(Message.platform == platform)

    own = fold_name(settings.own_name)

    display_by_thread: dict[str, str] = {}
    for thread_id, display_name in db.query(
        ContactMapping.thread_id, ContactMapping.display_name
    ).all():
        display_by_thread.setdefault(thread_id, display_name)

    aggregated: dict[str, dict] = {}
    for thread_id, sender_name, count in query.all():
        if own and fold_name(sender_name) == own:
            continue
        name = display_by_thread.get(thread_id) or sender_name
        key = fold_name(name)
        entry = aggregated.setdefault(key, {"names": {}, "message_count": 0})
        entry["names"][name] = entry["names"].get(name, 0) + count
        entry["message_count"] += count

    ranking = [
        {
            "name": max(entry["names"], key=entry["names"].get),
            "message_count": entry["message_count"],
        }
        for entry in aggregated.values()
    ]
    ranking.sort(key=lambda row: (-row["message_count"], fold_name(row["name"])))
    return ranking[:limit]


@router.get("/", response_model=list[ContactMappingOut])
def list_mappings(db: Session = Depends(get_db)):
    return db.query(ContactMapping).all()


@router.post("/", response_model=ContactMappingOut, status_code=201)
def create_mapping(payload: ContactMappingCreate, db: Session = Depends(get_db)):
    mapping = ContactMapping(**payload.model_dump())
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@router.delete("/{mapping_id}")
def delete_mapping(mapping_id: int, db: Session = Depends(get_db)):
    mapping = db.query(ContactMapping).get(mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    db.delete(mapping)
    db.commit()
    return {"deleted": True}
