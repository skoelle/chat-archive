# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

from sqlalchemy import BigInteger, Column, Index, Integer, String, Text

from app.db import Base
from app.types import JSONList


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False)          # instagram | facebook
    thread_id = Column(String(255), nullable=False)
    sender_name = Column(String(255), nullable=False)
    timestamp_ms = Column(BigInteger, nullable=False)
    content = Column(Text, nullable=True)
    message_type = Column(String(20), nullable=False)      # text | photo | video | audio | share
    reactions = Column(JSONList, nullable=True)              # [{"actor": "...", "reaction": "..."}]
    participant_count = Column(Integer, nullable=True)       # number of participants in thread

    __table_args__ = (
        Index("idx_thread", "thread_id"),
        Index("idx_sender", "sender_name"),
        Index("idx_platform", "platform"),
    )


class ContactMapping(Base):
    """Maps display names (e.g. 'Mareike Wüste') to thread_ids
    (e.g. 'mareikija_525260105537291') for cross-platform contact resolution."""
    __tablename__ = "contact_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    display_name = Column(String(255), nullable=False)     # real name, e.g. "Mareike Wüste"
    thread_id = Column(String(255), nullable=False)        # thread_id in messages table
    platform = Column(String(20), nullable=True)            # instagram | facebook | null (any)

    __table_args__ = (
        Index("idx_mapping_display", "display_name"),
        Index("idx_mapping_thread", "thread_id"),
    )
