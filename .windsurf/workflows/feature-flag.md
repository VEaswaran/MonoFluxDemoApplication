# /feature-flag
**Trigger:** `/feature-flag`
**Description:** Detect whether the story introduces new functionality. If it does, scan Azure
App Configuration for an existing flag registry, register a new feature flag for this story,
wrap the implementation behind it, and verify a kill-switch test exists so the feature can be
turned off in production without a deployment.

---

## Philosophy
> Every new feature that changes observable behaviour must be born behind a flag.
> The flag is the kill-switch. If something goes wrong in production, the fix is one toggle
> in Azure App Configuration — not a hotfix, not a rollback, not a 2am deployment.

Feature flags are NOT optional for:
- New API endpoints
- New Kafka consumers or producers
- New DB schema reads/writes introduced by this story
- Any change to an existing algorithm or business rule
- Any integration with a new external service

Feature flags ARE optional for:
- Pure refactoring (no behaviour change)
- Test-only changes
- Infrastructure / config changes

---

## Steps

### 1. Detect Whether This Story Needs a Feature Flag

Run the diff:
```bash
git diff main...HEAD --name-only -- "*.java" "*.groovy" "*.yml" "*.yaml"
git diff main...HEAD -- "*.java" | grep "^\+" | grep -E \
  "(@GetMapping|@PostMapping|@PutMapping|@DeleteMapping|@PatchMapping|\
  @KafkaListener|kafkaTemplate\.send|\
  @Scheduled|\
  @Service|@Component|@EventListener|\
  FeignClient|RestTemplate|WebClient)" \
  | grep -v "^\+\+\+" > /tmp/ff-new-behaviour.txt
cat /tmp/ff-new-behaviour.txt
```

If `/tmp/ff-new-behaviour.txt` is empty → no feature flag needed. Output:
```
✅ No new observable behaviour detected. Feature flag not required.
```

If not empty → continue to Step 2.

---

### 2. Scan Existing Azure App Configuration Feature Flag Registry

Check the project for the existing feature flag configuration:

```bash
# Find the Azure App Configuration bootstrap file
find src/main/resources -name "*.yml" -o -name "*.yaml" | xargs grep -l \
  "azure.appconfiguration\|spring.cloud.azure.appconfiguration\|FeatureManagement\|feature-management" 2>/dev/null

# Find existing FeatureFlags enum or constants class
find src/main/java -name "FeatureFlags*.java" -o -name "FeatureFlag*.java" \
  -o -name "*FeatureConstants*.java" 2>/dev/null

# List all flags already registered
grep -rn "featureEnabled\|@FeatureGate\|isEnabled\|FeatureManager\|feature-management" \
  src/main/java --include="*.java" | grep -v "test\|Test\|Spec"
```

Print the **existing flag inventory**:
```
## Existing Feature Flags in Azure App Configuration
| Flag Key | Class/Method Using It | Status |
|----------|-----------------------|--------|
| feature.order.express-checkout | OrderService.processOrder() | ACTIVE |
| feature.payment.new-gateway | PaymentService.charge() | ACTIVE |
| feature.notification.sms | NotificationService.send() | INACTIVE |
```

If no flags exist yet: output a warning and proceed to scaffold the infrastructure first (Step 3a).
If flags exist: skip 3a, proceed directly to Step 3b.

---

### 3a. Scaffold Azure App Configuration Infrastructure (First-Time Only)

Only run this block if NO feature flag infrastructure exists in the project.

**pom.xml dependency:**
```xml
<dependency>
    <groupId>com.azure.spring</groupId>
    <artifactId>spring-cloud-azure-appconfiguration-config</artifactId>
</dependency>
<dependency>
    <groupId>com.microsoft.azure</groupId>
    <artifactId>spring-cloud-azure-feature-management</artifactId>
</dependency>
```

