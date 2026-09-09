# Architecture & Engineering Decisions

This document explains the main architectural decisions behind AI API Observability, the trade-offs accepted for the current scope, the known failure boundaries, and how the system would evolve if its requirements changed.

## 1. Context and Constraints

## 2. SQLite vs PostgreSQL

## 3. Direct HTTP vs Provider SDKs

## 4. HMAC-SHA256 Webhook Verification

## 5. Failure Modes

## 6. What Breaks First Under Load?

## 7. Evolution Toward Multi-Tenancy

## 8. What I Deliberately Did Not Build


# Architecture & Engineering Decisions

This document explains the main architectural decisions behind AI API Observability, the trade-offs accepted for the current scope, the known failure boundaries, and how the system would evolve if its requirements changed.

The goal is not to present the current architecture as universally scalable. The goal is to make clear why each component exists, what assumptions make it appropriate today, and which changes would invalidate those assumptions.

---

## 1. Context and Constraints

AI API Observability is a portfolio-scale backend service designed to make external API and AI-provider behavior inspectable.

The current system integrates GitHub REST, Gemini and Anthropic, and exposes operational telemetry including:

- provider and model
- input/output/total token usage
- estimated API cost
- request latency
- success/failure status
- correlation/request IDs
- recent request history and aggregated statistics

The current deployment intentionally targets a small, single-instance workload.

Important constraints are:

- one application instance
- low request volume
- no user authentication
- no multi-tenancy
- external AI providers may be intentionally disabled
- persistence must survive application redeployments
- CI must remain deterministic and secret-free
- implementation details should remain visible and inspectable for portfolio review

These constraints strongly influence the choices below.

---

## 2. SQLite vs PostgreSQL

### Current decision

The application uses SQLite through Python's standard `sqlite3` module and explicit SQL.

The database stores operational AI-request telemetry and currently runs inside a single application instance.

SQLite was appropriate for the current scope because it provides:

- durable relational persistence
- explicit SQL without an ORM abstraction
- no external database service dependency
- simple local and deployed operation
- sufficient capability for the current request volume
- straightforward aggregation for the `/stats` endpoint

The database layer also owns schema initialization, indexes, a small schema migration, and deterministic cost backfilling when historical token counts already exist.

### Trade-off accepted

SQLite keeps the system operationally small, but this simplicity creates a clear scaling boundary.

Writes ultimately target one database file. Under significant write concurrency, contention would become increasingly important. The current architecture also assumes that every application process can access the same local database file, which makes horizontal replication unsuitable without changing the persistence layer.

The connection currently uses a finite SQLite busy timeout rather than a distributed concurrency model.

### Migration triggers

I would reconsider SQLite if one or more of these requirements appeared:

- multiple application replicas
- sustained concurrent writes
- multi-tenant data isolation requirements
- significantly larger telemetry volume
- stronger operational backup/replication requirements
- independent workers writing telemetry
- more complex analytical workloads

At that point PostgreSQL would become the more appropriate default.

### Expected migration path

The application already separates telemetry persistence from provider clients and HTTP request handling.

A migration would therefore focus primarily on replacing the persistence implementation while preserving the service-level telemetry interface.

The likely evolution would be:

```text
Current

FastAPI
   |
Telemetry service
   |
SQLite


Future

FastAPI / Workers
       |
Telemetry service
       |
PostgreSQL
```

The important engineering decision is therefore not "SQLite is better than PostgreSQL."

It is:

> SQLite satisfies the current constraints with less operational complexity, while PostgreSQL becomes justified when concurrency, replication or tenancy requirements invalidate those constraints.

---

## 3. Direct HTTP vs Provider SDKs

### Current decision

GitHub, Gemini and Anthropic are integrated using direct `httpx` requests rather than provider-specific SDKs.

This makes several important behaviors explicit in the code:

- authentication headers
- endpoint construction
- request payloads
- timeout configuration
- retry behavior
- exponential backoff
- status-code mapping
- rate-limit detection
- response parsing
- token-usage extraction
- provider-specific normalization

For this project, that visibility is useful because integration behavior is one of the things the repository is intended to demonstrate.

### Benefits

Direct HTTP provides:

**Transparency**

The exact provider interaction is visible without relying on SDK internals.

**Testability**

HTTP behavior can be mocked and failure paths can be exercised deterministically.

**Provider normalization**

Gemini and Anthropic expose different response and usage structures. The application converts them into a smaller common representation.

**Explicit resilience behavior**

Timeouts, connection failures, transient server errors and rate limits are handled deliberately rather than implicitly.

### Trade-offs

Direct HTTP also creates maintenance work.

The application is responsible for:

- tracking provider API changes
- maintaining request/response parsing
- implementing resilience behavior
- supporting new provider capabilities manually

An SDK may become preferable if a provider introduces substantial functionality whose direct implementation would add complexity without increasing useful control.

Examples could include sophisticated streaming, large tool-calling interfaces or provider-specific session/state abstractions.

### Rate-limit behavior

The current implementation distinguishes rate limits from transient server failures.

Timeouts, connection errors and transient 5xx responses can trigger bounded retries with exponential backoff.

Rate-limit responses are currently surfaced to the caller as HTTP 429, preserving `Retry-After` when available, rather than automatically retrying for an unbounded or provider-controlled period.

This is intentional behavior that could evolve later if the service gained queueing, request budgets or asynchronous workers.

---

## 4. HMAC-SHA256 Webhook Verification

### Current decision

Inbound webhooks are authenticated using an HMAC-SHA256 signature generated over the raw request body and a shared secret.

The expected signature is compared using `hmac.compare_digest()`.

This provides two properties:

- payload integrity
- knowledge of the shared secret by the sender

