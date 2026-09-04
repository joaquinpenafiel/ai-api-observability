# API Integration Lab

A reproducible REST API integration and AI-services laboratory built with Python and FastAPI.

This project demonstrates practical patterns for integrating external services and AI providers into a small, inspectable backend application.

The laboratory focuses on:

- REST API design
- request validation
- external API integration
- AI provider integration
- environment-based configuration
- secret management
- resilience and retry strategies
- rate-limit handling
- structured logging
- request tracing
- automated testing
- continuous integration

---

## Current capabilities

The API currently includes:

- FastAPI REST application
- GET and POST endpoints
- Pydantic request validation
- structured JSON responses
- text normalization and processing
- asynchronous external requests with `httpx`
- GitHub REST API integration
- Anthropic Messages API integration
- Google Gemini API integration
- multiple AI-provider clients
- configurable provider models
- environment-based API keys
- timeout handling
- connection-error handling
- exponential backoff
- configurable retry limits
- HTTP `429` rate-limit handling
- HTTP `5xx` retry behavior
- controlled external-error mapping
- structured JSON logging
- request correlation IDs
- token-usage extraction
- automated tests with `pytest`
- continuous integration with GitHub Actions

---

## Architecture

```text
                         Client
                            |
                            v
                        FastAPI
                            |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
    /health             /process        External integrations
                                                |
                         +----------------------+----------------------+
                         |                      |                      |
                         v                      v                      v
              /github/{owner}/{repo}      /ai/analyze      /ai/gemini/analyze
                         |                      |                      |
                         v                      v                      v
                  GitHub REST API        Anthropic API           Gemini API
                         |                      |                      |
                         +----------------------+----------------------+
                                                |
                                                v
                                     Normalized API responses
```

Provider-specific logic is separated from the FastAPI endpoint layer.

```text
src/
├── main.py
├── config.py
├── logging_config.py
├── request_context.py
└── services/
    ├── github_client.py
    ├── ai_client.py
    └── gemini_client.py
```

This separation keeps external-service responsibilities isolated and makes each integration easier to test, replace, and extend.

---

# API endpoints

## Health check

```http
GET /health
```

Returns the API status and a UTC timestamp.

Example response:

```json
{
  "status": "ok",
  "timestamp": "2026-09-04T12:00:00+00:00"
}
```

---

## Process data

```http
POST /process
```

Normalizes whitespace in an input string and returns basic processing metadata.

Example request:

```json
{
  "text": "   Hello    API Integration Lab   ",
  "source": "manual-test"
}
```

Example response:

```json
{
  "source": "manual-test",
  "original_text": "   Hello    API Integration Lab   ",
  "normalized_text": "Hello API Integration Lab",
  "character_count": 25,
  "processed_at": "2026-09-04T12:00:00+00:00"
}
```

Input is validated with Pydantic before processing.

---

# GitHub REST API integration

## Endpoint

```http
GET /github/{owner}/{repo}
```

Example:

```http
GET /github/fastapi/fastapi
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

Example normalized response:

```json
{
  "repository": "fastapi/fastapi",
  "description": "FastAPI framework...",
  "language": "Python",
  "stars": 0,
  "forks": 0,
  "open_issues": 0,
  "url": "https://github.com/fastapi/fastapi"
}
```

Values shown above are illustrative.

---

## GitHub resilience behavior

The GitHub client implements controlled handling for external-service failures.

Implemented behavior includes:

- configurable request timeout
- configurable maximum retries
- exponential backoff
- retry after connection failures
- retry after request timeouts
- retry for transient HTTP `5xx` responses
- no retry for permanent repository `404`
- GitHub rate-limit detection
- HTTP `429` propagation
- GitHub `403` rate-limit detection
- preservation of `Retry-After` when available
- normalized FastAPI error responses
- structured external-service logging

---

# AI integrations

The laboratory currently includes two independent AI-provider clients:

```text
Anthropic
Gemini
```

The provider clients use direct HTTP requests through `httpx`.

No provider SDK is required.

This keeps the integration small, explicit, and easy to inspect.

---

# Anthropic integration

## Endpoint

```http
POST /ai/analyze
```

Example request:

```json
{
  "text": "External APIs introduce latency and failure modes.",
  "instruction": "Summarize this text in one sentence."
}
```

The Anthropic client sends the request to the Anthropic Messages API.

Implemented behavior includes:

- API authentication through environment variables
- configurable API base URL
- configurable Claude model
- configurable timeout
- configurable retry count
- exponential backoff
- connection-error retries
- timeout retries
- HTTP `429` handling
- transient HTTP `5xx` retries
- authentication-error mapping
- response validation
- text-content extraction
- token-usage extraction
- structured logging
- normalized application response

Example normalized response shape:

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "output": "Generated analysis...",
  "usage": {
    "input_tokens": 20,
    "output_tokens": 8
  }
}
```

