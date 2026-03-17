# /code-quality
**Trigger:** `/code-quality`
**Description:** For every class touched in this story branch — detect code smells, refactor
to clean readable code WITHOUT changing business logic, inject structured logging with MDC
trace context, add @Timed / @Counted metrics for Grafana/Micrometer, and update Spock specs
to cover the refactored code. Produces a Code Quality Report.

---

## Philosophy
> "Code is written once, read a hundred times."
> Every method should answer three questions at a glance:
> - **What** does it do? (name + single responsibility)
> - **Why** might it fail? (exception paths, logging)
> - **How long** did it take? (metrics, tracing)

Business logic is **never changed** — only structure, naming, observability, and readability.

---

## Steps

### 1. Get Changed Files
```bash
git diff main...HEAD --name-only -- "*.java" | grep -v "Test\|Spec\|config\|Config\|Dto\|Request\|Response"
```
Work through each file one at a time. Do not batch multiple files in a single pass.

---

### 2. For Each Changed File — Smell Detection Pass

Read the full file. For each method, flag any of the following:

#### 2a. Method Length Smell
Flag any method longer than **20 lines** (excluding blank lines and comments).
```
🟠 [ClassName].[methodName]() — [N] lines. Exceeds 20-line guideline. Extract sub-methods.
```

#### 2b. Too Many Parameters
Flag any method with **more than 3 parameters**.
```
🟠 [methodName](a, b, c, d) — 4 params. Consider a parameter object or builder.
```

#### 2c. Magic Numbers / Magic Strings
Flag any hardcoded numeric literal (not 0 or 1) or string literal used in logic.
```
🟠 if (status == 3) — magic number. Extract to a named constant or enum.
🟠 url.contains("/api/v1/") — magic string. Move to @Value property or constant.
```

#### 2d. Nested Conditionals (Arrow Code)
Flag any method with **3+ levels of if/else nesting** or nested ternaries.
```
🔴 [methodName]() — 4 levels of nesting. Apply guard clauses / early return pattern.
```

#### 2e. Commented-Out Code
Flag any blocks of commented-out production code.
```
🟠 Lines [N-M]: commented-out code block. Remove — version control is the history.
```

#### 2f. Catch-and-Swallow Exception — DETECT ONLY, DO NOT AUTO-FIX
Flag any `catch` block that is empty or only logs without rethrowing or handling.

**CRITICAL RULE:** If a swallowed exception exists in code that was written **before this story**
(i.e. the surrounding method is NOT in the `git diff` as a new `+` block), then:
- **DO NOT change the existing code**
- **DO update this workflow's report** with the finding
- **DO add it to the MD report** under "Existing Technical Debt — Swallowed Exceptions"
- **DO create a new Spock spec** that documents the current (broken) behaviour as a regression guard

If the swallowed exception is in **new code written for this story** (lines starting with `+` in the diff):
- Fix it immediately: log at `ERROR` + rethrow or wrap in a domain exception

Detection:
```bash
# Find all catch blocks in changed files
grep -n "catch" [ChangedFile].java
# For each catch block, check if it is empty or only has a comment
```

```
🔴 EXISTING DEBT [ClassName].[methodName]() line [N] — swallowed exception in PRE-EXISTING code.
   Action: DO NOT MODIFY. Added to NFR debt report. Regression guard Spock spec created.

🔴 NEW CODE [ClassName].[methodName]() line [N] — swallowed exception in THIS STORY's new code.
   Action: FIXED — log at ERROR + rethrow as ServiceException.
```

**Regression guard spec for existing swallowed exception (documents current behaviour):**
```groovy
def "existing swallowed exception in [methodName] — regression guard, do not change"() {
    given: "dependency throws an exception"
    mockDependency.[method](_) >> { throw new RuntimeException("simulated failure") }

    when: "the method is called — currently swallows the exception silently"
    service.[methodName](validInput())

    then: "no exception propagates — THIS IS EXISTING BEHAVIOUR, NOT CORRECT"
    // TODO [TECH-DEBT]: This catch block swallows exceptions. Tracked in debt report.
    // When fixed, change this to: thrown(ServiceException)
    noExceptionThrown()
}
```


#### 2g. Primitive Obsession
Flag where a raw `String` or `int` represents a domain concept (e.g. `String orderId`,
`int statusCode` as a business status).
```
🟡 String orderId — consider value object OrderId for type safety.
```

