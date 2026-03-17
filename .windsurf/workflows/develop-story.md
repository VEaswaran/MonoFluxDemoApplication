# /develop-story
**Trigger:** `/develop-story`
**Description:** TDD development loop — write Spock specs first, implement until green, verify JaCoCo coverage meets threshold, then commit.

---

## Steps

### 1. Confirm Pre-Conditions
- Review summary from `/review-story` is available
- Feature branch is checked out: `git branch --show-current`
- No uncommitted changes from a previous session: `git status`

### 2. Detect Integration Type — API / Kafka / DB
Before writing any spec or implementation, identify what external integration this story touches.
Run:
```bash
git diff main...HEAD --name-only -- "*.java" "*.groovy" "*.yml"
grep -rn "FeignClient\|RestTemplate\|WebClient\|KafkaTemplate\|@KafkaListener\|JpaRepository\|CrudRepository\|JdbcTemplate" \
  src/main/java --include="*.java" -l
```

For **each** integration type found, the retry scaffold below is MANDATORY before writing
any business logic. Do not skip this step.

---

#### 2a. External API Call — Resilience4j Retry + Circuit Breaker

If the story introduces or modifies a FeignClient, RestTemplate, or WebClient call:

**Step 1 — Check `application.yml` for existing Resilience4j config:**
```bash
grep -A 20 "resilience4j" src/main/resources/application.yml
```

**Step 2 — Add or verify this config block exists (max 3 retries):**
```yaml
# application.yml
resilience4j:
  retry:
    instances:
      [service-name]-retry:                      # e.g. pricing-service-retry
        max-attempts: 3
        wait-duration: 500ms
        retry-exceptions:
          - feign.FeignException
          - java.net.SocketTimeoutException
          - java.io.IOException
        ignore-exceptions:
          - com.example.exception.ValidationException
          - com.example.exception.NotFoundException
        enable-exponential-backoff: true
        exponential-backoff-multiplier: 2         # 500ms → 1000ms → 2000ms

  circuit-breaker:
    instances:
      [service-name]-cb:
        sliding-window-size: 10
        failure-rate-threshold: 50
        wait-duration-in-open-state: 10s
        permitted-number-of-calls-in-half-open-state: 3
```

**Step 3 — Apply annotations on the service method:**
```java
@Retry(name = "[service-name]-retry", fallbackMethod = "fetchPriceFallback")
@CircuitBreaker(name = "[service-name]-cb", fallbackMethod = "fetchPriceFallback")
@Timed(value = "pricing.fetch.duration", percentiles = {0.5, 0.95, 0.99})
public PriceResponse fetchPrice(String productId) {
    log.info("Fetching price. productId={}", productId);
    PriceResponse response = pricingClient.getPrice(productId);
    log.info("Price fetched. productId={} price={}", productId, response.getPrice());
    return response;
}

// Fallback — same signature + Throwable as last param
public PriceResponse fetchPriceFallback(String productId, Throwable ex) {
    log.warn("Price fetch failed after retries. productId={} error={} fallback=default",
        productId, ex.getMessage());
    return PriceResponse.defaultPrice();
}
```

**Step 4 — FeignClient config (timeout + retry at transport level):**
```java
@FeignClient(
    name = "[service-name]",
    url = "${clients.[service-name].url}",
    configuration = FeignClientConfig.class
)
public interface [ServiceName]Client { ... }

// FeignClientConfig.java
@Configuration
public class FeignClientConfig {
    @Bean
    public Request.Options requestOptions() {
        return new Request.Options(
            2, TimeUnit.SECONDS,   // connectTimeout
            5, TimeUnit.SECONDS,   // readTimeout
            true
        );
    }
}
```

---

#### 2b. Kafka Producer — Retry + Dead Letter Topic

If the story introduces or modifies a `KafkaTemplate.send()` call:

**Step 1 — Check `application.yml` for existing Kafka producer config:**
```bash
grep -A 30 "kafka" src/main/resources/application.yml | grep -A 10 "producer"
```

**Step 2 — Add or verify producer retry config (max 3 retries):**
```yaml
spring:
  kafka:
    producer:
      retries: 3
      properties:
        retry.backoff.ms: 500
        delivery.timeout.ms: 10000
        request.timeout.ms: 3000
        enable.idempotence: true          # exactly-once semantics
        max.in.flight.requests.per.connection: 1
```

