# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

"""
TODO: port the logic from reference/facebook-message-parser.
Clone command in docs/REFERENCE-PARSERS.md.

Important: long Facebook threads are split across multiple files
(message_1.json, message_2.json, ...). The importer sends each file
separately with the same thread_id, so the API just needs to associate them
by thread_id (fine, since messages are stored per row, not per thread
object).

Input structure is structurally identical to Instagram (participants[],
messages[] with sender_name, timestamp_ms, content), Meta uses the same
base format for both platforms.
"""
from app.parsers.encoding_fix import fix_mojibake


def parse_facebook_thread(thread_id: str, raw_json: dict) -> list[dict]:
    messages = []
    participant_count = len(raw_json.get("participants", [])) or None

    for msg in raw_json.get("messages", []):
        message_type = "text"
        if msg.get("photos"):
            message_type = "photo"
        elif msg.get("videos"):
            message_type = "video"
        elif msg.get("audio_files") or msg.get("audio"):
            message_type = "audio"
        elif msg.get("share"):
            message_type = "share"

        messages.append({
            "thread_id": thread_id,
            "sender_name": fix_mojibake(msg.get("sender_name", "unknown")),
            "timestamp_ms": msg.get("timestamp_ms", 0),
            "content": fix_mojibake(msg.get("content")),
            "message_type": message_type,
            "participant_count": participant_count,
        })

    return messages
