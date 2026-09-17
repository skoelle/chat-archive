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
cp .env.example .env        # fill in API_TOKEN and MySQL credentials
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

## Endpoints

### Import

| Method | Path | Purpose |
|---|---|---|
| POST | /import/instagram | Accepts raw Instagram thread JSON, parses, stores |
| POST | /import/facebook | Accepts raw Facebook (standard) thread JSON, parses, stores |
| POST | /import/facebook-e2ee | Accepts raw Facebook E2EE thread JSON, parses, stores |

All import endpoints accept a JSON body:
```json
{
  "thread_id": "john-doe_123456789",
  "raw_json": { ... }
}
```

The `thread_id` is derived from the folder name inside the takeout ZIP.
The importer sends each JSON file found in the extracted ZIP automatically.

### Query

| Method | Path | Purpose |
|---|---|---|
| GET | /messages | Query individual messages with filters |
| GET | /threads | List all imported threads |
| GET | /conversation | Merged conversation across platforms |

#### GET /messages

Filter messages by platform, thread, or sender.

```
GET /messages?platform=facebook&sender_name=John+Doe&limit=100
```

#### GET /threads

Returns a list of all distinct `thread_id` + `platform` combinations.

#### GET /conversation

Retrieve a merged, chronologically sorted conversation with a specific
contact across one or more platforms. This is the primary endpoint for
chat analysis.

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| contact_names | list[str] | yes | Name(s) of the contact (same person across platforms) |
| platform | str | no | Filter to a specific platform (`instagram`, `facebook`) |
| offset | int | no | Pagination offset (default: 0) |
| limit | int | no | Max messages to return (default: 200, max: 5000) |

**Examples:**

```bash
# All messages with John Doe (all platforms)
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/conversation?contact_names=John+Doe"

# Only Facebook messages
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/conversation?contact_names=John+Doe&platform=facebook"

# Cross-platform: same person may have different names
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/conversation?contact_names=John+Doe&contact_names=john.doe"

# Paginated: page 2 with 100 messages per page
curl -H "X-API-Key: $TOKEN" \
  "http://localhost:8420/conversation?contact_names=John+Doe&offset=100&limit=100"
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
      "message_type": "text"
    }
  ]
}
```

### Health

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | /health | none | Healthcheck |

All endpoints except `/health` require the header `X-API-Key: <your token>`.
