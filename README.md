AI API Observability



A small FastAPI service for integrating external APIs and AI providers while keeping request behavior visible through SQL metrics, structured logs, request tracing, and a lightweight JavaScript dashboard.

I built this project as a practical integration service rather than a framework demo. The focus is on the parts that matter once an API leaves a notebook: retries, rate limits, secrets, webhooks, persistence, observability, automated tests, Docker, and deployment.

Live deployment

Dashboard: https://ai-api-observability-production.up.railway.app/dashboard

API docs: https://ai-api-observability-production.up.railway.app/docs

Health: https://ai-api-observability-production.up.railway.app/health

Metrics: https://ai-api-observability-production.up.railway.app/stats

The service is deployed on Railway from the Dockerfile in this repository.

AI provider credentials are not left enabled for anonymous public usage. Gemini was enabled temporarily for live validation, real requests were executed through the deployed API, and the credential was removed afterward. The resulting metrics remain stored in the persistent SQLite volume.

Live validation snapshot:

3 successful Gemini requests

0 failed requests

387 total tokens

real end-to-end latency measurements

What the service does

FastAPI REST endpoints

GitHub REST API integration

Anthropic Messages API integration

Google Gemini API integration

retries, exponential backoff, timeout handling, and rate-limit handling

normalized AI responses and token usage

HMAC-SHA256 signed webhook verification

request correlation IDs and structured JSON logging

SQLite persistence for AI request metrics

SQL aggregation through /stats

HTML + vanilla JavaScript dashboard

Docker, GitHub Actions CI, and Railway deployment

Architecture

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

Provider-specific HTTP clients, metrics persistence, and the FastAPI endpoint layer are kept separate so each part can be tested independently.

API endpoints

Method

Endpoint

Purpose

GET

/health

Service health and UTC timestamp

GET

/stats

Aggregated AI request metrics

GET

/dashboard

Browser metrics dashboard

POST

/process

Validated text processing

GET

/github/{owner}/{repo}

Normalized GitHub repository data

POST

/ai/analyze

Anthropic text analysis

POST

/ai/gemini/analyze

Gemini text analysis

POST

/webhooks/inbound

HMAC-SHA256 signed webhook

Interactive OpenAPI documentation is available at /docs.

AI providers

Both AI integrations use direct HTTP requests through httpx instead of provider SDKs. This keeps authentication, request construction, retries, status handling, and response parsing visible in the code.

Gemini

Endpoint:

POST /ai/gemini/analyze

Default model:

gemini-3.1-flash-lite

The client implements environment-based authentication, configurable timeouts and retries, exponential backoff, HTTP 429 handling, transient 5xx retries, response validation, content extraction, token extraction, and normalized responses.

Example request:

{
  "text": "External APIs introduce latency and failure modes.",
  "instruction": "Summarize this text in one sentence."
}

Example response shape:

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

Anthropic

Endpoint:

POST /ai/analyze

The Anthropic client follows the same general resilience pattern and returns a normalized application response.

Anthropic behavior is covered by automated mocked tests. I do not claim a live Anthropic provider validation for this repository.

Live Gemini validation

The deployed Gemini route was tested end to end:

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

A temporary GEMINI_API_KEY environment variable was added to Railway only for this validation.

Three real requests completed successfully. The API key was then removed so the public deployment would not expose anonymous access to provider usage.

The recorded metrics remain available because the database is stored on a persistent Railway volume.

Observability and SQL

AI calls are stored in SQLite with:

UTC creation time

provider and model

input, output, and total tokens

latency in milliseconds

success/error status

request ID

The project uses Python's standard sqlite3 module with explicit SQL rather than an ORM.

GET /stats aggregates data using SQL operations including COUNT, SUM, AVG, CASE, GROUP BY, and ORDER BY.

Example live-style response:

{
  "total_requests": 3,
  "successful_requests": 3,
  "failed_requests": 0,
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

Dashboard

The dashboard uses plain HTML, CSS, and JavaScript. There is no frontend framework or build pipeline.

It fetches /stats and displays:

total requests

successful and failed requests

total tokens

average latency

provider-level request counts

provider-level success/failure counts

provider-level tokens and latency

The Refresh button reloads current metrics from the API.

Request tracing and logging

Every incoming request receives a correlation ID.

If the client sends X-Request-ID, the application preserves it. Otherwise, a UUID is generated.

The request ID is returned in response headers, available during request processing, included in structured logs, and stored with AI request metrics.

Signed webhook

POST /webhooks/inbound validates an HMAC-SHA256 signature from:

X-Webhook-Signature

Expected format:

sha256=<hex-digest>

The server computes the digest from the raw request body and WEBHOOK_SECRET, then compares signatures with hmac.compare_digest().

Automated tests cover valid signatures, invalid signatures, missing signatures, and missing server-side configuration.

Resilience behavior

External clients use bounded retry behavior:

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

Retries are limited; the clients do not retry indefinitely.

Configuration and secrets

Configuration is centralized with pydantic-settings.

Main environment variables include:

APP_NAME
APP_VERSION
LOG_LEVEL

GITHUB_API_BASE
GITHUB_TOKEN

ANTHROPIC_API_BASE
ANTHROPIC_API_KEY
ANTHROPIC_MODEL

GEMINI_API_BASE
GEMINI_API_KEY
GEMINI_MODEL

WEBHOOK_SECRET
DATABASE_PATH

.env.example contains safe placeholders. Real .env files, API keys, webhook secrets, and SQLite database files are excluded from version control.

Running locally

Clone the repository:

git clone https://github.com/joaquinpenafiel/ai-api-observability.git
cd ai-api-observability

Install dependencies:

python -m pip install -r requirements.txt

Start the API:

python -m uvicorn src.main:app --host 0.0.0.0 --port 8000

Open:

http://127.0.0.1:8000/docs
http://127.0.0.1:8000/dashboard

Provider credentials are only required when the corresponding provider endpoint is called.

Docker

Build:

docker build -t ai-api-observability .

Run:

docker run --rm -p 8000:8000 ai-api-observability

Run with a local environment file:

docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  ai-api-observability

The container supports a platform-provided PORT variable and falls back to 8000 locally.

Deployment

Railway deploys the repository Dockerfile with:

a public HTTPS domain

/health as the deployment healthcheck

a persistent volume mounted at /app/data

environment-based configuration

dynamic platform port support

The SQLite path defaults to:

data/api_metrics.db

Because Railway mounts the persistent volume at /app/data, recorded metrics survive container redeployments.

Tests and CI

Run locally:

python -m pytest -q

Current CI result:

31 passed

The suite covers API behavior, provider clients, retries, rate limits, request IDs, signed webhooks, SQLite persistence, AI success/failure metrics, SQL aggregation, /stats, and dashboard/static-file serving.

External APIs are mocked in CI, so automated tests remain deterministic and do not require real provider credentials.

GitHub Actions runs on pushes and pull requests to main:

Checkout
   |
   v
Python 3.12
   |
   v
Install dependencies
   |
   v
pytest
   |
   v
31 tests
   |
   v
Docker build
   |
   v
CI success

A green workflow checks both the test suite and container construction.

Project structure

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

Design choices

Direct HTTP instead of provider SDKs
The integration behavior stays visible and testable instead of being hidden behind another abstraction layer.

SQLite instead of a larger database stack
This service needs a small operational metrics store. SQLite keeps the SQL explicit and the deployment compact.

Vanilla JavaScript instead of a frontend framework
The dashboard exists to expose backend behavior, not to introduce another build system.

Mocked CI and separate live validation
Automated tests remain deterministic and secret-free. Real provider calls are performed separately when validation is needed.

Current limitations

This is a small integration service, not a multi-tenant production platform.

SQLite is intended for the current single-instance deployment.

Provider credentials are disabled in the public deployment after validation.

The dashboard is read-only and intentionally minimal.

There is no user authentication layer.

Anthropic has automated integration coverage but no claimed live-provider validation.

These limits are explicit rather than hidden behind broader claims.

Main technologies

Python 3.12

FastAPI

Pydantic / pydantic-settings

httpx

SQLite / SQL

HTML / CSS

JavaScript

pytest

Docker

GitHub Actions

Railway

Purpose

This repository is a public portfolio project focused on practical API integration, external-service reliability, observability, SQL-backed metrics, automated testing, and deployment.
