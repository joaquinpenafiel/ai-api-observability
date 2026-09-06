# AI API Observability

[![API Tests](https://github.com/joaquinpenafiel/ai-api-observability/actions/workflows/tests.yml/badge.svg)](https://github.com/joaquinpenafiel/ai-api-observability/actions/workflows/tests.yml)

FastAPI service for external API and AI-provider integration with retries, request tracing, signed webhooks, SQL-backed observability, estimated API costs, a JavaScript dashboard, Docker, CI, and Railway deployment.

## Live deployment

- **Dashboard:** https://ai-api-observability-production.up.railway.app/dashboard
- **API docs:** https://ai-api-observability-production.up.railway.app/docs
- **Health:** https://ai-api-observability-production.up.railway.app/health
- **Metrics:** https://ai-api-observability-production.up.railway.app/stats

The public deployment is intentionally read-only for provider-backed execution.

AI provider credentials are not left enabled for anonymous usage, and interactive request execution is disabled in the public Swagger UI.

### Live validation

Gemini was temporarily enabled in Railway for end-to-end validation.

Recorded production snapshot:

- 3 successful Gemini requests
- 0 failed requests
- 387 total tokens
- real end-to-end latency measurements

The temporary Gemini credential was removed after validation. Metrics remain stored in SQLite on a persistent Railway volume.

Anthropic behavior is covered by automated mocked tests; this repository does **not** claim live Anthropic-provider validation.

## What this project demonstrates

- FastAPI REST API design
- GitHub REST API integration
- direct Anthropic and Gemini HTTP clients
- environment-based secret management
- retries and exponential backoff
- timeout, connection, rate-limit, and transient 5xx handling
- normalized AI responses
- token-usage extraction
- estimated API-cost tracking
- request correlation IDs
- structured JSON logging
- HMAC-SHA256 webhook verification
- SQLite persistence
- SQL aggregation
- recent-request history
- vanilla JavaScript observability dashboard
- pytest automation
- Docker containerization
- GitHub Actions CI
- Railway deployment with persistent storage

## Architecture

```text
Client
  |
  v
FastAPI
  |
  +-------------------+--------------------+
  |                   |                    |
  v                   v                    v
Core API         Integrations         Signed webhook
  |                   |                    |
  |              +----+----+               v
  |              |         |          HMAC verify
  |           GitHub    AI providers
  |                        |
  |                  +-----+------+
  |                  |            |
  |              Anthropic      Gemini
  |                       |
  +-----------------------+
                          |
                          v
                    AI telemetry
                          |
              +-----------+-----------+
              |                       |
              v                       v
         token usage             cost estimate
              |                       |
              +-----------+-----------+
                          |
                          v
                        SQLite
                          |
                 +--------+--------+
                 |                 |
                 v                 v
              /stats          /dashboard
```

Provider clients, request instrumentation, cost estimation, persistence, and presentation are separated so each layer can be tested independently.

## API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Health status and UTC timestamp |
| GET | `/stats` | Aggregated metrics and recent AI requests |
| GET | `/dashboard` | Read-only observability dashboard |
| POST | `/process` | Validated text processing |
| GET | `/github/{owner}/{repo}` | Normalized GitHub repository data |
| POST | `/ai/analyze` | Anthropic text analysis |
| POST | `/ai/gemini/analyze` | Gemini text analysis |
| POST | `/webhooks/inbound` | HMAC-SHA256 signed webhook |

OpenAPI documentation is available at `/docs`.

Interactive request execution is disabled in the public Swagger UI.

## AI integrations

Both AI providers use direct `httpx` requests rather than provider SDKs.

This keeps authentication, payload construction, retries, status handling, and response parsing visible in the code.

### Gemini

Endpoint:

```text
POST /ai/gemini/analyze
```

Default model:

```text
gemini-3.1-flash-lite
```

The client implements:

- environment-based authentication
- configurable timeout and retry count
- exponential backoff
- HTTP 429 handling
- transient 5xx retries
- authentication-error mapping
- response validation
- text extraction
- input/output/total token extraction
- automatic metrics persistence

Example response shape:

```json
{
  "provider": "gemini",
  "model": "gemini-3.1-flash-lite",
  "output": "Generated analysis...",
  "usage": {
    "input_tokens": 45,
    "output_tokens": 60,
    "total_tokens": 105
  }
}
```

### Anthropic

Endpoint:

```text
POST /ai/analyze
```

Default model:

```text
claude-sonnet-4-6
```

The Anthropic client follows the same resilience pattern: environment-based authentication, bounded retries, exponential backoff, rate-limit and transient-error handling, response validation, token extraction, normalized responses, and metrics persistence.

## Disabled-provider behavior

Provider credentials are optional.

When a provider credential is not configured, the corresponding endpoint returns:

```text
HTTP 503
```

This represents an intentionally disabled integration rather than an upstream AI-provider failure.

Disabled-provider responses are therefore not stored as failed AI requests. Real provider failures, such as HTTP 429 responses, remain observable.

## Observability

AI requests can be stored with:

- UTC creation time
- provider and model
- input/output/total tokens
- estimated API cost
- latency
- success or error status
- request ID

Metrics are stored in SQLite using Python's standard `sqlite3` module and explicit SQL.

### Estimated API cost

Successful AI calls estimate cost using input/output token usage and a centralized provider/model pricing table.

The value is persisted with the request metrics and exposed through `/stats` and the dashboard.

Estimated cost is intended for operational observability and is **not** a replacement for provider billing records.

The original three live Gemini requests predate cost telemetry. Their cost remains `0.0` rather than being reconstructed from incomplete historical data.

## Metrics API

```text
GET /stats
```

The endpoint uses explicit SQL aggregation including:

```text
COUNT
SUM
AVG
CASE
GROUP BY
ORDER BY
```

It exposes:

- total request count
- success/failure counts
- token totals
- estimated total cost
- average latency
- provider-level metrics
- 20 most recent AI requests

Recent requests are bounded to 20 records and returned newest first.

## Dashboard

The dashboard uses plain HTML, CSS, and JavaScript.

It displays:

- total requests
- successful and failed requests
- total tokens
- estimated AI API cost
- average latency
- provider-level metrics
- recent AI request history

The Recent Requests table includes:

- timestamp
- provider
- model
- status
- token count
- estimated cost
- latency

The **Refresh** button reloads data from `/stats`.

## Request tracing and logging

Every incoming HTTP request receives a correlation ID.

If the client provides:

```text
X-Request-ID
```

the application preserves it. Otherwise, a UUID is generated.

The request ID is returned in response headers and can also be included in structured logs and persisted AI metrics.

Structured logs can include HTTP method, path, status, duration, provider, model, retry information, rate-limit information, request ID, and exceptions.

Secrets are not intentionally logged.

## Signed webhook

Endpoint:

```text
POST /webhooks/inbound
```

The webhook validates an HMAC-SHA256 signature supplied through:

```text
X-Webhook-Signature
```

Expected format:

```text
sha256=<hex-digest>
```

The expected digest is computed from the raw request body and `WEBHOOK_SECRET` and compared with:

```python
hmac.compare_digest()
```

Tests cover valid, invalid, missing signatures, and missing server configuration.

## GitHub integration

Endpoint:

```text
GET /github/{owner}/{repo}
```

The GitHub client returns normalized repository information including:

- repository name
- description
- primary language
- stars
- forks
- open issues
- repository URL

It also implements timeout handling, bounded retries, exponential backoff, transient 5xx handling, 404 handling, rate-limit handling, and structured logging.

## Configuration

Configuration is centralized with `pydantic-settings`.

Main environment variables:

```text
APP_NAME
APP_VERSION
LOG_LEVEL

GITHUB_API_BASE
GITHUB_TOKEN
GITHUB_TIMEOUT_SECONDS
GITHUB_MAX_RETRIES
GITHUB_BACKOFF_SECONDS

ANTHROPIC_API_BASE
ANTHROPIC_API_KEY
ANTHROPIC_MODEL
ANTHROPIC_TIMEOUT_SECONDS
ANTHROPIC_MAX_RETRIES

GEMINI_API_BASE
GEMINI_API_KEY
GEMINI_MODEL
GEMINI_TIMEOUT_SECONDS
GEMINI_MAX_RETRIES

WEBHOOK_SECRET
DATABASE_PATH
```

`.env.example` contains safe placeholders. Real secrets are not committed.

## Run locally

```bash
git clone https://github.com/joaquinpenafiel/ai-api-observability.git
cd ai-api-observability
python -m pip install -r requirements.txt
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Then open:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/dashboard
```

Provider credentials are required only when the corresponding provider endpoint is used.

## Docker

Build:

```bash
docker build -t ai-api-observability .
```

Run:

```bash
docker run --rm -p 8000:8000 ai-api-observability
```

The container supports a platform-provided `PORT` and falls back to port `8000` locally.

## Railway deployment

The service is deployed from the repository Dockerfile with:

- public HTTPS
- `/health` deployment healthcheck
- environment-based configuration
- dynamic platform port support
- persistent volume mounted at `/app/data`

The SQLite database resolves to:

```text
/app/data/api_metrics.db
```

so recorded metrics survive redeployments.

The architecture is intentionally single-instance because SQLite is used as the operational metrics store.

## Automated tests and CI

Run:

```bash
python -m pytest -q
```

Current CI result:

```text
37 passed
```

The suite covers:

- core API behavior
- GitHub integration
- Anthropic and Gemini clients
- retries and rate limits
- request IDs
- signed webhooks
- SQLite persistence and migration
- AI success/failure telemetry
- disabled-provider behavior
- token-based cost estimation
- SQL cost aggregation
- recent-request history
- `/stats`
- dashboard/static serving

External APIs are mocked during CI, keeping tests deterministic and free of real provider credentials.

GitHub Actions validates:

```text
pytest -> 37 tests -> Docker build -> success
```

## Project structure

```text
.
├── .github/
│   └── workflows/
│       └── tests.yml
├── src/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── logging_config.py
│   ├── request_context.py
│   ├── services/
│   │   ├── ai_client.py
│   │   ├── ai_costs.py
│   │   ├── ai_metrics.py
│   │   ├── gemini_client.py
│   │   ├── github_client.py
│   │   └── webhook_security.py
│   └── static/
│       ├── dashboard.html
│       └── dashboard.js
├── tests/
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Design choices

### Direct HTTP instead of provider SDKs

Direct `httpx` integrations keep authentication, request construction, retries, error mapping, and response parsing explicit and testable.

### SQLite and explicit SQL

The project needs a compact operational metrics store rather than a large database stack. SQLite keeps deployment simple while preserving visible SQL aggregation.

### Centralized cost estimation

Pricing logic is separated from request instrumentation so provider/model pricing and telemetry can evolve independently.

### Vanilla JavaScript

The dashboard exists to expose backend behavior without adding another frontend build system.

### Mocked CI and separate live validation

CI remains deterministic and secret-free. Real provider calls are used only for deliberate end-to-end validation.

## Current limitations

This is a portfolio-scale integration and observability service, not a multi-tenant production platform.

- SQLite targets the current single-instance deployment.
- Gemini credentials are disabled in the public deployment.
- Anthropic credentials are disabled in the public deployment.
- The dashboard is read-only.
- There is no user authentication layer.
- Anthropic has mocked integration coverage but no claimed live-provider validation.
- Estimated costs are approximate.
- Historical rows created before cost telemetry are not backfilled.

## Main technologies

- Python 3.12
- FastAPI
- Pydantic / pydantic-settings
- httpx
- SQLite / SQL
- HTML / CSS / JavaScript
- pytest
- Docker
- GitHub Actions
- Railway

## Purpose

This repository is a public portfolio project focused on practical API integration, external-service reliability, observability, cost awareness, automated testing, containerization, and deployment.

The complete path remains inspectable:

```text
HTTP request
   -> validation
   -> external API
   -> retry / error handling
   -> token usage
   -> estimated cost
   -> SQLite
   -> SQL aggregation
   -> /stats
   -> dashboard
   -> CI / Docker / deployment
```
