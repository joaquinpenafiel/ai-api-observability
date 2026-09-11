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

The initial architectural hypothesis was that SQLite write concurrency could become a scaling boundary, but this needed to be separated from HTTP-server and application-level effects.

A small local probe was therefore created to measure the system in two layers:

1. HTTP behavior through FastAPI/Uvicorn.
2. Direct concurrent writes through the same SQLite persistence function used by AI telemetry.

No external AI-provider requests were used during these tests.

### Test environment

The measurements were collected locally with:

- Windows
- Python 3.10.6
- a single Uvicorn process
- 200 operations per concurrency level
- concurrency levels: 1, 5, 10, 20 and 40
- temporary isolated SQLite databases for the write-contention probe

The deployed Docker runtime and CI use Python 3.12. The measurements below were produced by the local Python 3.10.6 environment and should therefore be interpreted as local benchmark results rather than deployed-runtime performance measurements.

The reproducible probe is available at:

[`scripts/load_probe.py`](../scripts/load_probe.py)

SQLite write-contention probe:

```bash
python scripts/load_probe.py sqlite --requests 200 --levels 1,5,10,20,40
```

HTTP probe, with the application already running locally:

```bash
python scripts/load_probe.py http --requests 200 --levels 1,5,10,20,40
```

These results describe this implementation and this environment. They are not presented as universal SQLite performance limits.

### HTTP baseline

The HTTP probe exercised two endpoints:

```text
POST /process
GET /stats
```

`/process` does not write telemetry to SQLite, while `/stats` reads aggregated SQLite metrics.

Across 200 requests per concurrency level, both endpoints completed with zero errors.

However, latency increased significantly as concurrency increased.

Representative results:

| Concurrency | `/process` RPS | `/process` p95 | `/stats` RPS | `/stats` p95 |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 83.71 | 13.12 ms | 73.29 | 14.56 ms |
| 5 | 78.77 | 96.06 ms | 80.95 | 81.14 ms |
| 10 | 54.33 | 346.33 ms | 60.37 | 251.36 ms |
| 20 | 42.11 | 1188.98 ms | 43.97 | 930.32 ms |
| 40 | 35.58 | 2632.18 ms | 41.64 | 2592.32 ms |

Because `/process` showed substantial latency degradation without using SQLite persistence, the HTTP experiment does not support attributing all high-concurrency degradation to SQLite.

This suggests that server/process scheduling, the local runtime, request handling or the probe itself may contribute before the persistence layer becomes relevant.

### SQLite write-contention probe

The second probe removed HTTP, FastAPI routing and Uvicorn from the path.

It called the same `record_ai_request()` persistence function directly from concurrent worker threads against an isolated temporary SQLite database.

The experiment was repeated multiple times and produced the same qualitative pattern:

- no lock errors at concurrency 1
- lock errors beginning at low concurrency
- increasing error rate as concurrency increased
- rapidly increasing tail latency
- little improvement in successful-write throughput

The final verification run produced:

| Concurrency | Successful writes | Lock errors | Error rate | Successful writes/s | p95 | p99 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 200 | 0 | 0.0% | 6.19 | 244.69 ms | 307.67 ms |
| 5 | 189 | 11 | 5.5% | 5.74 | 1391.92 ms | 5277.31 ms |
| 10 | 179 | 21 | 10.5% | 6.21 | 3711.08 ms | 9017.42 ms |
| 20 | 164 | 36 | 18.0% | 7.05 | 5521.34 ms | 7285.20 ms |
| 40 | 145 | 55 | 27.5% | 6.42 | 8727.59 ms | 11748.00 ms |

Latency percentiles in the SQLite table are calculated over successful writes only. Failed lock attempts are counted separately in the error rate and are not included in p50/p95/p99 latency calculations.

### Baseline cost before contention

One result deserves separate attention.

At concurrency 1, all 200 writes succeeded with zero lock errors, yet successful throughput was only 6.19 writes per second and p95 latency was 244.69 ms.

Because there is only one active writer at this level, this baseline cost cannot be explained by writer contention alone.

The current persistence path opens a new SQLite connection and commits every telemetry write independently. That connection/transaction lifecycle is therefore a candidate contributor to the observed baseline cost.

Other possible contributors include:

- Windows filesystem behavior
- storage characteristics
- SQLite journal and synchronous settings
- connection setup/teardown overhead
- local Python/runtime behavior

The current experiment does not isolate which of these factors dominates.

A follow-up experiment should therefore test the persistence pattern before concluding that SQLite itself is the primary limitation. In particular, useful controlled comparisons include:

- the current connection/commit pattern
- WAL mode
- longer-lived connections
- WAL combined with longer-lived connections

The goal of that experiment would be to distinguish a database-engine limitation from an implementation-level write-path limitation.

The important observation is not a universal throughput number.

It is the shape of the response.

Increasing concurrency from 1 to 40 did not materially increase successful-write throughput, which remained roughly in the same range, while lock errors and tail latency increased sharply.

Conceptually:

```text
more concurrent writers
        |
        v
write contention
        |
        +------> waiting / higher tail latency
        |
        +------> database lock errors
        |
        v
little additional useful throughput
```

### Interpretation

The measurements support the original architectural concern that the current SQLite write pattern has a measurable concurrency boundary.

Specifically, the current implementation opens a connection and commits each telemetry write independently.

Under concurrent direct writes, this pattern produces contention rather than proportional throughput growth.

This does not mean:

> SQLite can only handle approximately 6-7 writes per second.

That conclusion would be unsupported.

Different hardware, filesystem behavior, SQLite configuration, transaction batching, WAL mode, connection strategies and workload shapes could produce substantially different results.

The supported conclusion is narrower:

> In the measured local environment, the current per-write connection/commit pattern develops lock errors and severe tail-latency growth under concurrent writes, while successful-write throughput remains approximately flat.

### Architectural consequence

For the current portfolio-scale, low-volume, single-instance deployment, SQLite remains appropriate.

The benchmark does not justify replacing it today.

It does, however, provide a concrete migration signal.

If the application required sustained concurrent telemetry writes, background workers, multiple replicas or multi-tenant workloads, I would first evaluate:

- PostgreSQL
- longer-lived database connections
- batched or queued telemetry writes
- asynchronous persistence
- connection pooling
- workload-specific load testing

The decision to migrate should therefore be driven by measured workload requirements rather than technology preference.

### Remaining bottlenecks

SQLite is not the only possible scaling boundary.

The HTTP baseline showed substantial latency growth even on `/process`, which does not perform telemetry writes.

Additional investigation would be required before making claims about the first end-to-end bottleneck of the complete service.

Other possible pressure points include:

- single-process Uvicorn execution
- local Windows/Python scheduling behavior
- synchronous work inside request handling
- per-request creation of external `httpx.AsyncClient` instances
- external provider quotas and latency

The current evidence therefore separates two conclusions:

1. the full HTTP service degrades under higher local concurrency without producing errors in this test;
2. the current SQLite write pattern independently exhibits measurable lock contention under concurrent writes.

The principle remains:

> predict bottlenecks from architecture, isolate them experimentally, and claim only what the measurements support.

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
