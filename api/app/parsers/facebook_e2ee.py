# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

"""
Parser for Facebook E2EE (end-to-end encrypted) takeout exports.

E2EE exports use camelCase field names and a different message structure
compared to the standard Facebook/Instagram takeout format.

Input structure:
{
  "participants": ["Name1", "Name2"],
  "threadName": "...",
  "messages": [
    {
      "isUnsent": false,
      "media": [{"uri": "./media/uuid.jpeg"}],
      "reactions": [{"actor": "Name", "reaction": "❤"}],
      "senderName": "...",
      "text": "...",
      "timestamp": 1715160207074,
      "type": "text" | "media" | "link"
    }
  ]
}
"""
from app.parsers.encoding_fix import fix_mojibake


def parse_facebook_e2ee_thread(thread_id: str, raw_json: dict) -> list[dict]:
    messages = []

    for msg in raw_json.get("messages", []):
        if msg.get("isUnsent"):
            continue

        message_type = _detect_message_type(msg)

        content = msg.get("text") or None
        if content:
            content = fix_mojibake(content)

        messages.append({
            "thread_id": thread_id,
            "sender_name": fix_mojibake(msg.get("senderName", "unknown")),
            "timestamp_ms": msg.get("timestamp", 0),
            "content": content,
            "message_type": message_type,
        })

    return messages


def _detect_message_type(msg: dict) -> str:
    raw_type = msg.get("type", "text")

    if raw_type == "link":
        return "share"

    if raw_type == "media":
        media_list = msg.get("media", [])
        if media_list:
            uri = media_list[0].get("uri", "").lower()
            if uri.endswith((".jpeg", ".jpg", ".png", ".gif", ".webp")):
                return "photo"
            if uri.endswith((".mp4", ".mov", ".avi")):
                return "video"
            if uri.endswith((".mp3", ".wav", ".ogg", ".m4a")):
                return "audio"
        return "photo"

    return "text"
