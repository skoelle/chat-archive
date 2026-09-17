# AGENTS.md

## Project overview

`chat-archive` is a two-component system for importing Instagram and Facebook
takeout chat exports into a searchable MySQL/MariaDB database, with a REST API
for further analysis.

## Architecture

```
chat-archive/
├── api/        Python/FastAPI service ("chat-archive-api")
│               Receives raw takeout JSON, parses it, writes to MySQL/MariaDB,
│               exposes REST endpoints for querying. Runs on port 8420.
├── importer/   Tauri v2 desktop tool ("takeout-message-importer")
│               Extracts takeout ZIPs locally and forwards raw JSON to the API.
│               Contains NO parsing or DB logic.
└── docs/       Reference parser projects (clone instructions, not dependencies).
```

## Key files

### api/

| File | Purpose |
|---|---|
| `app/main.py` | FastAPI entrypoint, mounts routers, runs `create_all` on startup |
| `app/models.py` | SQLAlchemy `Message` model (single table: `messages`) |
| `app/schemas.py` | Pydantic schemas: `RawThreadPayload`, `MessageOut`, `ImportResult` |
| `app/config.py` | Settings from `.env` via pydantic-settings (MySQL creds, API token) |
| `app/db.py` | SQLAlchemy engine, session factory, `get_db()` dependency |
| `app/auth.py` | API key verification (`X-API-Key` header) |
| `app/parsers/instagram.py` | Instagram thread JSON parser |
| `app/parsers/facebook.py` | Facebook thread JSON parser |
| `app/parsers/encoding_fix.py` | Mojibake fix (UTF-8 misinterpreted as Latin-1 by Meta) |
| `app/routers/import_router.py` | `POST /import/instagram` and `/import/facebook` endpoints |
| `app/routers/messages_router.py` | `GET /messages` and `GET /threads` query endpoints |

### importer/

| File | Purpose |
|---|---|
| `src-tauri/src/extractor.rs` | ZIP extraction to temp directory |
| `src-tauri/src/api_client.rs` | HTTP forwarding of extracted JSON to the API |
| `src-tauri/src/commands.rs` | Tauri command handlers (extract, forward, test connection) |
| `src/main.js` | Frontend: dropzones, API config, import orchestration |

## Data model

Single table `messages`:
- `id` (BigInteger, PK, auto-increment)
- `platform` (String: `instagram` | `facebook`)
- `thread_id` (String, indexed)
- `sender_name` (String, indexed)
- `timestamp_ms` (BigInteger)
- `content` (Text, nullable)
- `message_type` (String: `text` | `photo` | `video` | `audio` | `share`)
- `reactions` (JSON, nullable: `[{"actor": "Name", "reaction": "❤"}]`)
- `participant_count` (Integer, nullable: number of participants in thread)

## API endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/import/instagram` | X-API-Key | Parse and store Instagram thread |
| POST | `/import/facebook` | X-API-Key | Parse and store Facebook thread |
| POST | `/import/facebook-e2ee` | X-API-Key | Parse and store Facebook E2EE thread |
| GET | `/messages` | X-API-Key | Query messages (default: 1:1 chats) |
| GET | `/threads` | X-API-Key | List distinct threads (default: 1:1 chats) |
| GET | `/conversation` | X-API-Key | Merged conversation across platforms |
| GET | `/health` | none | Health check |

`/messages` and `/threads` accept `?thread_type=direct|group|all` (default:
`direct` = 1:1 chats with exactly 2 participants).

`/messages` also accepts `?order=asc|desc` (default: `asc` = oldest first).

## Environment variables (api/.env)

```
API_TOKEN=your-secret-token
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=secret
MYSQL_DATABASE=chat_archive
```

## Setup & run

### API

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in credentials
uvicorn app.main:app --host 0.0.0.0 --port 8420
```

### Importer (dev)

```bash
cd importer
npm install
npm run tauri dev
```

### Importer (build)

```bash
cd importer
npm run tauri build
```

## Important notes

- The API does NOT run behind Authelia — the Tauri client is a plain HTTP client
  without browser sessions. Auth is a static API token via `X-API-Key` header.
- Long Facebook threads are split across multiple JSON files by Meta. The importer
  combines all `message_*.json` files in a thread directory into a single request.
- Import is idempotent: the API deletes all messages for a `(thread_id, platform)`
  before inserting new ones, so re-importing replaces the old data.
- The `encoding_fix.py` module handles Meta's mojibake bug (UTF-8 bytes
  misinterpreted as Latin-1). This must be applied to all string values
  (`sender_name`, `content`) from both platforms.
- Instagram and Facebook parsers are structurally identical — Meta uses the same
  JSON format for both takeout exports.
- Instagram import only processes `messages/inbox/` (excludes message_requests,
  broadcast). Facebook import excludes `message_requests/` and `filtered_threads/`.
- Facebook E2EE: each `.json` file is a standalone thread. Non-thread files
  (settings, metadata) are skipped by checking for a `messages` key.
- `participant_count` is stored per message and used to filter threads:
  `?thread_type=direct` (2 participants), `?thread_type=group` (>2), `?thread_type=all`.
- `import_test.py` is a standalone script for testing the full parse+DB pipeline
  directly against MariaDB, bypassing the API. It drops and recreates the table
  on each run. Uses `.env` for credentials (already gitignored).

## License

MIT License - Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
- Full text in `LICENSE`
- License headers in all source code files
