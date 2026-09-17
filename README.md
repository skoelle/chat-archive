# chat-archive

Systematic import of Instagram and Facebook takeout messages into a searchable
MySQL/MariaDB database, with a REST API for further analysis.

## Architecture

```
chat-archive/
├── importer/   Tauri v2 desktop tool ("takeout-message-importer")
│               extracts the takeout ZIP locally and sends the raw JSON
│               files to the API over HTTP. Contains NO parsing or DB logic.
├── api/        Python/FastAPI service ("chat-archive-api")
│               handles parsing (incl. encoding fix), normalization,
│               writing to MySQL/MariaDB, and exposes REST endpoints
│               for later analysis.
└── docs/       References to external parser projects the actual parsing
                logic should be ported from.
```

## Why not behind Authelia

The API does not run behind Authelia, because the Tauri tool is a plain HTTP
client without a browser session, while Authelia's forward-auth relies on
cookie-based browser logins. Instead, the API protects itself with a static
**API token** (header `X-API-Key`), checked in `api/app/auth.py`. That's
sufficient for an internal homelab network, but the API should not be exposed
unprotected to the internet, keep it internal only, or add IP allowlisting on
the reverse proxy instead of Authelia.

## Setup order

1. Deploy `api/` first (see `api/README.md`), set the token in `.env`.
2. Build `importer/` (see `importer/README.md`), use the same token there.
3. Clone the reference parsers from `docs/REFERENCE-PARSERS.md`, port the
   logic into `api/app/parsers/` (currently placeholders with TODOs).

## License

Licensed under the [MIT License](LICENSE) - Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
