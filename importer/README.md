# takeout-message-importer

Tauri v2 desktop tool. Extracts an Instagram, Facebook, XING or LinkedIn export
locally and sends each thread/CSV to chat-archive-api over HTTP. Intentionally
contains no parsing or database logic, the API handles all of that.

Supported inputs: Instagram takeout, Facebook takeout, Facebook E2EE takeout
(all `.zip`), the XING data export and the LinkedIn data export (each `.zip` or
a single `.csv` file, which is forwarded as raw text).

## Setup

```bash
npm install
npm run tauri dev
```

## Configuration

Enter in the UI:
- API base URL (e.g. http://192.168.178.20:8420)
- API token (X-API-Key, must match the .env value of the API)

## Build (Windows)

```bash
npm run tauri build
```
