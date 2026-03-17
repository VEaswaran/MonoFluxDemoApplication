# /architecture-review
**Trigger:** `/architecture-review`
**Description:** Before any implementation begins on a new API, service, or integration,
perform a structured architecture review. Analyse the story's scale requirements, fault
tolerance needs, and communication patterns. Recommend the right technology stack from
first principles, present the trade-offs, ask the developer to confirm, then lock the
decision into a signed Architecture Decision Record (ADR) that guides the entire
`/develop-story` implementation.

This workflow produces a confirmation prompt — **no code is written until the developer
explicitly approves the architecture recommendation.**

---

## Philosophy
> "Every architectural decision made without understanding scale
>  becomes a rewrite at 10x traffic."
>
> A microservice built for 100 req/s that must handle 1M transactions/day
> needs a fundamentally different approach to one that handles 1,000/day.
> Thread-per-request, synchronous blocking, and unbounded queues are
> invisible at low load and catastrophic at scale.
> This review catches those decisions before the first line of code.

---

## Step 1 — Extract Scale and Load Profile from Story

Read the story and its intake report. Extract or ask for the following:

```
📊 SCALE PROFILE QUESTIONNAIRE

1. Expected throughput at launch?
   □ < 100 req/s (low)
   □ 100–1,000 req/s (medium)
   □ 1,000–10,000 req/s (high)
   □ > 10,000 req/s / millions of transactions/day (critical scale)
   □ Unknown — assume design for horizontal scale

2. Traffic pattern?
   □ Steady / predictable
   □ Spiky (e.g. flash sales, end-of-month billing, market open)
   □ Bursty ingest (batch uploads, event storms)
   □ Unknown

3. Latency requirement?
   □ Real-time user-facing (< 100ms p99)
   □ Near-real-time (< 500ms p99)
   □ Background / async (seconds acceptable)
   □ Batch (minutes acceptable)

4. Data consistency requirement?
   □ Strong consistency (financial transactions, inventory)
   □ Eventual consistency acceptable (analytics, notifications, feeds)
   □ Read-your-own-write (user profile, session data)

5. Downstream dependencies?
   □ Calls external APIs (number: ___)
   □ Reads/writes DB (tables: ___)
   □ Publishes/consumes Kafka (topics: ___)
   □ Calls other internal microservices (names: ___)

6. Failure tolerance?
   □ Must not lose data (financial, audit)
   □ Degraded mode acceptable (show cached/stale data)
   □ Can drop requests under extreme load (analytics, metrics)

7. Existing codebase pattern?
   □ Traditional Spring MVC (servlet/thread-per-request)
   □ Spring WebFlux (reactive/non-blocking)
   □ Mixed
```

If any answer is unknown, default to: **design for scale, exact numbers TBD**.
Log which assumptions were made — they go into the ADR.

---

## Step 2 — Communication Pattern Selection

Based on the scale profile, evaluate each communication pattern.
Present a scored recommendation with trade-offs. Do NOT just pick one silently.

### 2a. REST (Spring MVC / Feign / RestTemplate)

**Best for:**
- Simple CRUD operations with < 1,000 req/s
- Human-readable APIs consumed by external clients
- Teams without reactive programming experience

**Limitations at scale:**
- Thread-per-request blocks a thread during every I/O wait
- Default Tomcat thread pool: 200 threads → saturates at ~200 concurrent slow requests
- Feign is blocking by default — each call holds a thread for the full RTT

**Score for this story:** [LOW / MEDIUM / HIGH fit] — reason: [...]

---

### 2b. Spring WebFlux + Project Reactor (Mono / Flux)

**Best for:**
- High-concurrency I/O-bound services (API aggregators, gateway services)
- Services making multiple downstream calls that can be parallelised
- When a single pod must handle thousands of concurrent connections
- Streaming responses (SSE, chunked transfer)

**How it scales:**
- Event-loop model (Netty) — a handful of threads handle thousands of concurrent requests
- No thread blocked during DB query or HTTP call — CPU used only when work is available
- `Mono.zip()` / `Flux.merge()` run downstream calls truly in parallel
- Backpressure prevents OOM under burst load