**Step 3 — Service-layer Kafka send with retry and error handling:**
```java
@Retry(name = "kafka-retry", fallbackMethod = "publishEventFallback")
@Timed(value = "order.event.publish.duration", percentiles = {0.5, 0.95, 0.99})
public void publishOrderEvent(OrderEvent event) {
    log.info("Publishing order event. orderId={} eventType={}",
        event.getOrderId(), event.getType());
    try {
        SendResult<String, OrderEvent> result = kafkaTemplate
            .send(ORDER_TOPIC, event.getOrderId(), event)
            .get(5, TimeUnit.SECONDS);                  // block only in sync path
        log.info("Order event published. orderId={} partition={} offset={}",
            event.getOrderId(),
            result.getRecordMetadata().partition(),
            result.getRecordMetadata().offset());
    } catch (Exception e) {
        log.error("Failed to publish order event. orderId={} eventType={} error={}",
            event.getOrderId(), event.getType(), e.getMessage(), e);
        throw new KafkaPublishException("Event publish failed for orderId=" + event.getOrderId(), e);
    }
}

public void publishEventFallback(OrderEvent event, Throwable ex) {
    log.error("Kafka publish exhausted all retries. orderId={} eventType={} error={}. Routing to DLT.",
        event.getOrderId(), event.getType(), ex.getMessage());
    deadLetterTemplate.send(ORDER_TOPIC + ".DLT", event.getOrderId(), event);
    meterRegistry.counter("order.event.publish.dlt", "eventType", event.getType()).increment();
}
```

**Step 4 — Kafka Consumer retry + DLT config:**
```yaml
spring:
  kafka:
    listener:
      ack-mode: MANUAL_IMMEDIATE
    consumer:
      enable-auto-commit: false
      properties:
        isolation.level: read_committed

# Dead letter topic
  kafka:
    retry:
      topic:
        attempts: 3
        delay: 1000
        multiplier: 2.0
        max-delay: 10000
```

```java
@KafkaListener(topics = "${kafka.topics.orders}", groupId = "${kafka.group-id}")
@Timed(value = "order.event.consume.duration")
public void consumeOrderEvent(
        @Payload OrderEvent event,
        @Header(KafkaHeaders.RECEIVED_TOPIC) String topic,
        Acknowledgment ack) {
    log.info("Consuming order event. orderId={} topic={} eventType={}",
        event.getOrderId(), topic, event.getType());
    try {
        orderService.handleEvent(event);
        ack.acknowledge();
        log.info("Order event consumed. orderId={} eventType={}", event.getOrderId(), event.getType());
    } catch (NonRetryableException e) {
        log.error("Non-retryable error consuming event. orderId={} error={}",
            event.getOrderId(), e.getMessage(), e);
        ack.acknowledge();  // ack to skip — will not retry poison pill
    } catch (Exception e) {
        log.error("Retryable error consuming event. orderId={} error={} — will retry",
            event.getOrderId(), e.getMessage(), e);
        // do NOT ack — framework retries up to 3 times then routes to DLT
    }
}
```

---

#### 2c. Database (JPA / Repository) — Retry on Transient Failures

If the story introduces or modifies a `@Repository` or JPA call:

**Step 1 — Check for existing Spring Retry config:**
```bash
grep -rn "@EnableRetry\|@Retryable\|spring-retry" src/ pom.xml
```

**Step 2 — Add Spring Retry (transient DB failures only):**
```xml
<!-- pom.xml -->
<dependency>
    <groupId>org.springframework.retry</groupId>
    <artifactId>spring-retry</artifactId>
</dependency>
```

Enable in a config class:
```java
@Configuration
@EnableRetry
public class RetryConfig { }
```

