# API Integration Lab

A reproducible REST API integration laboratory built with Python and FastAPI.

This project demonstrates API design, request validation, external service integration, error handling, automated testing, and continuous integration.

## Current capabilities

- REST API built with FastAPI
- GET and POST endpoints
- Request validation with Pydantic
- JSON input and structured responses
- Text normalization and data processing
- Asynchronous external API integration with `httpx`
- GitHub REST API integration
- Request timeout handling
- External connection error handling
- Controlled 404 responses
- Response normalization
- Automated tests with `pytest`
- Continuous Integration with GitHub Actions

## Architecture

```text
Client
  |
  v
FastAPI
  |
  +-- /health
  |
  +-- /process
  |
  +-- /github/{owner}/{repo}
             |
             v
      GitHub REST API
             |
             v
      Response normalization
```

The external API logic is separated from the application endpoints to keep responsibilities isolated.

```text
src/
├── main.py
└── services/
    └── github_client.py
```
## API endpoints

### Health check

```http
GET /health
```

Returns the current API status and a UTC timestamp.

Example response:

```json
{
  "status": "ok",
  "timestamp": "2026-08-25T00:00:00+00:00"
}
```

### Process data

```http
POST /process
```

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
  "processed_at": "2026-08-25T00:00:00+00:00"
}
```

Input text is validated before processing.

### GitHub repository integration

```http
GET /github/{owner}/{repo}
```

Example:

```http
GET /github/fastapi/fastapi
```

The application retrieves repository information from the GitHub REST API and returns a normalized response containing:

- Repository name
- Description
- Primary language
- Stars
- Forks
- Open issues
- Repository URL

The integration includes handling for:

- Request timeouts
- Connection failures
- Repository not found (`404`)
- Unexpected external API errors

## Environment configuration

Application configuration is centralized using `pydantic-settings`.

The project supports both operating-system environment variables and a local `.env` file.

Available configuration:

```text
APP_NAME
APP_VERSION
LOG_LEVEL
GITHUB_API_BASE
GITHUB_TIMEOUT_SECONDS
GITHUB_MAX_RETRIES
GITHUB_BACKOFF_SECONDS
GITHUB_TOKEN
```

A safe configuration template is provided in:

```text
.env.example
```

Real `.env` files are ignored by Git and should never be committed.

The GitHub token is optional and is never hardcoded in the application.

## Structured logging

Application logs are emitted as structured JSON.

Logged information can include:

- UTC timestamp
- log level
- logger name
- message
- HTTP method
- request path
- response status code
- request duration
- external repository
- external API status code
- rate-limit information
- request correlation ID
- exception information

This makes application behavior easier to inspect and trace across requests.

## Resilience and request tracing

The GitHub integration includes controlled resilience behavior for transient external failures.

Implemented behavior includes:

- configurable retry limits
- exponential backoff
- retries for connection failures
- retries for timeouts
- retries for HTTP `5xx` responses
- no retry for permanent `404` responses
- GitHub rate-limit detection
- HTTP `429` propagation
- `Retry-After` preservation when provided
- automatic `X-Request-ID` generation
- preservation of client-provided request IDs
- correlation IDs across API and external-service logs

A request ID can also be supplied manually:

```bash
curl -H "X-Request-ID: example-request-123" \
  http://127.0.0.1:8000/github/fastapi/fastapi
```

The same identifier is returned in the response and included in related structured logs.

## Running the project

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the API:

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

FastAPI interactive documentation is available at:

```text
/docs
```

## Automated tests

Run the test suite with:

```bash
python -m pytest -q
```

Current test coverage includes:

- Health endpoint
- Data processing endpoint
- Input validation
- Successful external API integration
- Repository-not-found behavior
- retry behavior after transient server failures
- recovery after external API failures
- maximum retry enforcement
- prevention of unnecessary retries for `404`
- HTTP `429` rate-limit handling
- GitHub `403` rate-limit detection
- generated request IDs
- preservation of client-provided request IDs

Current suite:

```text
12 passed
```

External API behavior is mocked during automated testing so the test suite does not depend on network availability or the GitHub API being reachable.

## Continuous Integration

GitHub Actions automatically runs the test suite on:

- Pushes to `main`
- Pull requests targeting `main`

The CI environment:

1. Checks out the repository
2. Sets up Python 3.12
3. Installs project dependencies
4. Executes the automated test suite

This provides an independent validation of the project after every relevant change.

## Project structure

```text
api-integration-lab/
├── .github/
│   └── workflows/
│       └── tests.yml
│
├── src/
│   ├── main.py
│   ├── config.py
│   ├── logging_config.py
│   ├── request_context.py
│   └── services/
│       └── github_client.py
│
├── tests/
│   ├── test_api.py
│   ├── test_request_id.py
│   └── test_resilience.py
│
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## Technologies

- Python
- FastAPI
- Pydantic
- Pydantic-settings
- Httpx
- Pytest
- GitHub REST API
- GitHub Actions