**Trade-offs:**
- Steeper learning curve — entire call chain must be reactive (no blocking calls)
- Debugging stack traces are harder to read
- JPA is blocking — requires R2DBC for reactive DB access
- Cannot mix blocking and non-blocking easily

**Reactive patterns for this story:**
```java
// Parallel downstream calls — saves sum of latencies, pays max latency
public Mono<OrderSummary> buildOrderSummary(String orderId) {
    return Mono.zip(
        orderService.findById(orderId),          // 50ms
        pricingClient.getPrices(orderId),         // 80ms
        inventoryClient.checkStock(orderId)       // 60ms
    ).map(tuple -> OrderSummary.from(
        tuple.getT1(), tuple.getT2(), tuple.getT3()
    ));
    // Total: ~80ms (max) not 190ms (sum)
}

// Backpressure-aware stream
public Flux<OrderEvent> streamEvents(String customerId) {
    return eventRepository.findByCustomerId(customerId)
        .delayElements(Duration.ofMillis(10))
        .onErrorResume(e -> Flux.empty());
}
```

**Score for this story:** [LOW / MEDIUM / HIGH fit] — reason: [...]

---

### 2c. gRPC (Protocol Buffers over HTTP/2)

**Best for:**
- **Internal microservice-to-microservice** communication at high throughput
- When payload size matters (binary serialisation is 3–10x smaller than JSON)
- Streaming use cases (server-streaming, bidirectional streaming)
- When strict API contracts between services are required
- Low-latency internal calls (trading systems, real-time analytics)

**How it scales:**
- HTTP/2 multiplexing — many calls over a single TCP connection
- Binary protobuf: smaller payload = less network, less GC pressure
- Strongly typed contracts via `.proto` files — breaking changes caught at compile time
- Native streaming: server can push events continuously to a client

**Trade-offs:**
- Not human-readable — harder to debug without tooling (grpcurl, Postman gRPC)
- External/browser clients cannot call gRPC directly without a proxy (grpc-web)
- Requires `.proto` schema management and shared generated stubs
- Not suitable for public-facing APIs

**When to combine with REST:**
Use gRPC for internal service calls, expose REST/GraphQL externally:
```
External Client → REST/GraphQL API Gateway → gRPC → [internal microservices]
```

**Spring Boot setup:**
```xml
<dependency>
    <groupId>net.devh</groupId>
    <artifactId>grpc-spring-boot-starter</artifactId>
    <version>2.15.0.RELEASE</version>
</dependency>
```

**Score for this story:** [LOW / MEDIUM / HIGH fit] — reason: [...]

---

### 2d. GraphQL (Spring for GraphQL)

**Best for:**
- APIs consumed by multiple clients with different data shape needs (mobile vs web vs partner)
- Reducing over-fetching and under-fetching (clients request exactly what they need)
- Aggregating data from multiple sources into a single response
- When the API schema evolves frequently and versioning is painful

**How it scales:**
- Single endpoint — no REST versioning sprawl
- DataLoader pattern batches N+1 queries automatically
- Subscription support for real-time push (over WebSocket)
- Federation enables splitting the schema across microservices

**Trade-offs:**
- N+1 query risk without DataLoader (must be explicitly configured)
- Complex queries can be expensive — must implement query depth/complexity limits
- Caching is harder than REST (POST body varies per request)
- Not suitable for simple CRUD with no varied client needs

**Spring for GraphQL setup:**
```java
@Controller
public class OrderGraphQLController {

    @QueryMapping
    public Mono<Order> order(@Argument String id) {
        return orderService.findById(id);
    }

    @MutationMapping
    public Mono<Order> createOrder(@Argument OrderInput input) {
        return orderService.create(input);
    }

    @SubscriptionMapping
    public Flux<OrderEvent> orderEvents(@Argument String customerId) {
        return orderEventService.streamFor(customerId);
    }
}
```

**Score for this story:** [LOW / MEDIUM / HIGH fit] — reason: [...]

---

### 2e. Kafka (Event-Driven / Async)

