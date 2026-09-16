from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.auth import verify_api_key
from app.db import get_db
from app.models import Message
from app.schemas import MessageOut

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/messages", response_model=List[MessageOut])
def list_messages(
    platform: Optional[str] = None,
    thread_id: Optional[str] = None,
    sender_name: Optional[str] = None,
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
    return query.order_by(Message.timestamp_ms).limit(limit).all()


@router.get("/threads")
def list_threads(db: Session = Depends(get_db)):
    rows = (
        db.query(Message.thread_id, Message.platform)
        .distinct()
        .all()
    )
    return [{"thread_id": r[0], "platform": r[1]} for r in rows]