**bootstrap.yml (Azure App Config connection):**
```yaml
spring:
  cloud:
    azure:
      appconfiguration:
        stores:
          - connection-string: ${AZURE_APP_CONFIG_CONNECTION_STRING}
            feature-flags:
              enabled: true
        refresh:
          enabled: true
          interval: 30s       # poll interval — flags refresh without restart
```

**FeatureFlags.java — central constants class:**
```java
package com.example.[module].config;

/**
 * Central registry of all feature flag keys.
 * Every flag used in production MUST be declared here.
 * Naming convention: feature.[domain].[feature-name]
 */
public final class FeatureFlags {
    private FeatureFlags() {}

    // ── Existing flags ────────────────────────────────────────────
    // Add existing flags here as they are discovered

    // ── New flags added by story [STORY-ID] ───────────────────────
    // (added in Step 3b)
}
```

**FeatureFlagService.java — thin wrapper with logging:**
```java
package com.example.[module].config;

import com.microsoft.azure.spring.cloud.feature.manager.FeatureManager;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class FeatureFlagService {

    private final FeatureManager featureManager;

    public boolean isEnabled(String flagKey) {
        boolean enabled = featureManager.isEnabledAsync(flagKey).block();
        log.debug("Feature flag evaluated. flag={} enabled={}", flagKey, enabled);
        return enabled;
    }
}
```

---

### 3b. Register the New Feature Flag for This Story

**Step 1 — Define the flag key following the naming convention:**
```
feature.[domain].[story-id]-[short-description]

Examples:
  feature.order.proj-123-express-checkout
  feature.payment.proj-456-new-gateway
  feature.notification.proj-789-push-alerts
```

**Step 2 — Add the constant to `FeatureFlags.java`:**
```java
// In FeatureFlags.java — add under "New flags added by story [STORY-ID]"
public static final String [DOMAIN]_[FEATURE_NAME] =
    "feature.[domain].[story-id]-[short-description]";
```

Example:
```java
public static final String ORDER_EXPRESS_CHECKOUT =
    "feature.order.proj-123-express-checkout";
```

**Step 3 — Register the flag in Azure App Configuration (Terraform / Bicep or manual):**

If the project uses Terraform:
```hcl
# In infrastructure/feature-flags.tf
resource "azurerm_app_configuration_feature" "proj_123_express_checkout" {
  configuration_store_id = azurerm_app_configuration.main.id
  description            = "[PROJ-123] Express checkout — kill-switch for new order flow"
  name                   = "feature.order.proj-123-express-checkout"
  label                  = var.environment          # dev / staging / prod
  enabled                = false                    # OFF by default in all environments
}
```

If manual (Azure Portal / CLI):
```bash
az appconfig feature set \
  --name [app-config-store-name] \
  --feature "feature.order.proj-123-express-checkout" \
  --label [environment] \
  --yes
# Note: default state is disabled — enable explicitly when ready
```

**Step 4 — Add flag to `application.yml` local dev fallback (always OFF by default):**
```yaml
# application.yml — local dev / test fallback (Azure App Config overrides in deployed envs)
feature-management:
  feature.order.proj-123-express-checkout: false   # OFF by default everywhere
```

---

### 4. Wrap the New Feature Implementation Behind the Flag

For every new method, endpoint, or Kafka listener identified in Step 1, wrap it:

#### 4a. Service Layer — Guard Pattern
```java
@Slf4j
@Service
@RequiredArgsConstructor
public class OrderService {

    private final FeatureFlagService featureFlagService;
    private final OrderRepository orderRepository;

    @Timed(value = "order.express-checkout.duration", percentiles = {0.5, 0.95, 0.99})
    public OrderResponse processOrder(OrderRequest request) {
        log.info("Processing order. customerId={} expressCheckout={}",
            request.getCustomerId(),
            featureFlagService.isEnabled(FeatureFlags.ORDER_EXPRESS_CHECKOUT));

        if (featureFlagService.isEnabled(FeatureFlags.ORDER_EXPRESS_CHECKOUT)) {
            log.info("Feature flag active — using express checkout. customerId={}",
                request.getCustomerId());
            return processExpressCheckout(request);       // NEW code path
        }

        log.info("Feature flag inactive — using standard checkout. customerId={}",
            request.getCustomerId());
        return processStandardCheckout(request);           // EXISTING code path (unchanged)
    }

    // NEW — only reached when flag is ON
    private OrderResponse processExpressCheckout(OrderRequest request) { ... }

    // EXISTING — always reachable when flag is OFF, must never be modified
    private OrderResponse processStandardCheckout(OrderRequest request) { ... }
}
```

#### 4b. Controller Layer — Endpoint Guard (if the whole endpoint is new)
```java
@RestController
@RequestMapping("/orders")
@RequiredArgsConstructor
public class OrderController {

    private final FeatureFlagService featureFlagService;

    @PostMapping("/express")
    public ResponseEntity<OrderResponse> expressCheckout(@Valid @RequestBody OrderRequest request) {
        if (!featureFlagService.isEnabled(FeatureFlags.ORDER_EXPRESS_CHECKOUT)) {
            log.warn("Express checkout endpoint called but feature flag is disabled. Returning 404.");
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(orderService.processExpressCheckout(request));
    }
}
```

#### 4c. Kafka Listener Guard (if a new consumer is introduced)
```java
@KafkaListener(topics = "${kafka.topics.express-orders}")
public void consumeExpressOrder(@Payload OrderEvent event, Acknowledgment ack) {
    if (!featureFlagService.isEnabled(FeatureFlags.ORDER_EXPRESS_CHECKOUT)) {
        log.warn("Express order event received but feature flag is disabled. "
            + "Acknowledging and discarding. orderId={}", event.getOrderId());
        ack.acknowledge();   // do not process — kill-switch is ON
        meterRegistry.counter("order.express.flag-discarded").increment();
        return;
    }
    // ... normal processing ...
}
```

#### 4d. Kill-Switch Behaviour Contract
When the flag is **disabled**, the implementation must:
- Return the **existing behaviour** (existing code path, unchanged)
- OR return `404 Not Found` if the endpoint is entirely new and has no fallback
- OR silently ack and discard for Kafka (never dead-letter due to a disabled flag)
- Log at `WARN` level with `feature flag disabled` in the message — searchable in ELK
- Increment a Micrometer counter: `[domain].[feature].flag-disabled` — visible in Grafana

---

### 5. Write Spock Specs — Flag ON and Flag OFF Paths (Both Are Mandatory)

Every feature-flagged method MUST have specs for BOTH states. No exceptions.

