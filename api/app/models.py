from sqlalchemy import Column, BigInteger, String, Text, Index

from app.db import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False)          # instagram | facebook
    thread_id = Column(String(255), nullable=False)
    sender_name = Column(String(255), nullable=False)
    timestamp_ms = Column(BigInteger, nullable=False)
    content = Column(Text, nullable=True)
    message_type = Column(String(20), nullable=False)      # text | photo | video | audio | share

    __table_args__ = (
        Index("idx_thread", "thread_id"),
        Index("idx_sender", "sender_name"),
        Index("idx_platform", "platform"),
    )
