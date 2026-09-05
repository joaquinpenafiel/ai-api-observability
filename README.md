# AI API Observability
[![API Tests](https://github.com/joaquinpenafiel/ai-api-observability/actions/workflows/tests.yml/badge.svg)](https://github.com/joaquinpenafiel/ai-api-observability/actions/workflows/tests.yml)

A compact FastAPI service for integrating external APIs and AI providers while keeping request behavior visible through SQL metrics, request tracing, structured logging, and a lightweight JavaScript dashboard.

The project focuses on practical backend concerns that appear once an API moves beyond a local experiment: retries, rate limits, secrets, webhooks, persistence, observability, automated tests, Docker, and deployment.

## Live deployment
- **Dashboard:** https://ai-api-observability-production.up.railway.app/dashboard
- **API documentation:** https://ai-api-observability-production.up.railway.app/docs
- **Health check:** https://ai-api-observability-production.up.railway.app/health
- **Metrics API:** https://ai-api-observability-production.up.railway.app/stats

The service is deployed on Railway from the Dockerfile in this repository.

AI provider credentials are **not left enabled for anonymous public usage**. Gemini was enabled temporarily in Railway for live validation, real requests were executed through the deployed API, the resulting metrics were stored in SQLite, and the API key was removed afterward.

The recorded metrics remain available because the database is stored on a persistent Railway volume.

### Live validation snapshot
- 3 successful Gemini requests
- 0 failed requests
- 387 total tokens
- real end-to-end latency measurements

## What the service does
- FastAPI REST endpoints
- GitHub REST API integration
- Anthropic Messages API integration
- Google Gemini API integration
- configurable provider models and credentials
- bounded retries and exponential backoff
- timeout, connection-error, rate-limit, and transient 5xx handling
- normalized AI responses and token-usage extraction
- HMAC-SHA256 signed webhook verification
- request correlation IDs and structured JSON logging
- SQLite persistence for AI request metrics
- SQL aggregation through `/stats`
- HTML + vanilla JavaScript dashboard
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
          +-----------------+------------------+
          |                 |                  |
          v                 v                  v
     Core endpoints    API integrations   Signed webhook
          |                 |                  |
          v          +------+------+           v
      /health        |             |       HMAC verify
      /process    GitHub       AI providers       |
      /stats        API        Anthropic          v
      /dashboard                Gemini       accept/reject
                                  |
                                  v
                             AI metrics
                                  |
                                  v
                               SQLite
                                  |
                         +--------+--------+
                         |                 |
                         v                 v
                      /stats          JS dashboard
```

Provider-specific HTTP clients, metrics persistence, and the FastAPI endpoint layer are separated so each part can be tested independently.

## API endpoints
| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Service health and UTC timestamp |
| GET | `/stats` | Aggregated AI request metrics |
| GET | `/dashboard` | Browser metrics dashboard |
| POST | `/process` | Validated text processing |
| GET | `/github/{owner}/{repo}` | Normalized GitHub repository data |
| POST | `/ai/analyze` | Anthropic text analysis |
| POST | `/ai/gemini/analyze` | Gemini text analysis |
| POST | `/webhooks/inbound` | HMAC-SHA256 signed webhook |

Interactive OpenAPI documentation is available at `/docs`.

## AI providers
Both AI integrations use direct HTTP requests through `httpx` instead of provider SDKs. This keeps authentication, request construction, retries, status handling, and response parsing visible in the code.

### Gemini
Endpoint:
```text
POST /ai/gemini/analyze
```

Default model:
```text
gemini-3.1-flash-lite
```

The client implements environment-based authentication, configurable model and timeout, bounded retries, exponential backoff, HTTP 429 handling, transient 5xx retries, authentication-error mapping, response validation, text extraction, token-usage extraction, normalized responses, and request metric persistence.

Example request:
```json
{
  "text": "External APIs introduce latency and failure modes.",
  "instruction": "Summarize this text in one sentence."
}
```

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

The Anthropic client follows the same general resilience pattern: environment-based authentication, configurable model and timeout, bounded retries, exponential backoff, HTTP 429 handling, transient 5xx retries, authentication-error mapping, response validation, token extraction, normalized responses, and request metric persistence.

Anthropic behavior is covered by automated mocked tests. I do **not** claim a live Anthropic provider validation for this repository.

## Live Gemini validation
The deployed Gemini route was tested end to end through Railway:
```text
Browser / OpenAPI docs
        |
        v
Railway public HTTPS endpoint
        |
        v
FastAPI
        |
        v
Gemini client
        |
        v
Google Gemini API
        |
        v
200 response
        |
        v
SQLite metrics
        |
        v
/stats
        |
        v
JavaScript dashboard
```

A temporary `GEMINI_API_KEY` environment variable was added to Railway only for this validation. Three real requests completed successfully.

After validation, the Gemini API key was removed from Railway so the public deployment would not expose anonymous access to provider usage. The recorded metrics remain available because the SQLite database is stored on a persistent Railway volume.

CI and live-provider validation are intentionally separated:
- **CI validation:** mocked, deterministic, and secret-free.
- **Live validation:** performed separately when end-to-end provider behavior needs to be checked.

## Observability and SQL persistence
AI calls are recorded in SQLite with:
- UTC creation time
- provider and model
- input, output, and total tokens
- latency in milliseconds
- success or error status
- request ID

The project uses Python's standard `sqlite3` module with explicit SQL rather than an ORM. The database schema is created automatically when the application starts.

### Metrics endpoint
```text
GET /stats
```

The endpoint aggregates data using SQL operations including `COUNT`, `SUM`, `AVG`, `CASE`, `GROUP BY`, and `ORDER BY`.

Example response shape:
```json
{
  "total_requests": 3,
  "successful_requests": 3,
  "failed_requests": 0,
  "total_input_tokens": 0,
  "total_output_tokens": 0,
  "total_tokens": 387,
  "average_latency_ms": 1930.61,
  "providers": [
    {
      "provider": "gemini",
      "requests": 3,
      "successful_requests": 3,
      "failed_requests": 0,
      "total_tokens": 387,
      "average_latency_ms": 1930.61
    }
  ]
}
```

The values above illustrate the response shape using the live validation totals. Individual input/output totals are not presented as a historical claim.

## Dashboard
The dashboard uses plain HTML, CSS, and JavaScript. It fetches `/stats` and renders:
- total requests
- successful and failed requests
- total tokens
- average latency
- provider-level request counts
- provider-level success/failure counts
- provider-level token totals
- provider-level average latency

The **Refresh** button reloads the current metrics. The frontend is intentionally small so the full path from SQL to API to browser remains easy to inspect.

## Request tracing and logging
Every incoming HTTP request receives a correlation ID.

If the client sends `X-Request-ID`, the application preserves it. Otherwise, a UUID is generated automatically.

The request ID is returned in response headers, available during request processing, included in structured logs, and stored with AI request metrics.

Structured JSON logs can include HTTP method, request path, response status, request duration, provider, model, retry information, rate-limit information, request ID, and exceptions. Secrets are not intentionally included in logs.

## Signed webhook
Endpoint:
```text
POST /webhooks/inbound
```

The endpoint validates an HMAC-SHA256 signature supplied through `X-Webhook-Signature`.

Expected format:
```text
sha256=<hex-digest>
```

The server computes the expected digest from the raw request body and `WEBHOOK_SECRET`, then compares signatures with:
```python
hmac.compare_digest()
```

Automated tests cover valid signatures, invalid signatures, missing signatures, and missing server-side webhook configuration. The webhook secret is never hardcoded in the repository.

## External API resilience
External clients use bounded retry behavior:
```text
Request
   |
   v
External API
   |
   +-- success --------------------> response
   |
   +-- timeout --------+
   +-- connection -----+--> retry --> exponential backoff
   +-- HTTP 5xx -------+
   |
   +-- HTTP 429 -------------------> controlled rate-limit response
   |
   +-- permanent error ------------> mapped application error
```

Retries are limited; the clients do not retry indefinitely.

## GitHub API integration
Endpoint:
```text
GET /github/{owner}/{repo}
```

The application requests repository information from the GitHub REST API and returns a normalized response with repository name, description, primary language, stars, forks, open issues, and repository URL.

The GitHub client also implements timeout handling, bounded retries, exponential backoff, transient 5xx retries, 404 handling without unnecessary retries, rate-limit handling, and structured external-service logging.

## Configuration and secrets
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

## Running locally
Clone the repository:
```bash
git clone https://github.com/joaquinpenafiel/ai-api-observability.git
cd ai-api-observability
```

Install dependencies:
```bash
python -m pip install -r requirements.txt
```

Start the API:
```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Open:
```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/dashboard
```

Provider credentials are only required when the corresponding provider endpoint is called.

## Docker
Build the image:
```bash
docker build -t ai-api-observability .
```

Run it:
```bash
docker run --rm -p 8000:8000 ai-api-observability
```

Run with a local environment file:
```bash
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  ai-api-observability
```

The container supports a platform-provided `PORT` variable and falls back to port `8000` locally.

## Railway deployment
The service is deployed on Railway from the repository Dockerfile with:
- public HTTPS domain
- `/health` deployment healthcheck
- persistent volume mounted at `/app/data`
- environment-based configuration
- dynamic platform port support

The SQLite database path defaults to:
```text
data/api_metrics.db
```

Inside the deployed container the application runs from `/app`, so the database resolves to:
```text
/app/data/api_metrics.db
```

Because the persistent Railway volume is mounted at `/app/data`, recorded metrics survive container redeployments.

## Automated tests and CI
The project uses `pytest`.

Run locally:
```bash
python -m pytest -q
```

Current CI result:
```text
31 passed
```

The suite covers API behavior, provider clients, retries, rate limits, request IDs, signed webhooks, SQLite persistence, AI success/failure metrics, SQL aggregation, `/stats`, and dashboard/static-file serving.

External APIs are mocked during CI, keeping tests deterministic and free of real provider credentials.

GitHub Actions runs on pushes and pull requests to `main`:
```text
Checkout repository
        |
        v
Set up Python 3.12
        |
        v
Install dependencies
        |
        v
Run pytest
        |
        v
31 tests
        |
        v
Build Docker image
        |
        v
CI success
```

A green workflow checks both the test suite and container construction.

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
Anthropic and Gemini are integrated through `httpx` so authentication, payload construction, status handling, retry behavior, and response parsing remain visible.

### SQLite instead of a larger database stack
The service only needs a small operational metrics store. SQLite keeps the SQL explicit, dependencies small, and deployment compact.

### Vanilla JavaScript instead of a frontend framework
The dashboard exists to expose backend behavior. A frontend framework would add another build system without solving a problem this project currently has.

### Mocked CI and separate live validation
Automated tests remain deterministic and secret-free. Real provider calls are performed separately when end-to-end validation is needed.

## Current limitations
This is a small integration service, not a multi-tenant production platform.

Current limitations:
- SQLite is intended for the current single-instance deployment
- Gemini credentials are not left enabled in the public deployment
- Anthropic credentials are not enabled in the public deployment
- the dashboard is read-only
- there is no user authentication layer
- Anthropic has automated integration coverage but no claimed live-provider validation

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
This repository is a public portfolio project focused on practical API integration, external-service reliability, observability, SQL-backed metrics, automated testing, containerization, and deployment.

The goal is to keep a small system complete enough that its behavior can be inspected from incoming HTTP request to external provider, persistence, metrics, CI, Docker, and live deployment.
