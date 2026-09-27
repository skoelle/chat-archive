# chat-archive

Systematic import of Instagram, Facebook, XING and LinkedIn takeout messages
into a searchable MySQL/MariaDB database, with a REST API for further analysis.

## Architecture

```
chat-archive/
├── importer/   Tauri v2 desktop tool ("takeout-message-importer")
│               extracts the takeout ZIP locally and sends the raw JSON
│               files to the API over HTTP. Contains NO parsing or DB logic.
│               Supports Instagram, Facebook, Facebook E2EE, XING and LinkedIn
│               (XING/LinkedIn: ZIP or a single CSV file each, no parsing
│               here either).
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
3. Parsing logic lives in `api/app/parsers/` (Instagram, Facebook, Facebook
   E2EE, XING, LinkedIn); `docs/REFERENCE-PARSERS.md` lists the external parser
   projects some of it was ported from.

## Supported platforms

| Platform | Takeout format | Import endpoint |
|---|---|---|
| Instagram | Standard (snake_case) | `POST /import/instagram` |
| Facebook | Standard (snake_case) | `POST /import/facebook` |
| Facebook | E2EE (camelCase) | `POST /import/facebook-e2ee` |
| XING | Data export (CSV, `.zip` or single `.csv`) | `POST /import/xing` |
| LinkedIn | Data export (CSV, `.zip` or single `.csv`) | `POST /import/linkedin` |

Use `GET /conversation?contact_names=John+Doe` to retrieve a merged,
chronologically sorted conversation across all platforms.

## License

Licensed under the [MIT License](LICENSE) - Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
