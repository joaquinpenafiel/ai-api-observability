# AI API Observability

[![API Tests](https://github.com/joaquinpenafiel/ai-api-observability/actions/workflows/tests.yml/badge.svg)](https://github.com/joaquinpenafiel/ai-api-observability/actions/workflows/tests.yml)

A small FastAPI service for integrating external APIs and AI providers while keeping request behavior visible through SQL metrics, structured logging, request tracing, and a lightweight JavaScript dashboard.

I built this project as a practical integration service rather than a framework demo. The focus is on the parts that become important once an API leaves a notebook: retries, rate limits, secrets, webhooks, persistence, observability, automated tests, Docker, and deployment.

## Live deployment

- **Dashboard:** https://ai-api-observability-production.up.railway.app/dashboard
- **API documentation:** https://ai-api-observability-production.up.railway.app/docs
- **Health check:** https://ai-api-observability-production.up.railway.app/health
- **Metrics API:** https://ai-api-observability-production.up.railway.app/stats

The service is deployed on Railway from the Dockerfile in this repository.

AI provider credentials are **not left enabled for anonymous public usage**.

Gemini was enabled temporarily in Railway for live validation. Real requests were executed through the deployed API, the resulting metrics were stored in SQLite, and the API key was removed afterward.

The metrics remain available because the database is stored on a persistent Railway volume.

### Live validation snapshot

At the end of the validation run, the dashboard contained:

- 3 successful Gemini requests
- 0 failed requests
- 387 total tokens
- real end-to-end latency measurements

---

## What the service does

The application currently includes:

- FastAPI REST endpoints
- GitHub REST API integration
- Anthropic Messages API integration
- Google Gemini API integration
- configurable provider models and credentials
- bounded retries
- exponential backoff
- timeout handling
- connection-error handling
- HTTP 429 rate-limit handling
- transient HTTP 5xx retries
- normalized AI responses
- token-usage extraction
- HMAC-SHA256 signed webhook verification
- request correlation IDs
- structured JSON logging
- SQLite persistence for AI request metrics
- SQL aggregation through `/stats`
- HTML + vanilla JavaScript dashboard
- Docker containerization
- GitHub Actions CI
- Railway deployment with persistent storage

---

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
          |          +------+------+           |
          |          |             |           |
          v          v             v           v
      /health     GitHub       Anthropic     HMAC verify
      /process      API          Gemini          |
      /stats                       |             v
      /dashboard                   v         accept/reject
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

Provider-specific HTTP clients, metrics persistence, and the FastAPI endpoint layer are kept separate so each part can be tested independently.

---

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

Interactive OpenAPI documentation is available at:

```text
/docs
```

---

## AI providers

Both AI integrations use direct HTTP requests through `httpx` instead of provider SDKs.

This keeps authentication, request construction, retries, status handling, and response parsing visible in the code.

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
- configurable API base URL
- configurable model
- configurable timeout
- bounded retries
- exponential backoff
- connection-error retries
- HTTP 429 handling
- transient HTTP 5xx retries
- authentication-error mapping
- response validation
- text extraction
- token-usage extraction
- normalized application responses
- request metric persistence

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

The Anthropic client follows the same general resilience pattern:

- environment-based authentication
- configurable model
- configurable timeout
- bounded retries
- exponential backoff
- connection-error retries
- HTTP 429 handling
- transient HTTP 5xx retries
- authentication-error mapping
- response validation
- token extraction
- normalized responses
- request metric persistence

Anthropic behavior is covered by automated mocked tests.

I do **not** claim a live Anthropic provider validation for this repository.

---

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
Metrics recorded in SQLite
        |
        v
/stats
        |
        v
JavaScript dashboard
```

A temporary `GEMINI_API_KEY` environment variable was added to Railway only for this validation.

Three real requests completed successfully.

After validation, the Gemini API key was removed from Railway so the public deployment would not expose anonymous access to provider usage.

The recorded metrics remain available because the SQLite database is stored on a persistent Railway volume.

This separates two concerns:

- **CI validation** remains deterministic, mocked, and secret-free.
- **Live provider validation** is performed separately when needed.

---

## Observability and SQL persistence

AI calls are recorded in SQLite with fields including:

- UTC creation time
- provider
- model
- input tokens
- output tokens
- total tokens
- latency in milliseconds
- success or error status
- request ID

The project uses Python's standard `sqlite3` module with explicit SQL rather than an ORM.

The database schema is created automatically when the application starts.

### Metrics endpoint

```text
GET /stats
```

The endpoint aggregates data using SQL operations including:

- `COUNT`
- `SUM`
- `AVG`
- `CASE`
- `GROUP BY`
- `ORDER BY`

It returns both overall statistics and provider-level statistics.

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

The snapshot values above illustrate the structure using the live validation totals. Individual input/output token totals are not being presented here as a historical claim.

---

## Dashboard

The dashboard uses plain:

- HTML
- CSS
- JavaScript

There is no frontend framework or frontend build pipeline.

The browser calls:

```text
GET /stats
```

and renders:

- total requests
- successful requests
- failed requests
- total tokens
- average latency
- provider-level request counts
- provider-level success/failure counts
- provider-level token totals
- provider-level average latency

The **Refresh** button reloads the current metrics from the API.

The frontend is intentionally small so the complete path from SQL to API to browser remains easy to inspect.

---

## Request tracing

Every incoming HTTP request receives a correlation ID.

If the client sends:

```text
X-Request-ID
```

the application preserves it.

Otherwise, a UUID is generated automatically.

The request ID is:

- available during request processing
- returned in response headers
- included in structured logs
- stored with AI request metrics

This makes it possible to correlate an incoming request with its application logs and persisted AI metrics.

---

## Structured logging

The application emits structured JSON logs.

Logged information can include:

- UTC timestamp
- log level
- logger name
- message
- HTTP method
- request path
- response status
- request duration
- external API status
- provider
- model
- retry information
- rate-limit information
- request ID
- exceptions

Secrets are not intentionally included in logs.

---

## Signed webhook

Endpoint:

```text
POST /webhooks/inbound
```

The endpoint validates an HMAC-SHA256 signature supplied through:

```text
X-Webhook-Signature
```

Expected format:

```text
sha256=<hex-digest>
```

The server computes the expected digest from the raw request body and `WEBHOOK_SECRET`.

Signatures are compared using:

```python
hmac.compare_digest()
```

Automated tests cover:

- valid signatures
- invalid signatures
- missing signatures
- missing server-side webhook configuration

The webhook secret is never hardcoded in the repository.

---

## External API resilience

External clients use bounded retry behavior rather than assuming third-party services are always available.

```text
Request
   |
   v
External API
   |
   +-- success --------------------> response
   |
   +-- timeout --------+
   |                   |
   +-- connection -----+--> retry
   |                   |      |
   +-- HTTP 5xx -------+      v
   |                    exponential backoff
   |
   +-- HTTP 429 -------------------> controlled rate-limit response
   |
   +-- permanent error ------------> mapped application error
```

Retries are limited.

The clients do not retry indefinitely.

---

## GitHub API integration

Endpoint:

```text
GET /github/{owner}/{repo}
```

The application requests repository information from the GitHub REST API and returns a normalized response.

Returned information includes:

- repository name
- description
- primary language
- stars
- forks
- open issues
- repository URL

The GitHub client also implements:

- timeout handling
- bounded retries
- exponential backoff
- transient 5xx retries
- 404 handling without unnecessary retries
- GitHub rate-limit handling
- structured external-service logging

---

## Configuration and secrets

Configuration is centralized using `pydantic-settings`.

Main environment variables include:

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

`.env.example` contains safe placeholders.

Real secrets are not committed.

The repository excludes:

- local `.env` files
- API keys
- webhook secrets
- SQLite database files
- Python cache files
- virtual environments

---

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
```

and:

```text
http://127.0.0.1:8000/dashboard
```

Provider credentials are only required when the corresponding provider endpoint is called.

---

## Docker

The project includes a Dockerfile based on:

```text
python:3.12-slim
```

Build the image:

```bash
docker build -t ai-api-observability .
```

Run it:

```bash
docker run --rm \
  -p 8000:8000 \
  ai-api-observability
```

Run with a local environment file:

```bash
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  ai-api-observability
```

The container supports a platform-provided `PORT` variable and falls back to port `8000` locally.

---

## Railway deployment

The service is deployed on Railway directly from the repository Dockerfile.

The deployment currently uses:

- public HTTPS domain
- `/health` deployment healthcheck
- persistent storage volume
- volume mount at `/app/data`
- environment-based configuration
- dynamic platform port support

The SQLite database path defaults to:

```text
data/api_metrics.db
```

Inside the deployed container, the application runs from:

```text
/app
```

so the database resolves to:

```text
/app/data/api_metrics.db
```

Because the persistent Railway volume is mounted at `/app/data`, recorded metrics survive container redeployments.

---

## Automated tests

The project uses `pytest`.

Run locally:

```bash
python -m pytest -q
```

Current CI result:

```text
31 passed
```

The suite covers behavior including:

- health endpoint
- text processing
- request validation
- GitHub API integration
- GitHub 404 handling
- retry recovery
- retry limits
- rate-limit handling
- request ID generation
- request ID preservation
- Anthropic response parsing
- Anthropic missing-key handling
- Anthropic rate-limit handling
- Gemini response parsing
- Gemini missing-key handling
- Gemini rate-limit handling
- signed webhook verification
- invalid webhook rejection
- missing webhook configuration
- SQLite schema initialization
- AI metric persistence
- Gemini endpoint metric persistence
- Anthropic endpoint metric persistence
- failed AI request metric persistence
- SQL statistics aggregation
- `/stats`
- dashboard HTML serving
- dashboard JavaScript serving

External APIs are mocked during CI.

This keeps automated tests:

- deterministic
- independent of provider uptime
- independent of paid API usage
- free of real provider credentials

---

## Continuous Integration

GitHub Actions runs on:

```text
push -> main
pull request -> main
```

Current workflow:

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

The Docker image build is part of the workflow.

A green CI run therefore verifies both:

- application tests
- container construction

---

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

---

## Design choices

### Direct HTTP instead of provider SDKs

Anthropic and Gemini are integrated through `httpx`.

This keeps authentication, payload construction, status handling, retry behavior, and response parsing visible in the repository.

### SQLite instead of a larger database stack

The current service needs a small operational metrics store.

SQLite keeps:

- SQL explicit
- dependencies small
- deployment compact
- persistence easy to inspect

### Vanilla JavaScript instead of a frontend framework

The dashboard exists to expose backend behavior.

Adding React or another frontend framework would introduce a second build system without solving a problem this project currently has.

### Mocked CI and separate live validation

Automated tests remain deterministic and secret-free.

Real provider calls are performed separately when end-to-end validation is needed.

---

## Current limitations

This is a small integration service, not a multi-tenant production platform.

Current limitations are explicit:

- SQLite is intended for the current single-instance deployment
- Gemini credentials are not left enabled in the public deployment
- Anthropic credentials are not enabled in the public deployment
- the dashboard is read-only
- there is no user authentication layer
- there is no role or tenant system
- Anthropic has automated integration coverage but no claimed live-provider validation

These limitations are intentional and are not hidden behind broader claims.

---

## Main technologies

- Python 3.12
- FastAPI
- Pydantic
- pydantic-settings
- httpx
- SQLite
- SQL
- HTML
- CSS
- JavaScript
- pytest
- Docker
- GitHub Actions
- Railway

---

## Purpose

This repository is a public portfolio project focused on practical API integration, external-service reliability, observability, SQL-backed metrics, automated testing, containerization, and deployment.

The goal is not to present a large platform.

The goal is to keep a small system complete enough that its integration behavior can be inspected from HTTP request to external provider, persistence, metrics, CI, Docker, and live deployment.