**Best for:**
- Decoupling producers from consumers at scale
- Fire-and-forget operations where the caller does not need an immediate response
- Fan-out: one event consumed by multiple services
- Buffering burst load — Kafka absorbs spikes, consumers process at their own pace
- Audit trails and event sourcing
- When strong ordering guarantees are needed within a partition

**How it scales:**
- Kafka partitions allow horizontal scaling of consumers in lockstep
- A topic with 12 partitions can be consumed by up to 12 consumer instances in parallel
- Kafka retains messages — consumers can replay from any offset
- Exactly-once semantics available with idempotent producers + transactional consumers

**Trade-offs:**
- Asynchronous — caller does not get a synchronous response
- Additional infrastructure dependency
- Message schema evolution requires care (Avro + Schema Registry recommended at scale)
- Dead Letter Topics required for poison pill handling

**Score for this story:** [LOW / MEDIUM / HIGH fit] — reason: [...]

---

### 2f. Hybrid Pattern (API + Kafka)

**Best for:**
- Accepting requests synchronously (REST/gRPC), processing asynchronously (Kafka)
- The "accept, acknowledge, process" pattern for high-throughput writes:
  ```
  POST /orders → 202 Accepted → Kafka → OrderProcessor → DB → notify
  ```
- Separating the user-facing latency concern from the processing concern

**Example — Accept and Acknowledge:**
```java
@PostMapping("/orders")
public ResponseEntity<OrderAcknowledgement> placeOrder(@RequestBody OrderRequest request) {
    String correlationId = UUID.randomUUID().toString();
    kafkaTemplate.send("order-requests", correlationId, request);  // async
    log.info("Order accepted. correlationId={} customerId={}",
        correlationId, request.getCustomerId());
    return ResponseEntity.accepted()
        .body(new OrderAcknowledgement(correlationId, "ORDER_RECEIVED"));
}
```

**Score for this story:** [LOW / MEDIUM / HIGH fit] — reason: [...]

---

## Step 3 — Resilience Pattern Selection

For every integration identified in the story, select the appropriate resilience pattern.

### Resilience Decision Matrix

| Scenario | Pattern | Why |
|----------|---------|-----|
| External API call, caller needs response | Circuit Breaker + Retry (Resilience4j) | Fail fast, retry transient errors, open circuit on sustained failure |
| Internal service call, latency matters | Circuit Breaker + Bulkhead | Isolate thread pools, prevent cascade failure |
| High-throughput write that can be async | Kafka + DLT | Decouple, buffer, retry via consumer, DLT for poison pills |
| DB write that must not be lost | @Retryable (transient only) + outbox pattern | Retry connection errors, outbox for guaranteed Kafka delivery |
| Read that can tolerate stale data | Circuit Breaker + Cache fallback | Return cached value when downstream is down |
| Bulk operation with partial failure | Bulkhead + per-item error handling | Isolate failures, process what succeeded |

### 3a. Circuit Breaker Sizing (Resilience4j)
```yaml
resilience4j:
  circuit-breaker:
    instances:
      [service-name]:
        # Sliding window: last 10 calls
        sliding-window-size: 10
        # Open circuit if 50% of calls fail
        failure-rate-threshold: 50
        # Slow call threshold — treat calls > 2s as failures
        slow-call-duration-threshold: 2s
        slow-call-rate-threshold: 80
        # Stay open for 10s before trying half-open
        wait-duration-in-open-state: 10s
        # Try 3 calls in half-open before deciding
        permitted-number-of-calls-in-half-open-state: 3
        # Minimum calls before evaluating failure rate
        minimum-number-of-calls: 5
```

### 3b. Bulkhead — Thread Pool Isolation
Use when one slow downstream must not starve the entire service:
```yaml
resilience4j:
  bulkhead:
    instances:
      pricing-service:
        max-concurrent-calls: 20      # max threads for pricing calls
        max-wait-duration: 100ms      # queue wait before BulkheadFullException
      inventory-service:
        max-concurrent-calls: 10
        max-wait-duration: 50ms
```

### 3c. Rate Limiter — Protect Downstream
```yaml
resilience4j:
  rate-limiter:
    instances:
      external-payment-api:
        limit-for-period: 100         # 100 calls per refresh period
        limit-refresh-period: 1s      # per second
        timeout-duration: 0s          # reject immediately if limit hit
```

