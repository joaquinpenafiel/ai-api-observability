API Integration Lab

A reproducible REST API, AI-services, webhook, and containerization laboratory built with Python and FastAPI.

This project demonstrates practical backend engineering patterns for integrating third-party services into a small, inspectable application with explicit configuration, resilience, observability, testing, and CI validation.

The laboratory focuses on:

REST API design

request validation

external API integration

AI provider integration

signed webhook handling

environment-based configuration

secret isolation

resilience and retry strategies

rate-limit handling

structured logging

request tracing

automated testing

Docker containerization

continuous integration

Current capabilities

The API currently includes:

FastAPI REST application

GET and POST endpoints

Pydantic request validation

structured JSON responses

text normalization and processing

asynchronous external requests with httpx

GitHub REST API integration

Anthropic Messages API integration

Google Gemini API integration

multiple AI-provider clients

configurable provider models

environment-based API keys

configurable timeouts and retry limits

exponential backoff

connection-error handling

HTTP 429 rate-limit handling

transient HTTP 5xx retry behavior

controlled external-error mapping

structured JSON logging

request correlation IDs

token-usage extraction

signed inbound webhook integration

HMAC-SHA256 webhook signature verification

constant-time signature comparison

Docker containerization

Docker build validation in GitHub Actions

automated tests with pytest

continuous integration with GitHub Actions

Architecture

                              Client
                                 |
                                 v
                             FastAPI
                                 |
       +-------------------------+--------------------------+
       |                         |                          |
       v                         v                          v
 Core endpoints          External integrations       Signed webhook
       |                         |                          |
       |             +-----------+-----------+              |
       |             |           |           |              |
       v             v           v           v              v
   /health        GitHub      Anthropic    Gemini      /webhooks/inbound
   /process       client       client      client             |
                     |           |           |                v
                     v           v           v          HMAC-SHA256 verify
                 GitHub API  Anthropic API Gemini API          |
                                                           accept/reject

Provider-specific logic is separated from the FastAPI endpoint layer.

src/
├── main.py
├── config.py
├── logging_config.py
├── request_context.py
└── services/
    ├── github_client.py
    ├── ai_client.py
    ├── gemini_client.py
    └── webhook_security.py

This separation keeps external-service responsibilities isolated and makes integrations easier to test, replace, and extend.

API endpoints

Health check

GET /health

Returns the API status and a UTC timestamp.

Example response:

{
  "status": "ok",
  "timestamp": "2026-09-04T12:00:00+00:00"
}

Process data

POST /process

Normalizes whitespace in an input string and returns basic processing metadata.

Example request:

{
  "text": "   Hello    API Integration Lab   ",
  "source": "manual-test"
}

Example response:

{
  "source": "manual-test",
  "original_text": "   Hello    API Integration Lab   ",
  "normalized_text": "Hello API Integration Lab",
  "character_count": 25,
  "processed_at": "2026-09-04T12:00:00+00:00"
}

Input is validated with Pydantic before processing.

GitHub REST API integration

Endpoint

GET /github/{owner}/{repo}

Example:

GET /github/fastapi/fastapi

The application requests repository information from the GitHub REST API and returns a normalized response.

Returned information includes:

repository name

description

primary language

stars

forks

open issues

repository URL

Example normalized response:

{
  "repository": "fastapi/fastapi",
  "description": "FastAPI framework...",
  "language": "Python",
  "stars": 0,
  "forks": 0,
  "open_issues": 0,
  "url": "https://github.com/fastapi/fastapi"
}

Values shown above are illustrative.

GitHub resilience behavior

The GitHub client implements controlled handling for external-service failures.

Implemented behavior includes:

configurable request timeout

configurable maximum retries

exponential backoff

retry after connection failures

retry after request timeouts

retry for transient HTTP 5xx responses

no retry for permanent repository 404

GitHub rate-limit detection

HTTP 429 propagation

GitHub 403 rate-limit detection

preservation of Retry-After when available

normalized FastAPI error responses