#### 2h. Missing or Vague Method Names
Flag method names that are vague: `process()`, `handle()`, `doStuff()`, `execute()`, `run()`.
```
🟠 process() — name is too vague. Rename to describe what is processed and what is returned.
```

#### 2j. Missing Feature Flag Guard on New Functionality
Scan new code (`+` lines in diff) for any new `@GetMapping`, `@PostMapping`, `@PutMapping`,
`@DeleteMapping`, `@KafkaListener`, or business logic method that does NOT call
`featureFlagService.isEnabled(...)` or check a `FeatureFlags` constant.

```bash
grep -n "^\+" /tmp/story-diff.txt | grep -E \
  "(@GetMapping|@PostMapping|@PutMapping|@DeleteMapping|@KafkaListener)" \
  > /tmp/cq-new-endpoints.txt

grep -n "isEnabled\|FeatureFlags\." /tmp/story-diff.txt \
  > /tmp/cq-flag-checks.txt

# If /tmp/cq-new-endpoints.txt has entries but /tmp/cq-flag-checks.txt is empty:
```

```
🔴 [ClassName].[method]() — new functionality with no feature flag guard.
   Action: Wrap with featureFlagService.isEnabled(FeatureFlags.[CONSTANT]) before proceeding.
   DO NOT auto-fix — flag name must be confirmed with developer.
```

**This is a BLOCKER.** Do not continue `/code-quality` until the flag guard is confirmed.
If the developer confirms the story does NOT require a flag, document the decision:
```java
// NO_FEATURE_FLAG: [reason — e.g. "pure refactor, no behaviour change"]
```

Flag methods in the service layer that have NONE of:
- A log statement at entry or exit
- An MDC trace context set
- A `@Timed` or `@Counted` annotation
```
🔴 [methodName]() — no logging, no metrics. Add structured log + @Timed.
```

---

### 3. Refactor Each Smell — Business Logic Unchanged

For each flagged smell, apply the following transformations. Show the before/after for every change.

#### 3a. Extract Long Method
```java
// ❌ Before — 35-line method doing 3 things
public OrderResponse processOrder(OrderRequest request) {
    // validate
    if (request.getItems() == null || request.getItems().isEmpty()) {
        throw new ValidationException("Items required");
    }
    // calculate total
    BigDecimal total = BigDecimal.ZERO;
    for (OrderItem item : request.getItems()) {
        total = total.add(item.getPrice().multiply(BigDecimal.valueOf(item.getQuantity())));
    }
    // persist
    Order order = new Order(request.getCustomerId(), request.getItems(), total);
    orderRepository.save(order);
    return new OrderResponse(order.getId(), total);
}

// ✅ After — each method is a named, testable unit
public OrderResponse processOrder(OrderRequest request) {
    validateOrderRequest(request);
    BigDecimal total = calculateOrderTotal(request.getItems());
    Order order = persistOrder(request, total);
    return toOrderResponse(order, total);
}

private void validateOrderRequest(OrderRequest request) {
    if (request.getItems() == null || request.getItems().isEmpty()) {
        throw new ValidationException("Order must contain at least one item");
    }
}

private BigDecimal calculateOrderTotal(List<OrderItem> items) {
    return items.stream()
        .map(item -> item.getPrice().multiply(BigDecimal.valueOf(item.getQuantity())))
        .reduce(BigDecimal.ZERO, BigDecimal::add);
}

private Order persistOrder(OrderRequest request, BigDecimal total) {
    Order order = Order.builder()
        .customerId(request.getCustomerId())
        .items(request.getItems())
        .total(total)
        .build();
    return orderRepository.save(order);
}
```

#### 3b. Replace Magic Numbers with Named Constants
```java
// ❌ Before
if (retryCount > 3) { ... }
if (status == 2) { ... }

// ✅ After
private static final int MAX_RETRY_ATTEMPTS = 3;
// or use an enum for status
if (retryCount > MAX_RETRY_ATTEMPTS) { ... }
if (order.getStatus() == OrderStatus.CONFIRMED) { ... }
```

#### 3c. Replace Nested Conditionals with Guard Clauses
```java
// ❌ Before — arrow code, 4 levels deep
public void fulfil(Order order) {
    if (order != null) {
        if (order.isConfirmed()) {
            if (!order.isFulfilled()) {
                if (inventory.isAvailable(order)) {
                    // actual logic here — buried 4 levels in
                    warehouse.dispatch(order);
                }
            }
        }
    }
}

// ✅ After — guard clauses, happy path reads top to bottom
public void fulfil(Order order) {
    if (order == null) throw new IllegalArgumentException("Order must not be null");
    if (!order.isConfirmed()) return;
    if (order.isFulfilled()) return;
    if (!inventory.isAvailable(order)) {
        log.warn("Inventory unavailable for orderId={}", order.getId());
        return;
    }
    warehouse.dispatch(order);
}
```

