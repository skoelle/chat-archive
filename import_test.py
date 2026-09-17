#!/usr/bin/env python3
"""Direct-to-DB import test.

Reads extracted takeout JSONs from .tmp/, parses them with the API parsers,
and inserts directly into MariaDB. Bypasses the API and Tauri entirely.

Usage:
    python import_test.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

DB_HOST = os.getenv("MYSQL_HOST", "mariadb.fritz.box")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASS = os.getenv("MYSQL_PASSWORD", "direct0r")
DB_NAME = os.getenv("MYSQL_DATABASE", "chatarchive")

TMP_DIR = Path(__file__).parent / ".tmp"

# Add api/ to path so we can import the parsers
sys.path.insert(0, str(Path(__file__).parent / "api"))
from app.parsers.instagram import parse_instagram_thread
from app.parsers.facebook import parse_facebook_thread
from app.parsers.facebook_e2ee import parse_facebook_e2ee_thread
from app.models import Message, Base


def get_db():
    url = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    engine = create_engine(url, pool_pre_ping=True)
    # Drop and recreate to pick up schema changes (e.g. new columns)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def collect_threads(extracted_path: Path, platform: str):
    """Walk extracted directory, group JSON files by parent dir, return threads."""
    from collections import defaultdict

    groups = defaultdict(list)

    for p in extracted_path.rglob("*.json"):
        path_str = str(p)

        # Platform-specific filters
        if platform == "instagram" and "/messages/inbox/" not in path_str:
            continue
        if platform == "facebook":
            if "/messages/message_requests/" in path_str:
                continue
            if "/messages/filtered_threads/" in path_str:
                continue

        parent = p.parent
        groups[parent].append(p)

    threads = []
    for parent, files in groups.items():
        has_message_files = any(f.name.startswith("message_") for f in files)

        if has_message_files:
            # Instagram / Facebook normal: combine split files
            thread_id = parent.name
            combined_messages = []
            participants = None
            for f in files:
                data = json.loads(f.read_text(encoding="utf-8"))
                if participants is None:
                    participants = data.get("participants")
                combined_messages.extend(data.get("messages", []))
            combined = {"messages": combined_messages}
            if participants:
                combined["participants"] = participants
            threads.append((thread_id, combined))
        else:
            # Facebook E2EE: each file is its own thread
            for f in files:
                data = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "messages" not in data:
                    continue
                thread_id = f.stem
                threads.append((thread_id, data))

    return threads


def persist(db, platform: str, thread_id: str, parsed: list[dict]):
    db.query(Message).filter(
        Message.platform == platform,
        Message.thread_id == thread_id,
    ).delete()
    for item in parsed:
        db.add(Message(platform=platform, **item))
    db.commit()
    return len(parsed)


def run():
    db = get_db()
    total_threads = 0
    total_rows = 0

    platforms = [
        ("insta", "instagram", parse_instagram_thread),
        ("fb-normal", "facebook", parse_facebook_thread),
        ("fb-e2ee", "facebook", parse_facebook_e2ee_thread),
    ]

    for dir_name, platform, parser in platforms:
        extracted = TMP_DIR / dir_name
        if not extracted.exists():
            print(f"[{platform}] {extracted} not found, skipping")
            continue

        threads = collect_threads(extracted, platform)
        print(f"[{platform}] {len(threads)} threads found")

        for thread_id, raw_json in threads:
            parsed = parser(thread_id, raw_json)
            rows = persist(db, platform, thread_id, parsed)
            total_threads += 1
            total_rows += rows
            print(f"  {thread_id}: {rows} messages")

    print(f"\nDone: {total_threads} threads, {total_rows} messages total")
    db.close()


if __name__ == "__main__":
    run()