structured external-service logging

Signed webhook integration

Endpoint

POST /webhooks/inbound

The endpoint accepts the raw request body and validates an HMAC-SHA256 signature provided through:

X-Webhook-Signature

The webhook secret is supplied through:

WEBHOOK_SECRET

Expected signature format:

sha256=<hex-digest>

The application calculates the expected digest from the raw payload and configured secret, then compares the received and expected signatures with hmac.compare_digest().

Implemented behavior includes:

raw payload signature verification

HMAC-SHA256 digest generation

constant-time signature comparison

rejection of missing signatures

rejection of invalid signatures

controlled handling when the webhook secret is not configured

environment-based secret management

structured webhook logging

Example successful response:

{
  "status": "accepted",
  "payload_bytes": 37
}

Possible error responses include:

401 - webhook signature is missing
401 - invalid webhook signature
503 - webhook service is not configured

The webhook secret is never hardcoded or committed to the repository.

Webhook test coverage

Automated tests verify:

a correctly signed payload is accepted

an invalid signature is rejected

a missing signature is rejected

a missing server-side webhook secret returns a controlled configuration error

AI integrations

The laboratory currently includes two independent AI-provider clients:

Anthropic
Google Gemini

Both provider clients use direct HTTP requests through httpx.

No Anthropic or Gemini SDK is required.

This keeps provider behavior explicit and makes authentication, retries, rate limits, parsing, and error mapping visible in the application code.

Anthropic integration

Endpoint

POST /ai/analyze

Example request:

{
  "text": "External APIs introduce latency and failure modes.",
  "instruction": "Summarize this text in one sentence."
}

The Anthropic client sends requests to the Anthropic Messages API.

Implemented behavior includes:

API authentication through environment variables

configurable API base URL

configurable Claude model

configurable timeout

configurable retry count

exponential backoff

connection-error retries

timeout retries

HTTP 429 handling

transient HTTP 5xx retries

authentication-error mapping

response validation

text-content extraction

token-usage extraction

structured logging

normalized application response

Example normalized response shape:

{
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "output": "Generated analysis...",
  "usage": {
    "input_tokens": 20,
    "output_tokens": 8
  }
}

The real Anthropic API key is never committed to the repository.

Anthropic behavior is covered through mocked automated tests so CI does not require paid API usage.

Note: the Anthropic integration has not been presented as a live-provider validation. Its behavior is validated through mocked automated tests.

Google Gemini integration

Endpoint

POST /ai/gemini/analyze

Example request:

{
  "text": "External APIs introduce latency and failure modes.",
  "instruction": "Summarize this text in one sentence."
}

The Gemini client sends requests to the Google Generative Language API.

Current configured model:

gemini-3.1-flash-lite

Implemented behavior includes:

API authentication through environment variables

configurable API base URL

configurable Gemini model

configurable timeout

configurable retry count

exponential backoff

connection-error retries

timeout retries

HTTP 429 rate-limit handling

transient HTTP 5xx retries

authentication-error mapping

candidate validation

text-content extraction

token-usage extraction

structured logging

normalized application response

Example normalized response:

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

Live Gemini validation

In addition to mocked automated tests, the published Gemini client was manually validated against the real Gemini API.

The validation workflow was:

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

The live call successfully returned:

provider: gemini
model: gemini-3.1-flash-lite
input tokens: 45
output tokens: 60
total tokens: 105

This validates the actual client implementation published in the repository rather than only a standalone API experiment.

The real Gemini API key was not stored in the repository.

Normalized AI responses

Both AI clients transform provider-specific responses into application-level structures.

The objective is to prevent the FastAPI layer from depending directly on raw provider payloads.

Conceptually:

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

This makes provider implementations easier to replace or extend.

Environment configuration

Configuration is centralized using:

pydantic-settings

The project supports:

operating-system environment variables

local .env files

safe .env.example documentation

Real .env files are ignored by Git and excluded from the Docker build context.

General configuration

APP_NAME
APP_VERSION
LOG_LEVEL

