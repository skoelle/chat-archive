# chat-archive-api

FastAPI service that receives takeout JSON from the Tauri importer, parses
it, and writes it to MySQL/MariaDB. Also exposes read endpoints for later
analysis.

## Setup

```bash
cd api
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill in API_TOKEN, MySQL credentials, OWN_NAME
uvicorn app.main:app --host 0.0.0.0 --port 8420
```

## Deploy as a Docker container (recommended: Debian docker host)

```bash
docker build -t chat-archive-api .
docker run -d --name chat-archive-api \
  --env-file .env \
  -p 8420:8420 \
  chat-archive-api
```

## Data model

### `messages`

| Column | Type | Description |
|---|---|---|
| `id` | BigInteger, PK | Auto-increment |
| `platform` | String | `instagram` \| `facebook` \| `xing` \| `linkedin` |
| `thread_id` | String, indexed | Folder name from takeout ZIP, `xing_<...>` / `xing-notiz-<...>` for XING, `linkedin_<...>` / `linkedin-notiz-<...>` for LinkedIn |
| `sender_name` | String, indexed | Who sent the message |
| `timestamp_ms` | BigInteger | Unix timestamp in milliseconds |
| `content` | Text, nullable | Message text (null for photos/videos) |
| `message_type` | String | `text` \| `photo` \| `video` \| `audio` \| `share` |
| `reactions` | JSON, nullable | `[{"actor": "Name", "reaction": "❤"}]` |
| `participant_count` | Integer, nullable | Number of participants in thread (2 = 1:1 chat) |

### `contact_mappings`

Maps display names to thread_ids for cross-platform contact resolution.

| Column | Type | Description |
|---|---|---|
| `id` | Integer, PK | Auto-increment |
| `display_name` | String, indexed | Real name, e.g. "Jane Doe" |
| `thread_id` | String, indexed | Thread ID in messages table |
| `platform` | String, nullable | `instagram` \| `facebook` \| `xing` \| `linkedin` \| null (any) |

### Message object

```json
{
  "id": 1234,
  "platform": "facebook",
  "thread_id": "john-doe_123456789",
  "sender_name": "John Doe",
  "timestamp_ms": 1715160207074,
  "content": "Hey, wanna grab lunch?",
  "message_type": "text",
  "reactions": [
    {"actor": "Jane Smith", "reaction": "❤"},
    {"actor": "John Doe", "reaction": "😂"}
  ],
  "participant_count": 2
}
```

`reactions` is `null` when no reactions exist. When present, it is an array
of objects with `actor` (who reacted) and `reaction` (the emoji).

## Endpoints

### Import

| Method | Path | Purpose |
|---|---|---|
| POST | /import/instagram | Accepts raw Instagram thread JSON, parses, stores |
| POST | /import/facebook | Accepts raw Facebook (standard) thread JSON, parses, stores |
| POST | /import/facebook-e2ee | Accepts raw Facebook E2EE thread JSON, parses, stores |
| POST | /import/xing | Accepts all CSV files of a XING data export, parses, stores |
| POST | /import/linkedin | Accepts all CSV files of a LinkedIn data export, parses, stores |

The Meta endpoints (instagram, facebook, facebook-e2ee) accept a JSON body:
```json
{
  "thread_id": "john-doe_123456789",
  "raw_json": { ... }
}
```

The `thread_id` is derived from the folder name inside the takeout ZIP.
The importer sends each JSON file found in the extracted ZIP automatically.

#### XING (bulk import)

`POST /import/xing` receives every CSV file of the export in a single request
and classifies them by header row (`messages` / `notes` / `contacts`):

```json
{
  "files": [
    { "path": "data/messages-backend/files/<hash>.csv", "content": "..." },
    { "path": "data/network-inquiry/files/<hash>.csv", "content": "..." }
  ]
}
```

Thread ids: conversations `xing_<slug(subject)>_<hash8>`, contact notes
`xing-notiz-<slug(name)>`. The import replaces the previously stored XING data
of every file kind present in the payload (kind-scoped, so a payload with only
the messages CSV leaves the notes untouched) and creates `contact_mappings`
for every resolvable contact.