The real Anthropic API key is never committed to the repository.

Anthropic behavior is covered through mocked automated tests so CI does not require paid API usage.

---

# Google Gemini integration

## Endpoint

```http
POST /ai/gemini/analyze
```

Example request:

```json
{
  "text": "External APIs introduce latency and failure modes.",
  "instruction": "Summarize this text in one sentence."
}
```

The Gemini client sends requests to the Google Generative Language API.

Current configured model:

```text
gemini-3.1-flash-lite
```

Implemented behavior includes:

- API authentication through environment variables
- configurable API base URL
- configurable Gemini model
- configurable timeout
- configurable retry count
- exponential backoff
- connection-error retries
- timeout retries
- HTTP `429` rate-limit handling
- transient HTTP `5xx` retries
- authentication-error mapping
- candidate validation
- text-content extraction
- token-usage extraction
- structured logging
- normalized application response

Example normalized response:

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

---

## Live Gemini validation

In addition to mocked automated tests, the published Gemini client was manually validated against the real Gemini API.

The validation workflow was:

```text
Public GitHub repository
        |
        v
Clone repository
        |
        v
Import src.services.gemini_client
        |
        v
Provide API key through environment variable
        |
        v
Call analyze_text_with_gemini()
        |
        v
Google Gemini API
        |
        v
Successful normalized response
```

The live call successfully returned:

```text
provider: gemini
model: gemini-3.1-flash-lite
input tokens: 45
output tokens: 60
total tokens: 105
```

This validates the actual client implementation published in the repository rather than only a standalone API experiment.

The real Gemini API key was not stored in the repository.

---

# Normalized AI responses

Both AI clients transform provider-specific responses into application-level structures.

The objective is to prevent the FastAPI layer from depending directly on raw provider payloads.

Conceptually:

```text
External provider response
          |
          v
Provider client
          |
          v
Validation
          |
          v
Content extraction
          |
          v
Usage extraction
          |
          v
Normalized response
```

This makes provider implementations easier to replace or extend.

---

# Environment configuration

Configuration is centralized using:

```text
pydantic-settings
```

The project supports:

- operating-system environment variables
- local `.env` files
- safe `.env.example` documentation

Real `.env` files are ignored by Git.

---

## General configuration

```text
APP_NAME
APP_VERSION
LOG_LEVEL
```

---

## GitHub configuration

```text
GITHUB_API_BASE
GITHUB_TIMEOUT_SECONDS
GITHUB_MAX_RETRIES
GITHUB_BACKOFF_SECONDS
GITHUB_TOKEN
```

The GitHub token is optional.

---

## Anthropic configuration

```text
ANTHROPIC_API_BASE
ANTHROPIC_API_KEY
ANTHROPIC_MODEL
ANTHROPIC_TIMEOUT_SECONDS
ANTHROPIC_MAX_RETRIES
ANTHROPIC_BACKOFF_SECONDS
ANTHROPIC_MAX_TOKENS
```

---

## Gemini configuration

```text
GEMINI_API_BASE
GEMINI_API_KEY
GEMINI_MODEL
GEMINI_TIMEOUT_SECONDS
GEMINI_MAX_RETRIES
GEMINI_BACKOFF_SECONDS
GEMINI_MAX_TOKENS
```

---

## Secret management

Real provider API keys are never hardcoded.

The repository contains only safe placeholders such as:

```text
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

Local credentials should be provided through environment variables or a local `.env` file.

```text
.env
```

is excluded from version control.

---

# Structured logging

The application emits structured JSON logs.

Logged fields can include:

- UTC timestamp
- log level
- logger name
- message
- HTTP method
- request path
- response status code
- request duration
- external status code
- repository identifier
- AI provider
- AI model
- input token count
- output token count
- total token count
- rate-limit information
- retry information
- request correlation ID
- exception information

This provides better observability than unstructured console output.

---

# Request tracing

Every incoming request receives a correlation identifier.

If the client provides:

```http
X-Request-ID
```

the application preserves it.

Otherwise, a new UUID is generated automatically.

Example:

```bash
curl \
  -H "X-Request-ID: example-request-123" \
  http://127.0.0.1:8000/github/fastapi/fastapi
```

The same request ID is:

- returned in the API response headers
- available during request processing
- included in related structured logs

This allows events from the same request to be correlated across application and service layers.

---

# Resilience strategy

External integrations use controlled resilience behavior instead of assuming third-party APIs are always available.

Implemented patterns include:

```text
Request
   |
   v