GitHub configuration

GITHUB_API_BASE
GITHUB_TIMEOUT_SECONDS
GITHUB_MAX_RETRIES
GITHUB_BACKOFF_SECONDS
GITHUB_TOKEN

The GitHub token is optional.

Anthropic configuration

ANTHROPIC_API_BASE
ANTHROPIC_API_KEY
ANTHROPIC_MODEL
ANTHROPIC_TIMEOUT_SECONDS
ANTHROPIC_MAX_RETRIES
ANTHROPIC_BACKOFF_SECONDS
ANTHROPIC_MAX_TOKENS

Gemini configuration

GEMINI_API_BASE
GEMINI_API_KEY
GEMINI_MODEL
GEMINI_TIMEOUT_SECONDS
GEMINI_MAX_RETRIES
GEMINI_BACKOFF_SECONDS
GEMINI_MAX_TOKENS

Webhook configuration

WEBHOOK_SECRET

Secret management

Real provider API keys and webhook secrets are never hardcoded.

The repository contains only safe placeholders such as:

ANTHROPIC_API_KEY=
GEMINI_API_KEY=
WEBHOOK_SECRET=

Local credentials should be provided through operating-system environment variables or a local .env file.

Structured logging

The application emits structured JSON logs.

Logged fields can include:

UTC timestamp

log level

logger name

message

HTTP method

request path

response status code

request duration

external status code

repository identifier

AI provider

AI model

input token count

output token count

total token count

rate-limit information

retry information

request correlation ID

exception information

Webhook verification also records controlled success and failure events without exposing the secret.

Request tracing

Every incoming request receives a correlation identifier.

If the client provides:

X-Request-ID

the application preserves it.

Otherwise, a new UUID is generated automatically.

Example:

curl \
  -H "X-Request-ID: example-request-123" \
  http://127.0.0.1:8000/github/fastapi/fastapi

The same request ID is:

returned in the API response headers

available during request processing

included in related structured logs

This allows events from the same request to be correlated across application and service layers.

Resilience strategy

External integrations use controlled resilience behavior instead of assuming third-party APIs are always available.

Implemented patterns include:

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

Retries are bounded.

The clients do not retry indefinitely.

Running the project locally

Clone the repository:

git clone https://github.com/joaquinpenafiel/api-integration-lab.git

Enter the project directory:

cd api-integration-lab

Install dependencies:

python -m pip install -r requirements.txt

Start the FastAPI server:

python -m uvicorn src.main:app --host 0.0.0.0 --port 8000

Interactive FastAPI documentation is available at:

http://127.0.0.1:8000/docs

Docker containerization

The project includes a Dockerfile based on:

python:3.12-slim

The image:

creates /app as the working directory

installs dependencies from requirements.txt

copies the application source

exposes port 8000

starts FastAPI through Uvicorn

Build the image:

docker build -t api-integration-lab .

Run the container without external-service credentials:

docker run --rm -p 8000:8000 api-integration-lab

Run with a local environment file when provider credentials or the webhook secret are required:

docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  api-integration-lab

The .dockerignore excludes local and development-only material such as:

.git

.github

Python cache files

test caches and coverage files

.env files

virtual environments

tests

editor metadata

OS-generated files

Secrets are therefore not intentionally copied into the Docker build context.

Docker CI validation

The Docker configuration is not only documented.

GitHub Actions executes:

docker build -t api-integration-lab .

after the automated test suite.

A successful workflow therefore verifies both:

22 automated tests
        +
successful Docker image build

This demonstrates containerization and deployment readiness without claiming that the application is currently deployed to a production hosting platform.

Automated tests

The project uses:

pytest

Run the complete suite:

python -m pytest -q

Current suite:

22 passed

Current automated coverage

The test suite covers behavior including:

health endpoint

text-processing endpoint

request validation

successful GitHub API integration

repository-not-found handling

transient external failures

retry recovery

maximum retry enforcement

prevention of unnecessary 404 retries