#### LinkedIn (bulk import)

`POST /import/linkedin` uses the same `files` payload as XING and classifies
each CSV by header row. Relevant files:

| File | Content |
|---|---|
| `messages.csv` | 1:1 and group conversations; `SUBJECT` becomes a leading `Betreff:` line, `ATTACHMENTS` are appended as `(Anhang: <url>)`, `FOLDER=SPAM` rows are dropped |
| `Connections.csv` | 3 free-text preamble lines, then one synthetic thread per connection (`linkedin-notiz-<slug>`, "Verbunden am <date>" + company/position/profile URL) |
| `Notes.csv` | connection notes (usually empty) |

Every other CSV of the export (profile, ads, shares, reactions, ...) is
ignored. Thread ids: conversations
`linkedin_<slug(CONVERSATION TITLE|gegenüber)>_<sha1(conversation id)[:8]>`,
notes/contacts `linkedin-notiz-<slug(name)>`. Placeholder senders
(`LinkedIn Member`, `LinkedIn for Learning`) are stored as `sender_name` but do
not create `contact_mappings`.

#### Import response

```json
{
  "rows_inserted": 42,
  "thread_id": "john-doe_123456789"
}
```

XING and LinkedIn additionally return `threads` (number of threads written,
bulk import): `{"rows_inserted": 1049, "thread_id": "linkedin", "threads": 696}`

### Query

| Method | Path | Purpose |
|---|---|---|
| GET | /messages | Query individual messages with filters |
| GET | /threads | List all imported threads |
| GET | /conversation | Merged conversation across platforms |
| GET | /contacts/top | Contacts ranked by received messages |
| GET | /contacts/ | List all contact mappings |
| POST | /contacts/ | Create contact mapping |
| DELETE | /contacts/{id} | Delete contact mapping |

#### GET /messages

Filter messages by platform, thread, or sender.

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| platform | str | no | Filter by platform (`instagram`, `facebook`, `xing`, `linkedin`) |
| thread_id | str | no | Filter by thread ID |
| sender_name | str | no | Filter by sender name (LIKE search with umlaut normalization) |
| thread_type | str | no | `direct` (default), `group`, or `all` |
| order | str | no | `asc` (default, oldest first) or `desc` (newest first) |
| limit | int | no | Max messages (default: 100, max: 1000) |

**Examples:**

```bash
# All 1:1 messages with John Doe
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/messages?sender_name=John+Doe"

# Group chats only, newest first
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/messages?thread_type=group&order=desc"

# Facebook messages from a specific thread
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/messages?platform=facebook&thread_id=john-doe_123456789"
```

**Response:**

```json
[
  {
    "id": 1234,
    "platform": "facebook",
    "thread_id": "john-doe_123456789",
    "sender_name": "John Doe",
    "timestamp_ms": 1715160207074,
    "content": "Hey, wanna grab lunch?",
    "message_type": "text",
    "reactions": null,
    "participant_count": 2
  }
]
```

#### GET /threads

Returns a list of all distinct `thread_id` + `platform` combinations.

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| thread_type | str | no | `direct` (default), `group`, or `all` |
| platform | str | no | Filter by platform (`instagram`, `facebook`, `xing`, `linkedin`) |

**Example:**

```bash
# Only 1:1 threads
curl -H "X-API-Key: $TOKEN" "http://localhost:8420/threads"

# All threads including groups
curl -H "X-API-Key: $TOKEN" "http://localhost:8420/threads?thread_type=all"

# Only LinkedIn threads
curl -H "X-API-Key: $TOKEN" "http://localhost:8420/threads?platform=linkedin"
```

**Response:**

```json
[
  {"thread_id": "john-doe_123456789", "platform": "facebook", "participant_count": 2},
  {"thread_id": "jane-smith_987654321", "platform": "instagram", "participant_count": 2}
]
```