---

## Step 4 — Generate Architecture Recommendation

Based on Steps 1–3, produce a structured recommendation.
This is presented to the developer for **explicit confirmation before any code is written.**

```
╔══════════════════════════════════════════════════════════════════════════╗
║          ARCHITECTURE RECOMMENDATION — [STORY-ID]: [TITLE]              ║
╚══════════════════════════════════════════════════════════════════════════╝

📊 SCALE PROFILE SUMMARY
  Throughput:     [X] req/s at launch, designed for [Y]x headroom
  Latency SLA:    < [N]ms p99
  Traffic:        [steady / spiky / bursty]
  Consistency:    [strong / eventual]
  Failure mode:   [must not lose data / degraded mode ok / can drop]

─────────────────────────────────────────────────────────────────────────
🏗️  RECOMMENDED APPROACH
─────────────────────────────────────────────────────────────────────────

  Primary pattern:   [REST + WebFlux / gRPC / GraphQL / Kafka / Hybrid]
  Resilience:        [Circuit Breaker / Bulkhead / Rate Limiter / Retry]
  Consistency:       [Synchronous / Async + Kafka / Outbox]
  Reactive:          [YES — WebFlux/Mono/Flux / NO — MVC sufficient]

─────────────────────────────────────────────────────────────────────────
📋  OPTION COMPARISON
─────────────────────────────────────────────────────────────────────────

  Option A — [Name] (RECOMMENDED ✅)
  ┌─────────────────────────────────────────────────────┐
  │ Fits requirements:  [reasons]                       │
  │ Scale ceiling:      [handles up to X req/s per pod] │
  │ Failure behaviour:  [what happens when downstream   │
  │                      is unavailable]                │
  │ Complexity:         [LOW / MEDIUM / HIGH]           │
  │ Team familiarity:   [check existing codebase]       │
  └─────────────────────────────────────────────────────┘

  Option B — [Name]
  ┌─────────────────────────────────────────────────────┐
  │ Fits requirements:  [reasons]                       │
  │ When to prefer:     [specific conditions]           │
  │ Why not recommended now: [clear reason]             │
  └─────────────────────────────────────────────────────┘

  Option C — [Name] (NOT RECOMMENDED for this story ❌)
  ┌─────────────────────────────────────────────────────┐
  │ Why not:  [clear reason without jargon]             │
  └─────────────────────────────────────────────────────┘

─────────────────────────────────────────────────────────────────────────
⚠️  RISKS IF WRONG CHOICE IS MADE
─────────────────────────────────────────────────────────────────────────

  If REST MVC chosen instead of WebFlux:
    → At [N] req/s, Tomcat thread pool exhausts in [calculation]
    → Each blocked thread consumes ~1MB stack → OOM risk at scale

  If synchronous instead of Kafka:
    → [downstream service] failure causes [this service] to fail
    → No buffering — traffic spike causes request loss

  If no circuit breaker:
    → [downstream] latency spike cascades to this service
    → Timeout threads pile up → eventual pod crash

─────────────────────────────────────────────────────────────────────────
🔧  IMPLEMENTATION BLUEPRINT (if confirmed)
─────────────────────────────────────────────────────────────────────────

  Layer          Technology              Reason
  ─────────────────────────────────────────────────────
  API            [REST/gRPC/GraphQL]    [one-line reason]
  Reactive       [WebFlux/MVC]          [one-line reason]
  DB access      [JPA/R2DBC]            [one-line reason]
  Resilience     [CB + Retry / Bulkhead] [one-line reason]
  Async          [Kafka / sync]          [one-line reason]
  Caching        [Redis / none]          [one-line reason]
  Observability  [@Timed + MDC + ELK]    always

─────────────────────────────────────────────────────────────────────────
❓  DECISION REQUIRED FROM DEVELOPER
─────────────────────────────────────────────────────────────────────────

  Please confirm one of:

  [A] ✅ Proceed with Option A (recommended)
  [B] Proceed with Option B — reason: ___________
  [C] I need to discuss with the team first

  Type your choice to continue.
```

