# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

from typing import Any

from pydantic import BaseModel


class RawThreadPayload(BaseModel):
    """Raw data as sent by the importer straight from a takeout thread JSON.
    Structure matches the Meta export 1:1 (participants[], messages[])."""
    thread_id: str
    raw_json: Any  # intentionally untyped, see app/parsers/*.py for the structure


class XingFile(BaseModel):
    """One raw CSV file of a XING data export."""
    path: str = ""
    content: str


class RawXingPayload(BaseModel):
    """All CSV files of a XING export in one request (messages, notes,
    contact dates). The importer does not parse them, the API classifies each
    file by its header row."""
    files: list[XingFile]


class MessageOut(BaseModel):
    id: int
    platform: str
    thread_id: str
    sender_name: str
    timestamp_ms: int
    content: str | None
    message_type: str
    reactions: list[dict] | None = None
    participant_count: int | None = None

    class Config:
        from_attributes = True


class ConversationResult(BaseModel):
    total: int
    offset: int
    limit: int
    messages: list[MessageOut]


class ImportResult(BaseModel):
    rows_inserted: int
    thread_id: str
    threads: int = 0  # only set for bulk imports (XING), 0 otherwise
