# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.db import get_db
from app.models import Message
from app.schemas import ConversationResult, MessageOut

router = APIRouter(dependencies=[Depends(verify_api_key)])

UMAP = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})


def _normalize(text: str) -> str:
    return text.translate(UMAP)


class ThreadType(str, Enum):
    all = "all"
    direct = "direct"
    group = "group"


def _apply_thread_type(query, thread_type: ThreadType):
    if thread_type == ThreadType.direct:
        query = query.filter(Message.participant_count == 2)
    elif thread_type == ThreadType.group:
        query = query.filter(Message.participant_count > 2)
    return query


def _apply_name_search(query, column, name: str):
    """Search by name with umlaut normalization (ü matches ue, etc.)."""
    from sqlalchemy import or_
    norm = _normalize(name)
    if norm != name:
        return query.filter(or_(column.like(f"%{name}%"), column.like(f"%{norm}%")))
    return query.filter(column.like(f"%{name}%"))


@router.get("/messages", response_model=List[MessageOut])
def list_messages(
    platform: Optional[str] = None,
    thread_id: Optional[str] = None,
    sender_name: Optional[str] = None,
    thread_type: ThreadType = Query(ThreadType.direct, description="all, direct (1:1), or group"),
    limit: int = Query(100, le=1000),
    order: str = Query("asc", description="asc (oldest first) or desc (newest first)"),
    db: Session = Depends(get_db),
):
    query = db.query(Message)
    if platform:
        query = query.filter(Message.platform == platform)
    if thread_id:
        query = query.filter(Message.thread_id == thread_id)
    if sender_name:
        query = _apply_name_search(query, Message.sender_name, sender_name)
    query = _apply_thread_type(query, thread_type)
    order_col = Message.timestamp_ms.desc() if order == "desc" else Message.timestamp_ms.asc()
    return query.order_by(order_col).limit(limit).all()


@router.get("/threads")
def list_threads(
    thread_type: ThreadType = Query(ThreadType.direct, description="all, direct (1:1), or group"),
    db: Session = Depends(get_db),
):
    query = db.query(
        Message.thread_id,
        Message.platform,
        Message.participant_count,
    ).distinct()
    query = _apply_thread_type(query, thread_type)
    rows = query.all()
    return [{"thread_id": r[0], "platform": r[1], "participant_count": r[2]} for r in rows]


@router.get("/conversation", response_model=ConversationResult)
def get_conversation(
    contact_names: list[str] = Query(..., description="Name(s) of the contact (same person across platforms)"),
    platform: Optional[str] = None,
    thread_type: ThreadType = Query(ThreadType.direct, description="all, direct (1:1), or group"),
    order: str = Query("asc", description="asc (oldest first) or desc (newest first)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, le=5000),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_
    name_conditions = []
    for name in contact_names:
        norm = _normalize(name)
        if norm != name:
            name_conditions.append(or_(
                Message.sender_name.like(f"%{name}%"),
                Message.sender_name.like(f"%{norm}%"),
            ))
        else:
            name_conditions.append(Message.sender_name.like(f"%{name}%"))
    thread_query = (
        db.query(Message.thread_id)
        .filter(or_(*name_conditions))
    )
    thread_query = _apply_thread_type(thread_query, thread_type)
    thread_ids = [r[0] for r in thread_query.distinct().all()]

    if not thread_ids:
        return ConversationResult(total=0, offset=offset, limit=limit, messages=[])

    query = db.query(Message).filter(Message.thread_id.in_(thread_ids))
    if platform:
        query = query.filter(Message.platform == platform)

    total = query.count()
    order_col = Message.timestamp_ms.desc() if order == "desc" else Message.timestamp_ms.asc()
    messages = (
        query
        .order_by(order_col)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ConversationResult(total=total, offset=offset, limit=limit, messages=messages)