#### 3d. Replace Primitive Obsession with Value Object (lightweight)
```java
// ❌ Before
public Order findByOrderId(String orderId) { ... }

// ✅ After — type-safe, self-documenting
public record OrderId(String value) {
    public OrderId { Objects.requireNonNull(value, "OrderId must not be null"); }
}
public Optional<Order> findByOrderId(OrderId orderId) { ... }
```

#### 3e. Rescue Swallowed Exceptions
```java
// ❌ Before
try {
    externalClient.send(payload);
} catch (Exception e) {
    // nothing
}

// ✅ After
try {
    externalClient.send(payload);
} catch (ExternalClientException e) {
    log.error("Failed to send payload to external service. correlationId={} error={}",
        MDC.get("correlationId"), e.getMessage(), e);
    throw new ServiceException("External notification failed", e);
}
```

---

### 4. Inject Structured Logging with MDC Trace Context

For every service-layer method that is new or changed, apply this logging pattern.
Do NOT add logs to private helper methods unless they contain their own exception handling.

#### 4a. MDC Setup (must be at the entry point — Controller or a Filter)
```java
// In a request filter or aspect — sets trace context once per request
MDC.put("correlationId", UUID.randomUUID().toString());
MDC.put("storyId", "[STORY-ID]");       // from request header if present
MDC.put("service", "order-service");
// Clear in finally: MDC.clear()
```

#### 4b. Service Method Logging Pattern
```java
@Slf4j
@Service
public class OrderService {

    public OrderResponse processOrder(OrderRequest request) {
        log.info("Processing order. customerId={} itemCount={}",
            request.getCustomerId(), request.getItems().size());

        try {
            validateOrderRequest(request);
            BigDecimal total = calculateOrderTotal(request.getItems());
            Order order = persistOrder(request, total);

            log.info("Order processed successfully. orderId={} total={} customerId={}",
                order.getId(), total, request.getCustomerId());

            return toOrderResponse(order, total);

        } catch (ValidationException e) {
            log.warn("Order validation failed. customerId={} reason={}",
                request.getCustomerId(), e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("Unexpected error processing order. customerId={} error={}",
                request.getCustomerId(), e.getMessage(), e);
            throw new ServiceException("Order processing failed", e);
        }
    }
}
```

#### Logging Rules Applied Automatically:
- `log.info` at method **entry** with key business identifiers (IDs, counts — never PII)
- `log.info` at method **exit** with outcome identifiers
- `log.warn` for expected failures (validation, not-found, circuit open)
- `log.error` for unexpected failures — always include the exception object as the last arg
- Log messages use **key=value** format (not sentences) — makes ELK/Splunk parsing trivial:
  ```
  ✅ "Order processed. orderId={} customerId={} total={}"
  ❌ "The order with id {} was successfully processed for customer {}"
  ```
- NEVER log passwords, tokens, card numbers, full request bodies with PII
- Always include the primary domain ID in every log line within the method

---

### 5. Inject @Timed and @Counted Metrics (Micrometer → Grafana/Prometheus)

For every public service-layer method that is new or changed, add Micrometer annotations.

#### 5a. Add to pom.xml (if not present)
```xml
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
<!-- Enable @Timed AOP support -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-aop</artifactId>
</dependency>
```

Enable `@Timed` annotation processing in a config class:
```java
@Configuration
public class MetricsConfig {
    @Bean
    public TimedAspect timedAspect(MeterRegistry registry) {
        return new TimedAspect(registry);
    }
}
```

#### 5b. Annotation Pattern — Service Methods
```java
@Timed(
    value = "order.process.duration",          // metric name — noun.verb.unit
    description = "Time taken to process an order",
    percentiles = {0.5, 0.95, 0.99},           // p50, p95, p99 visible in Grafana
    histogram = true                            // enables latency heatmap
)
@Counted(
    value = "order.process.count",
    description = "Number of order processing attempts"
)
public OrderResponse processOrder(OrderRequest request) { ... }
```

