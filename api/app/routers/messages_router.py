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


@router.get("/messages", response_model=List[MessageOut])
def list_messages(
    platform: Optional[str] = None,
    thread_id: Optional[str] = None,
    sender_name: Optional[str] = None,
    thread_type: ThreadType = Query(ThreadType.direct, description="all, direct (1:1), or group"),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(Message)
    if platform:
        query = query.filter(Message.platform == platform)
    if thread_id:
        query = query.filter(Message.thread_id == thread_id)
    if sender_name:
        query = query.filter(Message.sender_name == sender_name)
    query = _apply_thread_type(query, thread_type)
    return query.order_by(Message.timestamp_ms.desc()).limit(limit).all()


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
    offset: int = Query(0, ge=0),
    limit: int = Query(200, le=5000),
    db: Session = Depends(get_db),
):
    thread_ids = (
        db.query(Message.thread_id)
        .filter(Message.sender_name.in_(contact_names))
        .distinct()
        .all()
    )
    thread_ids = [r[0] for r in thread_ids]

    if not thread_ids:
        return ConversationResult(total=0, offset=offset, limit=limit, messages=[])

    query = db.query(Message).filter(Message.thread_id.in_(thread_ids))
    if platform:
        query = query.filter(Message.platform == platform)

    total = query.count()
    messages = (
        query
        .order_by(Message.timestamp_ms)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ConversationResult(total=total, offset=offset, limit=limit, messages=messages)