```groovy
package com.example.[module].service

import spock.lang.Specification
import spock.lang.Subject
import spock.lang.Unroll

class OrderServiceFeatureFlagSpec extends Specification {

    def mockFeatureFlagService = Mock(FeatureFlagService)
    def mockOrderRepository    = Mock(OrderRepository)

    @Subject
    def service = new OrderService(mockFeatureFlagService, mockOrderRepository)

    // ── Flag ON — new code path ──────────────────────────────────
    def "should use express checkout when feature flag ORDER_EXPRESS_CHECKOUT is enabled"() {
        given: "feature flag is ON"
        mockFeatureFlagService.isEnabled(FeatureFlags.ORDER_EXPRESS_CHECKOUT) >> true

        and: "a valid order request"
        def request = new OrderRequest(customerId: "CUST-1", items: [validItem()])

        when:
        def result = service.processOrder(request)

        then: "express checkout path was taken"
        result.checkoutType == "EXPRESS"
        1 * mockOrderRepository.saveWithExpressOptions(_)
        0 * mockOrderRepository.save(_)              // standard path NOT taken
    }

    // ── Flag OFF — existing code path unchanged ──────────────────
    def "should use standard checkout when feature flag ORDER_EXPRESS_CHECKOUT is disabled"() {
        given: "feature flag is OFF"
        mockFeatureFlagService.isEnabled(FeatureFlags.ORDER_EXPRESS_CHECKOUT) >> false

        and: "same valid order request"
        def request = new OrderRequest(customerId: "CUST-1", items: [validItem()])

        when:
        def result = service.processOrder(request)

        then: "standard (existing) checkout path was taken"
        result.checkoutType == "STANDARD"
        1 * mockOrderRepository.save(_)              // existing path
        0 * mockOrderRepository.saveWithExpressOptions(_)
    }

    // ── Kill-switch — flag toggled OFF mid-flight ────────────────
    def "should gracefully fall back to standard checkout when flag is toggled OFF"() {
        given: "flag starts ON then is toggled OFF"
        mockFeatureFlagService.isEnabled(FeatureFlags.ORDER_EXPRESS_CHECKOUT) >>> [true, false]

        when: "two consecutive requests"
        def result1 = service.processOrder(new OrderRequest(customerId: "CUST-1", items: [validItem()]))
        def result2 = service.processOrder(new OrderRequest(customerId: "CUST-2", items: [validItem()]))

        then: "first uses express, second uses standard — no exception"
        result1.checkoutType == "EXPRESS"
        result2.checkoutType == "STANDARD"
        noExceptionThrown()
    }

    // ── Controller 404 when endpoint is new and flag is OFF ──────
    def "should return 404 when express endpoint is called with flag disabled"() {
        given:
        mockFeatureFlagService.isEnabled(FeatureFlags.ORDER_EXPRESS_CHECKOUT) >> false

        when:
        def response = mockMvc.perform(post("/orders/express")
            .contentType("application/json")
            .content(validRequestJson()))

        then:
        response.andExpect(status().isNotFound())
        0 * mockOrderService._
    }

    // ── Kafka discard when flag is OFF ───────────────────────────
    def "should acknowledge and discard Kafka event when feature flag is disabled"() {
        given:
        mockFeatureFlagService.isEnabled(FeatureFlags.ORDER_EXPRESS_CHECKOUT) >> false
        def event = new OrderEvent(orderId: "ORD-1", type: "EXPRESS")
        def mockAck = Mock(Acknowledgment)

        when:
        consumer.consumeExpressOrder(event, mockAck)

        then: "message is acked (not retried) and discarded silently"
        1 * mockAck.acknowledge()
        0 * mockOrderService._
    }

    private OrderItem validItem() {
        new OrderItem(productId: "PROD-1", price: 10.0, quantity: 1)
    }
}
```

---

### 6. NFR Check for Feature Flag Overhead

Feature flag evaluation calls Azure App Configuration. Verify it is not introducing latency:

```bash
# Check if FeatureManager calls are cached / async
grep -rn "isEnabledAsync\|isEnabled\|RefreshInterval" src/main/java --include="*.java"
grep -A5 "refresh:" src/main/resources/bootstrap.yml
```

Rules:
- Flag evaluation MUST use the cached local value — NOT a live Azure call per request
- Azure App Configuration refresh interval must be `≥ 30s` (not real-time per call)
- Never call `featureManager.isEnabled()` inside a loop
- `FeatureFlagService.isEnabled()` is a synchronous wrapper over the local cache — this is safe

If a live-call pattern is found (no caching), flag as:
```
🔴 CRITICAL NFR: Feature flag evaluated via live Azure call per request.
   Add spring.cloud.azure.appconfiguration.refresh.interval=30s
   and use the local cache via FeatureManager.isEnabledAsync().block()
```

---

### 7. Generate Feature Flag Report

Write `feature-flag-report-[STORY-ID].md` to repo root:

```markdown
# Feature Flag Report — [STORY-ID]: [Story Title]

**Date:** [today]
**Branch:** [branch]

---

## New Feature Flag Registered

| Property | Value |
|----------|-------|
| Flag Key | `feature.[domain].[story-id]-[short-description]` |
| Java Constant | `FeatureFlags.[DOMAIN]_[FEATURE_NAME]` |
| Default State | DISABLED (all environments) |
| Azure Resource | app-config-store / label=[env] |
| Terraform Resource | `azurerm_app_configuration_feature.[resource_name]` |
| Kill-Switch Behaviour | [describe what happens when flag is OFF] |

---

## Existing Flags Inventory (unchanged)

| Flag Key | Owner Service | Status |
|----------|--------------|--------|
| [existing flags listed here] | | |

---

## Code Paths Guarded by This Flag

| Layer | Class | Method | Flag ON Behaviour | Flag OFF Behaviour |
|-------|-------|--------|-------------------|-------------------|
| Service | OrderService | processOrder() | Express checkout | Standard checkout (existing) |
| Controller | OrderController | POST /orders/express | 200 OK | 404 Not Found |
| Kafka | OrderEventConsumer | consumeExpressOrder() | Process event | Ack + discard |

---

## Kill-Switch Runbook

**When to use the kill-switch:**
- Elevated error rate on `/orders/express` endpoint (Grafana alert fires)
- Express checkout producing incorrect order totals
- External dependency for express flow is degraded

**How to disable (< 60 seconds, no deployment):**
```bash
# Azure CLI
az appconfig feature disable \
  --name [app-config-store-name] \
  --feature "feature.order.proj-123-express-checkout" \
  --label production

# OR via Azure Portal:
# App Configuration → Feature Manager → feature.order.proj-123-express-checkout → Disable
```

**What happens immediately after disabling:**
- Within 30 seconds (refresh interval), all running pods pick up the new state
- All new requests to `/orders/express` → 404
- All new `processOrder()` calls → standard checkout path (existing, stable)
- Grafana metric `order.express.flag-disabled` begins incrementing — confirms kill-switch active
- ELK query to verify: `message:"feature flag disabled" AND flag:"feature.order.proj-123-express-checkout"`

**How to re-enable:**
```bash
az appconfig feature enable \
  --name [app-config-store-name] \
  --feature "feature.order.proj-123-express-checkout" \
  --label production
```

---

## Spock Coverage

| Spec File | Test Blocks | Coverage |
|-----------|-------------|----------|
| OrderServiceFeatureFlagSpec.groovy | Flag ON path, Flag OFF path, Kill-switch toggle, Kafka discard | ✅ Both paths covered |

---

## ✅ Sign-Off Checklist
- [ ] Flag key follows naming convention: `feature.[domain].[story-id]-[description]`
- [ ] Flag constant added to `FeatureFlags.java`
- [ ] Flag registered in Azure App Configuration (Terraform or CLI)
- [ ] Flag default state is DISABLED in all environments
- [ ] New implementation wrapped behind flag guard
- [ ] Existing code path is reachable when flag is OFF (unchanged)
- [ ] Spock spec: flag ON path covered
- [ ] Spock spec: flag OFF path covered
- [ ] Spock spec: kill-switch toggle (ON → OFF mid-flight) covered
- [ ] Kill-switch runbook written in this report
- [ ] Flag evaluation uses local cache (not live Azure call per request)
- [ ] Grafana counter `[domain].[feature].flag-disabled` increments when flag is OFF
```

---

### 8. Commit
```bash
git add src/main src/test infrastructure/ feature-flag-report-*.md
git commit -m "feat([STORY-ID]): implement [feature] behind feature flag

- Feature flag: feature.[domain].[story-id]-[short-description]
- Default: DISABLED in all environments
- Flag ON: [new behaviour]
- Flag OFF: [existing/fallback behaviour]
- Spock: flag ON + OFF + kill-switch toggle specs added
- Kill-switch runbook: feature-flag-report-[STORY-ID].md"
```

Next step → run `/code-quality`
