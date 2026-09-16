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

| Method | Path | Purpose |
|---|---|---|
| POST | /import/instagram | Accepts raw Instagram thread JSON, parses, stores |
| POST | /import/facebook | Accepts raw Facebook thread JSON, parses, stores |
| GET | /messages | Query messages (filters: platform, thread_id, sender_name) |
| GET | /threads | Overview of all imported threads |
| GET | /health | Healthcheck, no token required |

All endpoints except `/health` require the header `X-API-Key: <your token>`.