**Step 3 — Annotate repository-calling service methods:**
```java
@Retryable(
    retryFor = {
        org.springframework.dao.TransientDataAccessException.class,
        org.springframework.dao.QueryTimeoutException.class,
        java.sql.SQLTransientConnectionException.class
    },
    maxAttempts = 3,
    backoff = @Backoff(delay = 500, multiplier = 2.0, maxDelay = 5000)
)
@Timed(value = "order.save.duration", percentiles = {0.5, 0.95, 0.99})
@Transactional
public Order saveOrder(Order order) {
    log.info("Saving order. customerId={} itemCount={}",
        order.getCustomerId(), order.getItems().size());
    Order saved = orderRepository.save(order);
    log.info("Order saved. orderId={} customerId={}", saved.getId(), saved.getCustomerId());
    return saved;
}

@Recover
public Order saveOrderRecover(TransientDataAccessException ex, Order order) {
    log.error("DB save failed after 3 retries. customerId={} error={}",
        order.getCustomerId(), ex.getMessage(), ex);
    throw new ServiceException("Order could not be persisted after retries", ex);
}
```

**Important:** `@Retryable` does NOT retry on `DataIntegrityViolationException` or
`NonTransientDataAccessException` — these are permanent failures and must not be retried.

---

#### 2d. Resilience4j Config Bean (required for @Retry/@CircuitBreaker AOP)
```java
@Configuration
public class ResilienceConfig {
    // Required for @Retry and @CircuitBreaker annotations to work via AOP
    // (auto-configured by spring-cloud-starter-circuitbreaker-resilience4j)
}
```

Dependency in pom.xml:
```xml
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-circuitbreaker-resilience4j</artifactId>
</dependency>
```

---

### 3. Write Spock Unit Specs FIRST (TDD)
For each task in the plan that involves business logic, create the Spock spec **before** implementing the class.

#### Spock Spec Template — Service Layer
```groovy
package com.example.[module].service

import spock.lang.Specification
import spock.lang.Subject
import spock.lang.Unroll

class [ClassName]Spec extends Specification {

    // Collaborators — use Spock mocks, not Mockito
    def mockDependency = Mock([DependencyClass])

    @Subject
    def subject = new [ClassName](mockDependency)

    // ── Happy path ──────────────────────────────────────────────
    def "should [describe expected behaviour] when [condition]"() {
        given: "a valid [input]"
        def input = new [InputClass](field: "value")

        when: "the service processes the request"
        def result = subject.[methodName](input)

        then: "the result matches expected output"
        result.field == "expected"
        1 * mockDependency.[collaboratorMethod](_) >> [stubbedReturn]
        0 * _   // no unexpected interactions
    }

    // ── Exception / failure paths ────────────────────────────────
    def "should throw [ExceptionType] when [failure condition]"() {
        given:
        mockDependency.[collaboratorMethod](_) >> { throw new RuntimeException("error") }

        when:
        subject.[methodName](new [InputClass]())

        then:
        thrown([ExceptionType])
    }

    // ── Data-driven / parameterised ──────────────────────────────
    @Unroll
    def "should return #expectedResult when input is #inputValue"() {
        when:
        def result = subject.[methodName](inputValue)

        then:
        result == expectedResult

        where:
        inputValue | expectedResult
        "valid"    | true
        "empty"    | false
        null       | false
    }
}
```

#### Spock Spec Template — Controller Layer (Spring MVC)
```groovy
package com.example.[module].controller

import com.example.[module].service.[ServiceClass]
import groovy.json.JsonSlurper
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest
import org.springframework.boot.test.mock.mockito.MockBean
import org.springframework.test.web.servlet.MockMvc
import spock.lang.Specification

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*

@WebMvcTest([ControllerClass])
class [ControllerClass]Spec extends Specification {

    @Autowired MockMvc mockMvc
    @MockBean [ServiceClass] service

    def "GET /[endpoint] returns 200 with expected body"() {
        given:
        service.[methodName](_) >> [stubbedResponse]

        when:
        def response = mockMvc.perform(get("/[endpoint]"))

        then:
        response.andExpect(status().isOk())
                .andExpect(jsonPath('$.field').value("expected"))
    }

    def "POST /[endpoint] returns 400 when request body is invalid"() {
        when:
        def response = mockMvc.perform(
            post("/[endpoint]")
            .contentType("application/json")
            .content('{}')
        )

        then:
        response.andExpect(status().isBadRequest())
        0 * service._
    }
}
```