GitHub HTTP 429 handling

GitHub HTTP 403 rate-limit detection

generated request IDs

preservation of client-provided request IDs

successful Anthropic response parsing

missing Anthropic API key

Anthropic rate-limit handling

successful Gemini response parsing

missing Gemini API key

Gemini rate-limit handling

AI token-usage extraction

normalized AI-provider responses

valid HMAC webhook signatures

invalid webhook signatures

missing webhook signatures

missing webhook-server configuration

Mocked external services

Automated tests do not call real external APIs.

Instead, external responses are mocked.

This means CI can validate application behavior without:

exposing API keys

consuming paid API credits

depending on provider uptime

introducing non-deterministic external responses

The separation is:

Automated CI
    |
    v
Mock external APIs
    |
    v
Deterministic tests

Live provider validation can be performed separately when required, as demonstrated with the published Gemini client.

Continuous Integration

GitHub Actions runs on:

push -> main
pull request -> main

The current workflow is:

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
22 automated tests
        |
        v
Build Docker image
        |
        v
CI success

A successful workflow independently verifies that the repository can be checked out, dependencies installed, the test suite executed, and the Docker image built in a clean GitHub-hosted environment.

Project structure

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
│       ├── gemini_client.py
│       └── webhook_security.py
│
├── tests/
│   ├── test_api.py
│   ├── test_request_id.py
│   ├── test_resilience.py
│   ├── test_ai.py
│   ├── test_gemini.py
│   └── test_webhook.py
│
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
└── requirements.txt

Dependencies

The project intentionally keeps its dependency list small.

fastapi
uvicorn[standard]
httpx
pytest
pydantic-settings

External APIs are called directly with httpx.

No Anthropic or Gemini SDK is required.

Webhook HMAC verification uses Python standard-library modules.

Technologies

Python

FastAPI

Pydantic

Pydantic Settings

HTTPX

Pytest

Uvicorn

GitHub REST API

Anthropic Messages API

Google Gemini API

Webhooks

HMAC-SHA256

Docker

GitHub Actions

REST

JSON

environment variables

structured logging

CI/CD

Design principles

Explicit integrations

External-provider behavior is visible in the code rather than hidden behind large frameworks.

Separation of responsibilities

FastAPI endpoints remain small while provider-specific HTTP logic and webhook verification live in dedicated service modules.

Secret isolation

Credentials and webhook secrets remain outside source code and are supplied through environment configuration.

Bounded retries

Transient external-service failures are retried, but retries are limited.

Verified webhook authenticity

Inbound webhook payloads are accepted only after HMAC-SHA256 signature verification.

Observable behavior

Requests and external interactions generate structured logs and correlation identifiers.

Deterministic tests

Automated tests mock external systems and exercise controlled failure paths.

Reproducible CI

GitHub Actions validates both the Python test suite and Docker image build in a clean environment.

Purpose

This repository is intentionally designed as a small integration laboratory rather than a large production application.

Its purpose is to demonstrate practical backend engineering patterns around:

REST API integrations

AI services

third-party services

signed webhooks

provider abstraction

reliability

configuration

observability

error handling

test isolation

secret management

containerization

continuous integration

The emphasis is not simply on making an external API call.

The emphasis is on making integrations:

configurable
testable
observable
resilient
securely configurable
containerized
reproducible

Validation summary

GitHub REST integration        complete
Anthropic integration          complete
Anthropic automated tests      complete
Gemini integration             complete
Gemini live API validation     complete
Signed webhook integration     complete
HMAC-SHA256 verification       complete
Webhook automated tests        complete
Request tracing                complete
Structured logging             complete
Retry / backoff                complete
Rate-limit handling            complete
Environment configuration      complete
Secret isolation               complete
Docker containerization        complete
Docker build validation in CI  complete
GitHub Actions CI              complete

Automated test suite: 22 passed

The repository currently demonstrates a tested integration backend with external APIs, multi-provider AI access, signed webhook handling, containerization, and CI validation.
