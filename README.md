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