#### Spock Spec Template — Resilience4j Retry (External API)
```groovy
package com.example.[module].service

import io.github.resilience4j.retry.RetryRegistry
import spock.lang.Specification
import spock.lang.Subject

class [ServiceName]RetrySpec extends Specification {

    def mockClient = Mock([FeignClientInterface])
    def mockMeterRegistry = Mock(io.micrometer.core.instrument.MeterRegistry)

    @Subject
    def service = new [ServiceName](mockClient, mockMeterRegistry)

    def "should retry up to 3 times when external API throws IOException"() {
        given: "the client fails twice then succeeds on third attempt"
        mockClient.[method](_) >>>
            [{ throw new IOException("timeout") },
             { throw new IOException("timeout") },
             new [ResponseClass](status: "OK")]

        when:
        def result = service.[serviceMethod](validInput())

        then: "called exactly 3 times — 2 failures + 1 success"
        3 * mockClient.[method](_)
        result.status == "OK"
    }

    def "should invoke fallback after 3 consecutive failures"() {
        given: "the client always fails"
        mockClient.[method](_) >> { throw new IOException("service down") }

        when:
        def result = service.[serviceMethod](validInput())

        then: "fallback default is returned, not an exception"
        3 * mockClient.[method](_)
        result == [ResponseClass].defaultValue()
        noExceptionThrown()
    }

    def "should NOT retry on ValidationException — it is non-retryable"() {
        given:
        mockClient.[method](_) >> { throw new ValidationException("bad input") }

        when:
        service.[serviceMethod](validInput())

        then: "called exactly once — no retry for non-retryable exception"
        1 * mockClient.[method](_)
        thrown(ValidationException)
    }

    def "should NOT retry on NotFoundException — it is non-retryable"() {
        given:
        mockClient.[method](_) >> { throw new NotFoundException("not found") }

        when:
        service.[serviceMethod](validInput())

        then:
        1 * mockClient.[method](_)
        thrown(NotFoundException)
    }
}
```

#### Spock Spec Template — Kafka Producer Retry + DLT
```groovy
class [ServiceName]KafkaSpec extends Specification {

    def mockKafkaTemplate = Mock(KafkaTemplate)
    def mockDeadLetterTemplate = Mock(KafkaTemplate)
    def mockMeterRegistry = new SimpleMeterRegistry()

    @Subject
    def service = new [ServiceName](mockKafkaTemplate, mockDeadLetterTemplate, mockMeterRegistry)

    def "should publish event successfully on first attempt"() {
        given:
        def event = new OrderEvent(orderId: "ORD-1", type: "PLACED")
        def mockFuture = Mock(ListenableFuture)
        def mockResult = Mock(SendResult)
        mockResult.recordMetadata >> Mock(RecordMetadata) { partition() >> 0; offset() >> 42L }
        mockFuture.get(_, _) >> mockResult
        mockKafkaTemplate.send(_, _, _) >> mockFuture

        when:
        service.publishOrderEvent(event)

        then:
        1 * mockKafkaTemplate.send(_, "ORD-1", event)
        0 * mockDeadLetterTemplate._
    }

    def "should route to DLT after all retries exhausted"() {
        given: "kafka send always fails"
        def event = new OrderEvent(orderId: "ORD-1", type: "PLACED")
        mockKafkaTemplate.send(_, _, _) >> { throw new KafkaException("broker down") }

        when:
        service.publishEventFallback(event, new KafkaException("broker down"))

        then: "event routed to dead letter topic"
        1 * mockDeadLetterTemplate.send({ it.contains(".DLT") }, "ORD-1", event)
    }

    def "should retry 3 times before invoking fallback on producer failure"() {
        given:
        def event = new OrderEvent(orderId: "ORD-1", type: "PLACED")
        mockKafkaTemplate.send(_, _, _) >> { throw new KafkaException("timeout") }

        when:
        service.publishOrderEvent(event)

        then: "attempted 3 times"
        3 * mockKafkaTemplate.send(_, _, _)
    }
}
```