#### 5c. Metric Naming Convention
```
[domain].[action].[unit]

order.process.duration        ← latency in seconds (Micrometer default)
order.process.count           ← call count (success + failure)
order.validation.failures     ← error counter (tag: reason)
inventory.check.duration      ← external call latency
payment.charge.duration       ← external call latency
```

#### 5d. Custom Tags for Grafana Filtering
```java
@Timed(
    value = "order.process.duration",
    extraTags = {"service", "order-service", "env", "${spring.profiles.active}"}
)
```

This allows Grafana dashboards to filter by `service` and `env` labels.

#### 5e. Manual Counter for Business Events (beyond @Timed)
```java
@Slf4j
@Service
public class OrderService {
    private final MeterRegistry meterRegistry;

    public OrderResponse processOrder(OrderRequest request) {
        // ... logic ...
        meterRegistry.counter("order.placed",
            "customerId", request.getCustomerId(),
            "channel", request.getChannel()
        ).increment();
    }
}
```

#### 5f. ELK Structured Log Fields (logback-spring.xml)
Ensure logback outputs JSON with MDC fields for ELK ingestion:
```xml
<!-- logback-spring.xml -->
<appender name="JSON" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="net.logstash.logback.encoder.LogstashEncoder">
        <includeMdcKeyName>correlationId</includeMdcKeyName>
        <includeMdcKeyName>service</includeMdcKeyName>
        <includeMdcKeyName>storyId</includeMdcKeyName>
    </encoder>
</appender>
```
Add dependency:
```xml
<dependency>
    <groupId>net.logstash.logback</groupId>
    <artifactId>logstash-logback-encoder</artifactId>
    <version>7.4</version>
</dependency>
```

---

### 6. Update Spock Specs for Refactored Code

For every extracted private method or renamed public method, update the Spock specs.
Private methods are tested indirectly through the public method — never use reflection to
test private methods.

For observability additions, add these spec blocks:

#### 6a. Verify Logging Behaviour (via Slf4j Test / Logback Appender capture)
```groovy
import ch.qos.logback.classic.Logger
import ch.qos.logback.classic.spi.ILoggingEvent
import ch.qos.logback.core.read.ListAppender
import org.slf4j.LoggerFactory

def "should log order processing with orderId and customerId"() {
    given: "a log appender capturing output"
    Logger logger = (Logger) LoggerFactory.getLogger(OrderService)
    def listAppender = new ListAppender<ILoggingEvent>()
    listAppender.start()
    logger.addAppender(listAppender)

    and: "a valid order request"
    def request = new OrderRequest(customerId: "CUST-1", items: [new OrderItem(price: 10.0, quantity: 2)])
    mockOrderRepository.save(_) >> new Order(id: "ORD-42")

    when:
    service.processOrder(request)

    then: "an INFO log contains the orderId"
    def logs = listAppender.list
    logs.any { it.level.toString() == "INFO" && it.formattedMessage.contains("ORD-42") }

    cleanup:
    logger.detachAppender(listAppender)
}
```

#### 6b. Verify @Timed Metric Is Registered
```groovy
import io.micrometer.core.instrument.MeterRegistry
import io.micrometer.core.instrument.simple.SimpleMeterRegistry

def "should record timing metric when processOrder is called"() {
    given:
    def registry = new SimpleMeterRegistry()
    // inject registry into service via constructor
    def service = new OrderService(mockRepo, registry)

    when:
    service.processOrder(validRequest())

    then: "a timer metric was recorded"
    def timer = registry.find("order.process.duration").timer()
    timer != null
    timer.count() == 1
}
```

#### 6c. Verify Exception Branch Logs at ERROR Level
```groovy
def "should log ERROR when repository throws unexpected exception"() {
    given:
    def listAppender = attachLogAppender(OrderService)
    mockOrderRepository.save(_) >> { throw new RuntimeException("DB down") }

    when:
    service.processOrder(validRequest())

    then:
    thrown(ServiceException)
    listAppender.list.any { it.level.toString() == "ERROR" && it.formattedMessage.contains("DB down") }
}
```

---

### 7. Generate Code Quality Report

Write `code-quality-report-[STORY-ID].md` to the repo root:

```markdown
# Code Quality Report — [STORY-ID]: [Story Title]

**Date:** [today]
**Branch:** [branch]

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Smells detected | [N] | 0 |
| Methods > 20 lines | [N] | 0 |
| Missing log statements | [N] | 0 |
| Missing @Timed metrics | [N] | 0 |
| Swallowed exceptions | [N] | 0 |
| Magic numbers/strings | [N] | 0 |
| JaCoCo line coverage | [X]% | [Y]% |
| JaCoCo branch coverage | [X]% | [Y]% |

---

## Refactored Files

### [ClassName].java
| Smell | Method | Action Taken |
|-------|--------|-------------|
| Method too long (35 lines) | processOrder() | Extracted: validateOrderRequest, calculateOrderTotal, persistOrder |
| Magic number (3) | retryLogic() | Extracted to MAX_RETRY_ATTEMPTS constant |
| Nested if (4 levels) | fulfil() | Replaced with guard clauses |
| Swallowed exception | sendNotification() | Now logs ERROR + wraps in ServiceException |

**Observability added:**
- `log.info` at entry/exit of processOrder(), createOrder()
- `log.warn` for validation failures
- `log.error` for unexpected exceptions with full stack
- MDC fields: correlationId, service, storyId
- `@Timed("order.process.duration")` on processOrder()
- `@Counted("order.process.count")` on processOrder()
- Manual counter: `order.placed` tagged by customerId, channel

---

## Metrics Available in Grafana After This Story

| Metric Name | Type | Labels | Use Case |
|-------------|------|--------|----------|
| `order.process.duration` | Timer (p50/p95/p99) | service, env | Latency SLA alerting |
| `order.process.count` | Counter | service, env | Throughput dashboard |
| `order.placed` | Counter | customerId, channel | Business KPI |
| `order.validation.failures` | Counter | reason | Error rate alerting |

---

## ELK Log Fields for This Story

Every log line from this service now contains:
```json
{
  "level": "INFO",
  "message": "Order processed successfully. orderId=ORD-42 total=20.00 customerId=CUST-1",
  "correlationId": "a1b2c3d4-...",
  "service": "order-service",
  "storyId": "PROJ-123",
  "logger": "com.example.order.OrderService",
  "timestamp": "2025-..."
}
```
ELK query to find all logs for an order: `correlationId:"a1b2c3d4" AND service:"order-service"`

---

## Spock Specs Added/Updated

| Spec File | New Test Blocks | Purpose |
|-----------|-----------------|---------|
| OrderServiceSpec.groovy | +3 | Logging content, @Timed registration, ERROR on exception |
| OrderControllerSpec.groovy | +1 | 400 on validation failure |

---

## Technical Debt — Existing Swallowed Exceptions (DO NOT MODIFY)

> These exceptions exist in pre-existing code outside the scope of this story.
> They have NOT been changed. Regression guard Spock specs have been added to document
> current behaviour and prevent silent regressions until a dedicated debt story fixes them.

| # | Class | Method | Line | Exception Swallowed | Regression Spec Added | Debt Story |
|---|-------|--------|------|--------------------|-----------------------|------------|
| 1 | [ClassName] | [methodName]() | [N] | RuntimeException | ✅ [ClassName]DebtSpec.groovy | TODO: raise story |

---

## ✅ Sign-Off Checklist
- [ ] 0 code smells remaining in **new** code written for this story
- [ ] All public service methods have entry/exit log statements
- [ ] All public service methods have @Timed annotation
- [ ] All exception paths log at WARN or ERROR
- [ ] MDC correlationId is set at request entry point
- [ ] Every new external API call has @Retry (max 3) + @CircuitBreaker + fallback
- [ ] Every new Kafka producer has retry config + DLT fallback
- [ ] Every new DB-calling method has @Retryable (transient only, max 3) + @Recover
- [ ] Retry Spock specs cover: success on retry, fallback after exhaustion, non-retryable skip
- [ ] Existing swallowed exceptions: NOT modified, documented in debt table, regression specs added
- [ ] JaCoCo thresholds still met after refactoring
- [ ] Spock specs updated for renamed/extracted methods
```

---

### 8. Final Coverage Run
```bash
./mvnw verify -pl [module] jacoco:report -q
```
Confirm thresholds still pass. If refactoring exposed previously-uncovered paths, add Spock
specs for them before completing.

### 9. Commit the Quality Pass
```bash
git add src/main src/test code-quality-report-*.md
git commit -m "refactor([STORY-ID]): apply code quality pass

- Extracted long methods, replaced magic numbers, removed nesting
- Added structured MDC logging to all service methods
- Added @Timed/@Counted metrics for Grafana
- Updated Spock specs for refactored code
- JaCoCo: line=[X]%, branch=[Y]%"
```

Next step → run `/nfr-check`
