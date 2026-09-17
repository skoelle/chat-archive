# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

from pydantic import BaseModel
from typing import Optional, List, Any


class RawThreadPayload(BaseModel):
    """Raw data as sent by the importer straight from a takeout thread JSON.
    Structure matches the Meta export 1:1 (participants[], messages[])."""
    thread_id: str
    raw_json: Any  # intentionally untyped, see app/parsers/*.py for the structure


class MessageOut(BaseModel):
    id: int
    platform: str
    thread_id: str
    sender_name: str
    timestamp_ms: int
    content: Optional[str]
    message_type: str

    class Config:
        from_attributes = True


class ImportResult(BaseModel):
    rows_inserted: int
    thread_id: str
