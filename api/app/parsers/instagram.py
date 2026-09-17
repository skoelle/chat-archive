# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

"""
TODO: port the logic from reference/instagram-to-sqlite.
Clone command in docs/REFERENCE-PARSERS.md.

Expected input structure (raw_json, as found in
your_instagram_activity/messages/inbox/<thread>/message_1.json):

{
  "participants": [{"name": "..."}],
  "messages": [
    {
      "sender_name": "...",
      "timestamp_ms": 1690000000000,
      "content": "...",          # optional
      "photos": [...],           # optional
      "videos": [...],           # optional
      "audio_files": [...],      # optional
      "share": {...}             # optional
    }
  ]
}
"""
from app.parsers.encoding_fix import fix_mojibake


def parse_instagram_thread(thread_id: str, raw_json: dict) -> list[dict]:
    messages = []

    for msg in raw_json.get("messages", []):
        message_type = "text"
        if msg.get("photos"):
            message_type = "photo"
        elif msg.get("videos"):
            message_type = "video"
        elif msg.get("audio_files"):
            message_type = "audio"
        elif msg.get("share"):
            message_type = "share"

        messages.append({
            "thread_id": thread_id,
            "sender_name": fix_mojibake(msg.get("sender_name", "unknown")),
            "timestamp_ms": msg.get("timestamp_ms", 0),
            "content": fix_mojibake(msg.get("content")),
            "message_type": message_type,
            "reactions": _extract_reactions(msg.get("reactions", [])),
        })

    return messages


def _extract_reactions(raw_reactions: list) -> list[dict] | None:
    if not raw_reactions:
        return None
    return [
        {"actor": fix_mojibake(r.get("actor", "")), "reaction": fix_mojibake(r.get("reaction", ""))}
        for r in raw_reactions
    ]