**Do not write any code, create any files, or proceed to `/plan-story` until the
developer types their choice.**

---

## Step 5 — Developer Confirms Architecture

When the developer confirms (e.g. types `A`):

1. Acknowledge the choice and state what will be built:
```
✅ Architecture confirmed: [Option A — description]

This story will be implemented using:
  • [communication pattern]
  • [reactive / blocking]
  • [resilience patterns]
  • [async/sync boundary]

Proceeding to generate Architecture Decision Record (ADR)...
```

2. If the developer chooses Option B (non-recommended):
```
Understood. Proceeding with Option B.
⚠️ Note: This choice introduces [specific risk]. Ensure the team is aware.
Logging deviation in ADR.
```

3. If the developer requests team discussion (`C`): stop the workflow and output:
```
⏸️ Architecture review paused. Raise the options above in your team's
architecture forum or Slack channel. Re-run /architecture-review when
a decision is made.
```

---

## Step 6 — Write the Architecture Decision Record (ADR)

Save `docs/adr/ADR-[STORY-ID]-[short-title].md` in the repository:

```markdown
# ADR-[STORY-ID]: [Short Title]

**Date:** [today]
**Story:** [STORY-ID] — [title]
**Status:** Accepted
**Decided by:** [developer name]
**Reviewed by:** Cascade /architecture-review

---

## Context

[2–3 sentences: what the story requires, what scale it must handle,
what the key constraint is that drove the decision]

## Scale Profile

| Dimension | Value | Source |
|-----------|-------|--------|
| Throughput | [X] req/s | Story intake / assumption |
| Latency SLA | < [N]ms p99 | Story intake / assumption |
| Traffic pattern | [steady/spiky] | Story intake |
| Consistency | [strong/eventual] | Story intake |
| Failure mode | [lose/degrade/drop] | Story intake |

## Decision

**Chosen approach:** [Option A — e.g. WebFlux + Resilience4j CB + Kafka async write]

## Technology Selections

| Layer | Technology | Version | Reason |
|-------|-----------|---------|--------|
| API style | [REST / gRPC / GraphQL] | [version] | [one-line reason] |
| Reactive | [WebFlux + Netty / Spring MVC + Tomcat] | Spring Boot 3.x | [reason] |
| DB access | [JPA / R2DBC] | [version] | [reason] |
| Resilience | [Resilience4j CB + Retry / Spring Retry] | [version] | [reason] |
| Async comms | [Kafka / synchronous] | [version] | [reason] |
| Caching | [Redis / Caffeine / none] | [version] | [reason] |

## Considered Alternatives

| Option | Why Rejected |
|--------|-------------|
| Option B | [specific reason it does not fit] |
| Option C | [specific reason it does not fit] |

## Consequences

**Positive:**
- [specific benefit at the chosen scale]
- [specific resilience behaviour on failure]

**Negative / Trade-offs:**
- [specific complexity cost]
- [specific operational requirement — e.g. need R2DBC driver]

**Risks if scale assumption is wrong:**
- [what needs to change if throughput is 10x higher than assumed]

## Assumptions Made
[List any scale numbers that were assumed because the story did not specify them]
- Throughput assumed: [X] req/s — confirm with PO if story goes to production
- Consistency model assumed: eventual — confirm if financial data is involved

## Implementation Constraints for /develop-story

The following MUST be enforced during implementation:
- [ ] [specific constraint derived from this decision, e.g. "no blocking calls on reactive thread"]
- [ ] [specific constraint, e.g. "all downstream calls via circuit breaker"]
- [ ] [specific constraint, e.g. "DB access via R2DBC only — no JPA"]
- [ ] Spock spec must include: load behaviour test, fallback test, circuit open test
```

---

## Step 7 — Inject ADR Constraints into /develop-story

Once the ADR is written, extract the `Implementation Constraints` checklist and
prepend it to the `develop-story` Implement step for this session:

```
📋 ADR CONSTRAINTS ACTIVE FOR THIS STORY — [STORY-ID]
(from docs/adr/ADR-[STORY-ID]-[short-title].md)

  ✅ Communication: [e.g. WebFlux Mono/Flux — no blocking operators]
  ✅ Resilience:    [e.g. @CircuitBreaker + @Retry on all external calls]
  ✅ Async:         [e.g. POST returns 202 Accepted, processing via Kafka]
  ✅ DB:            [e.g. R2DBC — no JPA blocking calls]
  ✅ Caching:       [e.g. Redis @Cacheable on pricing reads]

  If any code written by Cascade violates these constraints, STOP and flag.
```

---

## Step 8 — Architecture-Specific Spock Spec Requirements

Based on the confirmed architecture, add these mandatory spec categories to `/develop-story`:

### If WebFlux (Reactive):
```groovy
// Verify non-blocking — reactive chain returns Mono/Flux, not void/object
def "should return Mono<OrderResponse> — not block the calling thread"() {
    given:
    mockRepo.findById(_) >> Mono.just(order)

    when:
    def result = service.processOrder(request)

    then: "result is a Mono — reactive, not blocked"
    result instanceof Mono
    StepVerifier.create(result)
        .expectNextMatches { it.orderId == "ORD-1" }
        .verifyComplete()
}

// Verify parallel downstream calls
def "should fetch price and inventory in parallel, not sequentially"() {
    given:
    def pricingDelay = Duration.ofMillis(100)
    def inventoryDelay = Duration.ofMillis(80)
    mockPricingClient.getPrice(_) >> Mono.just(price).delayElement(pricingDelay)
    mockInventoryClient.checkStock(_) >> Mono.just(stock).delayElement(inventoryDelay)

    when:
    def stopwatch = Stopwatch.createStarted()
    service.buildSummary("ORD-1").block()
    def elapsed = stopwatch.elapsed(MILLISECONDS)

    then: "total time ≈ max(100, 80) not sum(100 + 80)"
    elapsed < 150  // parallel, not sequential
}
```

### If Circuit Breaker:
```groovy
def "should open circuit after 5 consecutive failures and return fallback"() {
    given: "downstream always fails"
    mockClient.call(_) >> { throw new IOException("service down") }

    when: "enough calls to open the circuit"
    (1..10).each { service.callDownstream("input-$it") }
    def result = service.callDownstream("final-call")

    then: "fallback response returned, not exception"
    result == FallbackResponse.DEFAULT
    noExceptionThrown()
}

def "should half-open and recover when downstream comes back"() {
    given: "first 5 fail, then succeed"
    mockClient.call(_) >>>
        ([{ throw new IOException() }] * 5) + [new SuccessResponse()]

    when:
    def results = (1..6).collect { service.callDownstream("input") }

    then: "last call succeeds — circuit recovered"
    results.last() instanceof SuccessResponse
}
```

### If gRPC:
```groovy
def "should call gRPC service with correct proto message"() {
    given:
    def expectedRequest = OrderRequest.newBuilder()
        .setOrderId("ORD-1")
        .setCustomerId("CUST-1")
        .build()
    mockGrpcStub.processOrder(expectedRequest) >> OrderResponse.newBuilder()
        .setStatus("CONFIRMED").build()

    when:
    def result = service.processOrder("ORD-1", "CUST-1")

    then:
    result.status == "CONFIRMED"
    1 * mockGrpcStub.processOrder(expectedRequest)
}
```

### If GraphQL:
```groovy
def "should resolve order query with correct fields"() {
    given:
    mockOrderService.findById("ORD-1") >> Mono.just(order)

    when:
    def result = graphQlTester
        .document("""
            query { order(id: "ORD-1") { id status total } }
        """)
        .execute()

    then:
    result.path("order.id").entity(String).isEqualTo("ORD-1")
    result.path("order.status").entity(String).isEqualTo("CONFIRMED")
}
```

---

## Step 9 — Commit the ADR
```bash
git add docs/adr/ADR-[STORY-ID]-*.md
git commit -m "docs([STORY-ID]): add architecture decision record

- Pattern: [chosen communication pattern]
- Reactive: [YES WebFlux / NO MVC]
- Resilience: [CB + Retry / Bulkhead]
- Async: [Kafka / sync]
- Reviewed by: Cascade /architecture-review"
```

Next step → run `/plan-story`