#### GET /conversation

Retrieve a merged conversation with a specific contact across one or more
platforms. Searches by `sender_name` AND by `contact_mappings` table (allows
mapping display names like "Jane Doe" to thread_ids where sender_name
differs).

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| contact_names | list[str] | yes | Name(s) of the contact (same person across platforms) |
| platform | str | no | Filter to a specific platform (`instagram`, `facebook`, `xing`, `linkedin`) |
| thread_type | str | no | `direct` (default), `group`, or `all` |
| order | str | no | `asc` (default, oldest first) or `desc` (newest first) |
| offset | int | no | Pagination offset (default: 0) |
| limit | int | no | Max messages to return (default: 200, max: 5000) |

**Examples:**

```bash
# All 1:1 messages with John Doe
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/conversation?contact_names=John+Doe"

# Include group chats
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/conversation?contact_names=John+Doe&thread_type=all"

# Only Facebook messages
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/conversation?contact_names=John+Doe&platform=facebook"

# Cross-platform: same person may have different names
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/conversation?contact_names=John+Doe&contact_names=john.doe"

# Newest first
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/conversation?contact_names=John+Doe&order=desc"
```

**Response:**

```json
{
  "total": 347,
  "offset": 0,
  "limit": 200,
  "messages": [
    {
      "id": 1234,
      "platform": "facebook",
      "thread_id": "john-doe_123456789",
      "sender_name": "John Doe",
      "timestamp_ms": 1715160207074,
      "content": "Hey, wanna grab lunch?",
      "message_type": "text",
      "reactions": null,
      "participant_count": 2
    },
    {
      "id": 1235,
      "platform": "instagram",
      "thread_id": "jane-smith_987654321",
      "sender_name": "Jane Smith",
      "timestamp_ms": 1715160300000,
      "content": "Sure, sounds great!",
      "message_type": "text",
      "reactions": [
        {"actor": "John Doe", "reaction": "❤"}
      ],
      "participant_count": 2
    },
    {
      "id": 1236,
      "platform": "facebook",
      "thread_id": "john-doe_123456789",
      "sender_name": "John Doe",
      "timestamp_ms": 1715200000000,
      "content": null,
      "message_type": "photo",
      "reactions": [
        {"actor": "Jane Smith", "reaction": "😍"},
        {"actor": "John Doe", "reaction": "👍"}
      ],
      "participant_count": 2
    }
  ]
}
```

### Contact Mappings

Manage display name → thread_id mappings for cross-platform contact resolution.

| Method | Path | Purpose |
|---|---|---|
| GET | /contacts/ | List all mappings |
| POST | /contacts/ | Add a new mapping |
| DELETE | /contacts/{id} | Delete a single mapping by ID |

#### GET /contacts/top

Contacts ranked by the number of messages they sent you in **1:1 chats**
(group threads are ignored). Only received messages are counted (your own
messages are excluded), and sender names are resolved via `contact_mappings`
(thread_id → display name), so a nickname like `jdoe_123` shows up as
`Jane Doe`. Names that fold to the same value (umlaut/case) are merged.

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| platform | str | no | Filter by platform (`instagram`, `facebook`, `xing`, `linkedin`) |
| limit | int | no | Max contacts to return (default: 50, max: 1000) |

**Example:**

```bash
curl -H "X-API-Key: $TOKEN" "http://localhost:8420/contacts/top?limit=10"
```

**Response:**

```json
[
  {"name": "Jane Doe", "message_count": 4218},
  {"name": "John Doe", "message_count": 1337}
]
```

#### POST /contacts/

Adds a new mapping. Multiple mappings per display_name are allowed (e.g. same
person on Instagram + Facebook).

#### POST /contacts/

```bash
curl -X POST -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d '{"display_name": "Jane Doe", "thread_id": "janedoe_394923402", "platform": "instagram"}' \
  "http://localhost:8420/contacts/"
```

### Health

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | /health | none | Healthcheck |

All endpoints except `/health` require the header `X-API-Key: <your token>`.