A modified payload will not produce the expected signature.

### Why HMAC

For a small server-to-server webhook integration, HMAC provides a simple and well-understood authentication mechanism without requiring a complete user-authentication system.

It is also independent of the JSON structure because the signature is calculated from the raw body.

### Current limitation: replay protection

The current signature proves integrity/authenticity of the payload, but it does not prove freshness.

A previously valid signed request could theoretically be replayed if an attacker obtained both the original body and its signature.

A stronger production webhook protocol would add:

- signed timestamp
- accepted time window
- event ID or nonce
- duplicate-event detection

Conceptually:

```text
signature =
HMAC(
    secret,
    timestamp + "." + raw_body
)
```

The server would then reject old timestamps and already-processed event IDs.

This is not implemented in the current portfolio-scale endpoint.

---

## 5. Failure Modes

The application treats external failures as expected system behavior rather than assuming provider availability.

| Failure | Current behavior | Future evolution if required |
| --- | --- | --- |
| Provider timeout | bounded retry, then timeout response | queue / circuit breaker |
| Connection failure | bounded retry, then upstream failure | queue / circuit breaker |
| Transient provider 5xx | exponential-backoff retries | circuit breaker / async retry |
| Provider rate limit | return 429 and preserve `Retry-After` when available | scheduled retry / request budget |
| Invalid provider credentials | mapped provider authentication failure | secret monitoring / rotation |
| Provider intentionally disabled | explicit 503 | expected operational state |
| Missing webhook signature | reject request | unchanged |
| Invalid webhook signature | reject request | unchanged |
| Webhook replay | not currently prevented | timestamp + nonce/event ID |
| SQLite write contention | bounded by current SQLite behavior | PostgreSQL |
| Stale pricing table | inaccurate cost estimate | versioned/automated pricing data |

The distinction between a disabled provider and a failed provider is important.

If credentials are intentionally absent, the endpoint returns 503 but the event is not persisted as an AI-provider failure because no provider request actually occurred.

---

## 6. What Breaks First Under Load?

This section currently describes engineering hypotheses, not benchmark results.

No claim is made yet about a measured maximum throughput.

Several pressure points are visible from the current architecture.

### SQLite write concurrency

Every AI telemetry event produces a database write and commit.

At sufficiently high concurrency, serialized writes to the SQLite database file are an expected scaling boundary.

### Per-request external HTTP clients

Provider integrations currently create an `httpx.AsyncClient` within the request operation.

This keeps lifecycle management simple, but sustained high request volume would benefit from a longer-lived shared client and connection pooling strategy.

### Synchronous telemetry writes

Telemetry persistence uses synchronous SQLite operations.

At the current scale this keeps the implementation straightforward. Under heavier asynchronous workloads, persistence could move behind an asynchronous queue or worker so provider-response latency is not coupled to telemetry storage.

### External providers

Even if the application itself scaled perfectly, upstream quotas, latency and rate limits remain independent constraints.

Scaling the local service cannot eliminate provider-side capacity limits.

### Next step: measurement

Before replacing any component purely for expected scale, I would run controlled load tests and record:

- requests per second
- p50 latency
- p95 latency
- p99 latency
- error rate
- database-lock/contention behavior
- CPU usage
- memory usage

Only then should the first actual bottleneck be claimed.

The principle is:

> predict bottlenecks from architecture, but identify them through measurement.

---

## 7. Evolution Toward Multi-Tenancy

The current system is not multi-tenant.

Adding multi-tenancy would be an architectural change rather than a small feature.

At minimum, the system would need concepts such as:

```text
User
  |
Organization
  |
Tenant
  |
Authorization
  |
Tenant-scoped telemetry
```

Important additions would include:

- authentication
- organization/tenant identity
- RBAC or equivalent authorization
- tenant-scoped queries
- tenant isolation guarantees
- audit trails
- per-tenant provider credentials or credential policy
- quotas/rate limits
- database migration to a shared multi-user store such as PostgreSQL
- tests specifically attempting cross-tenant access

A `tenant_id` column alone would not constitute multi-tenancy.

The important property would be proving that requests belonging to tenant A cannot access tenant B's data.

---

## 8. What I Deliberately Did Not Build

The repository intentionally avoids adding infrastructure only to increase the technology count.

### PostgreSQL

Not required by the current single-instance, low-volume persistence model.

Migration becomes justified when concurrency, replication, worker or tenancy requirements appear.

### Kubernetes

The service currently has one deployable application and does not require cluster orchestration.

Adding Kubernetes would increase operational surface without solving a demonstrated requirement.

### Microservices

The current domains are small enough to remain understandable inside one service.

Splitting them prematurely would introduce network boundaries, distributed failure modes and deployment complexity without a demonstrated benefit.

### React or another frontend framework

The dashboard exists primarily to expose backend telemetry.

Plain HTML/CSS/JavaScript is sufficient for that requirement and keeps the project focused on backend engineering.

### Agent framework

The application integrates AI providers but does not currently implement an agentic workflow.

Adding an orchestration framework without an orchestration problem would increase complexity without demonstrating meaningful engineering.

### Authentication / multi-tenancy

The public deployment is intentionally read-only for provider-backed execution and is a portfolio service rather than a customer-facing SaaS platform.

If authenticated users or independent organizations became requirements, authentication and authorization would be designed together with the data model rather than added superficially.

---

## Engineering Principle

The architecture is intentionally smaller than the architecture that would be required for a large production platform.

That is a design decision, not an assumption that the current components scale indefinitely.

The repository aims to make three things explicit:

1. what the system needs today,
2. where its current boundaries are,
3. what evidence or requirements would justify changing it.

Complexity should be introduced when a requirement demands it, not when a technology exists.