#### Spock Spec Template — DB @Retryable (Transient Failure)
```groovy
class [ServiceName]DbRetrySpec extends Specification {

    def mockRepository = Mock([RepositoryInterface])

    @Subject
    def service = new [ServiceName](mockRepository)

    def "should retry DB save up to 3 times on transient connection error"() {
        given: "DB fails twice then succeeds"
        mockRepository.save(_) >>>
            [{ throw new TransientDataAccessException("pool timeout") {} },
             { throw new TransientDataAccessException("pool timeout") {} },
             new Order(id: "ORD-1")]

        when:
        def result = service.saveOrder(new Order(customerId: "CUST-1"))

        then:
        3 * mockRepository.save(_)
        result.id == "ORD-1"
    }

    def "should throw ServiceException after 3 failed DB retries"() {
        given: "DB always fails"
        mockRepository.save(_) >> { throw new TransientDataAccessException("pool timeout") {} }

        when:
        service.saveOrder(new Order(customerId: "CUST-1"))

        then: "recover method throws ServiceException"
        thrown(ServiceException)
    }

    def "should NOT retry on DataIntegrityViolationException — permanent failure"() {
        given:
        mockRepository.save(_) >> { throw new DataIntegrityViolationException("duplicate key") }

        when:
        service.saveOrder(new Order(customerId: "CUST-1"))

        then: "only 1 attempt — no retry for permanent DB errors"
        1 * mockRepository.save(_)
        thrown(DataIntegrityViolationException)
    }
}
```

### 4. Run Tests — Watch Them Fail (Red)
```bash
./mvnw test -pl [module] -Dtest=[ClassName]Spec -q
```
Confirm tests fail with `AssertionError` or `UnsatisfiedExpectation` — not compilation errors.

### 5. Implement the Feature (Green)
Implement the minimum code in the production class to make specs pass.

**Feature Flag Guard (MANDATORY if plan flagged Feature Flag = YES):**
Before writing any new business logic, verify the guard is in place:
```java
// FIRST LINE of every new feature method — check the flag
if (!featureFlagService.isEnabled(FeatureFlags.[CONSTANT])) {
    log.warn("Feature flag disabled — [describe fallback]. flag={}",
        FeatureFlags.[CONSTANT]);
    // return existing behaviour OR return 404 OR ack+discard (Kafka)
}
// NEW feature logic below this line only
```

If Cascade writes new implementation code that is NOT wrapped behind the flag, stop and
add the guard before proceeding. The rule: **new code is never reachable in production
without an explicit flag enable.**

Rules (enforced by `.windsurfrules`):
- Constructor injection only — no `@Autowired` on fields
- `@Slf4j` for logging — no `System.out.println`
- Return `Optional<T>` from repository calls, never return `null`
- Wrap FeignClient calls with `@CircuitBreaker` or `@Retry` from Resilience4j
- Use `@Validated` + Bean Validation annotations on request DTOs
- Every new feature path guarded by `FeatureFlagService.isEnabled(FeatureFlags.[CONSTANT])`

Re-run until green:
```bash
./mvnw test -pl [module] -Dtest=[ClassName]Spec -q
```

### 6. Run Full Test Suite
```bash
./mvnw test -pl [module] -q
```
All tests must pass — zero failures, zero errors.

### 7. Verify JaCoCo Coverage
```bash
./mvnw verify -pl [module] jacoco:report -q
```

Check the HTML report at `[module]/target/site/jacoco/index.html` or parse the XML:
```bash
grep -A2 'name="[package]"' [module]/target/site/jacoco/jacoco.xml
```

Coverage gate (mirrors `jacoco-maven-plugin` config):
```
Minimum line coverage:   80%
Minimum branch coverage: 75%
```

If below threshold:
- Identify uncovered lines from the HTML report
- Add targeted Spock specs for missing branches (null input, exception path, edge cases)
- Re-run verify until gate passes

If `BUILD FAILURE` due to JaCoCo threshold:
```bash
./mvnw verify -pl [module] -Djacoco.haltOnFailure=false jacoco:report -q
# Review report, add specs, then re-run with haltOnFailure=true
```

### 8. Commit
```bash
git add src/main src/test
git commit -m "feat([PROJ-123]): [short description]

- Implements [AC summary]
- Spock specs: [list spec files added]
- JaCoCo: line=[X]%, branch=[Y]%"
```

Next step → run `/deploy-story`