External API
   |
   +-- success ------------------------> response
   |
   +-- timeout --------+
   |                   |
   +-- connection -----+--> retry
   |                   |      |
   +-- HTTP 5xx -------+      v
   |                      exponential backoff
   |
   +-- HTTP 429 -----------------------> controlled rate-limit response
   |
   +-- permanent error ----------------> mapped application error
```

Retries are bounded.

The clients do not retry indefinitely.

---

# Running the project

Clone the repository:

```bash
git clone https://github.com/joaquinpenafiel/api-integration-lab.git
```

Enter the project directory:

```bash
cd api-integration-lab
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the FastAPI server:

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Interactive FastAPI documentation is available at:

```text
http://127.0.0.1:8000/docs
```

---

# Automated tests

The project uses:

```text
pytest
```

Run the complete suite:

```bash
python -m pytest -q
```

Current suite:

```text
18 passed
```

---

## Current automated coverage

The test suite covers behavior including:

- health endpoint
- text-processing endpoint
- request validation
- successful GitHub API integration
- repository-not-found handling
- transient external failures
- retry recovery
- maximum retry enforcement
- prevention of unnecessary `404` retries
- GitHub HTTP `429` handling
- GitHub HTTP `403` rate-limit detection
- generated request IDs
- preservation of client-provided request IDs
- successful Anthropic response parsing
- missing Anthropic API key
- Anthropic rate-limit handling
- successful Gemini response parsing
- missing Gemini API key
- Gemini rate-limit handling
- AI token-usage extraction
- normalized AI-provider responses

---

# Mocked external services

Automated tests do not call real external APIs.

Instead, external responses are mocked.

This means CI can validate application behavior without:

- exposing API keys
- consuming paid API credits
- depending on internet availability
- depending on provider uptime
- introducing non-deterministic external responses

The separation is:

```text
Automated CI
    |
    v
Mock external APIs
    |
    v
Deterministic tests
```

while live provider validation can be performed separately when required.

---

# Continuous Integration

GitHub Actions automatically runs the complete test suite.

The workflow runs on:

```text
push -> main
pull request -> main
```

CI workflow:

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
18 automated tests
```

A successful workflow independently verifies that the repository can be checked out, dependencies installed, and the complete test suite executed in a clean environment.

---

# Project structure

```text
api-integration-lab/
│
├── .github/
│   └── workflows/
│       └── tests.yml
│
├── src/
│   ├── main.py
│   ├── config.py
│   ├── logging_config.py
│   ├── request_context.py
│   │
│   └── services/
│       ├── github_client.py
│       ├── ai_client.py
│       └── gemini_client.py
│
├── tests/
│   ├── test_api.py
│   ├── test_request_id.py
│   ├── test_resilience.py
│   ├── test_ai.py
│   └── test_gemini.py
│
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

# Dependencies

The project intentionally keeps its dependency list small.

```text
fastapi
uvicorn[standard]
httpx
pytest
pydantic-settings
```

External APIs are called directly with `httpx`.

No Anthropic or Gemini SDK is required.

---

# Technologies

- Python
- FastAPI
- Pydantic
- Pydantic Settings
- HTTPX
- Pytest
- Uvicorn
- GitHub REST API
- Anthropic Messages API
- Google Gemini API
- GitHub Actions
- REST
- JSON
- environment variables
- structured logging
- CI/CD

---

# Design principles

This laboratory follows several simple principles.

## Explicit integrations

External-provider behavior is visible in the code rather than hidden behind large frameworks.

## Separation of responsibilities

FastAPI endpoints do not implement provider-specific HTTP logic.

Provider clients live in:

```text
src/services/
```

## Secret isolation

Credentials remain outside source code.

## Bounded retries

Transient failures are retried, but retries are limited.

## Observable behavior

Requests and external interactions generate structured logs and correlation identifiers.

## Deterministic tests

Automated tests mock external systems.

## Reproducible CI

The repository is validated in a clean GitHub Actions environment after relevant changes.

---

# Purpose

This repository is intentionally designed as a small integration laboratory rather than a large production application.

Its purpose is to demonstrate practical backend engineering patterns around:

- API integrations
- AI services
- provider abstraction
- reliability
- configuration
- observability
- error handling
- test isolation
- secret management
- continuous integration

The emphasis is not simply on making an external API call.

The emphasis is on making that integration:

```text
configurable
testable
observable
resilient
reproducible
```

---

# Current status

```text
GitHub REST integration     
Anthropic integration       
Gemini integration          
Gemini live API validation  
Request tracing             
Structured logging          
Retry / backoff             
Rate-limit handling         
Environment configuration   
Secret isolation            
Automated tests             
GitHub Actions CI           

Test suite: 18 passed
```
