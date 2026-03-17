# /nfr-report
**Trigger:** `/nfr-report`
**Description:** Generate a structured NFR Impact Report based on the findings from `/nfr-check`.
Documents all impacted APIs, risk classifications, estimated performance impact, and
recommended remediations. Output saved as a markdown file and appended to the PR description.

---

## Steps

### 1. Load NFR Check Results
Read the output files from `/nfr-check`:
- `/tmp/nfr-loops.txt`
- `/tmp/nfr-api-calls.txt`
- `/tmp/nfr-unbounded-queries.txt`
- `/tmp/nfr-transactional-api.txt`
- `/tmp/nfr-blocking.txt`
- `/tmp/nfr-impacted-apis.txt`

If these files are missing, ask the user to run `/nfr-check` first.

---

### 2. Build the Full NFR Impact Report

Generate the file `nfr-impact-report-[STORY-ID].md` in the repo root:

```markdown
# NFR Impact Report — [STORY-ID]: [Story Title]

**Date:** [today's date]
**Branch:** [current branch]
**Author:** [git config user.name]
**Reviewed by Cascade:** Yes

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Files changed | [N] |
| Methods changed | [N] |
| NFR patterns detected | [N] |
| Impacted API endpoints | [N] |
| CRITICAL blockers | [N] |
| HIGH risk items | [N] |
| MEDIUM risk items | [N] |
| Safe to merge | YES / NO |

**Overall NFR Risk Level:** 🔴 CRITICAL / 🟠 HIGH / 🟡 MEDIUM / 🟢 LOW

---

## 2. Impacted API Endpoints

For each controller endpoint that calls a changed service method:

| # | Method | Path | SLA Target | Estimated Latency Impact | Risk |
|---|--------|------|-----------|--------------------------|------|
| 1 | POST | /orders | < 200ms | +[X]ms per loop iteration × N items | 🔴 CRITICAL |
| 2 | GET | /products | < 100ms | Unbounded query — O(N) memory | 🟠 HIGH |
| 3 | POST | /notifications | < 500ms | Holds DB conn during API call | 🔴 CRITICAL |

**How latency impact is estimated:**
- Loop with API call: assume each FeignClient call = 50–200ms RTT. If collection = 100 items → +5,000–20,000ms
- Unbounded query: assume 10k rows = ~100–500ms + GC pressure
- API call inside @Transactional: DB connection held for full RTT of external call (50–500ms added to conn hold time)

---

## 3. Detailed NFR Findings

### Finding 1 — [NFR Pattern Name]
| Field | Value |
|-------|-------|
| **File** | `[FileName].java` |
| **Method** | `[methodName]()` |
| **Line** | [line number in diff] |
| **NFR Category** | Latency / Throughput / Resource / Reliability |
| **Pattern** | [describe the pattern e.g. "FeignClient call inside forEach loop"] |
| **Risk Level** | 🔴 CRITICAL |
| **Blocker** | YES |

**Current code (diff excerpt):**
```java
// [paste the relevant + lines from the diff]
```

**Impact:**
- Each call to `[ExternalService].fetch()` adds ~[X]ms network RTT
- With [N] items in loop → total added latency: ~[X * N]ms in worst case
- Under 100 concurrent requests → [100 × X × N]ms of thread-held time
- At Spring Boot default thread pool (200 threads): exhaustion risk at [threshold] RPS

**Remediation:**
```java
// Option A — Batch the external call
List<String> ids = items.stream().map(Item::getId).toList();
List<Result> results = externalClient.fetchBatch(ids);  // single API call

// Option B — Cache with @Cacheable if data is stable
@Cacheable(value = "items", key = "#id")
public Item getItem(String id) { ... }

// Option C — Async parallel with CompletableFuture (non-transactional context only)
List<CompletableFuture<Result>> futures = items.stream()
    .map(item -> CompletableFuture.supplyAsync(() -> client.fetch(item.getId()), executor))
    .toList();
List<Result> results = futures.stream().map(CompletableFuture::join).toList();
```

**Spock test to add (regression guard):**
```groovy
def "should call external API once for all items, not once per item"() {
    given:
    def items = (1..10).collect { new Item(id: "item-$it") }

    when:
    service.processItems(items)

    then:
    // Assert batch call, not 10 individual calls
    1 * mockClient.fetchBatch(_)
    0 * mockClient.fetch(_)
}
```

---

### Finding 2 — [Next Finding]
[repeat block above for each finding from /nfr-check]

---

## 4. Call Chain Diagram

For each impacted API, show the full call chain with NFR risk annotations:

```
POST /orders
  └─ OrderController.createOrder()
       └─ OrderService.processOrder()           ← CHANGED
            ├─ for each orderLine (N items)
            │    └─ PricingClient.getPrice()    ← 🔴 API CALL IN LOOP
            │    └─ InventoryRepo.findById()    ← 🔴 N+1 QUERY
            └─ OrderRepo.save()                 ← OK
```

```
GET /products
  └─ ProductController.listProducts()
       └─ ProductService.findAll()              ← CHANGED
            └─ ProductRepo.findAll()            ← 🟠 UNBOUNDED LIST
```

---

## 5. Resource Impact Estimates

### Thread Pool (Tomcat default: 200 threads)
| Scenario | Added hold time per req | Saturation RPS (200 threads) |
|----------|------------------------|------------------------------|
| Loop (N=50) × FeignClient (100ms) | 5,000ms | 200/5 = **40 RPS** 🔴 |
| Single FeignClient (100ms) | 100ms | 200/0.1 = 2,000 RPS ✅ |
| Unbounded query (10k rows) | 400ms | 200/0.4 = 500 RPS 🟡 |

### DB Connection Pool (HikariCP default: 10 connections)
| Scenario | Hold time per conn | Saturation RPS |
|----------|--------------------|----------------|
| @Transactional + API call (200ms) | 200ms | 10/0.2 = **50 RPS** 🔴 |
| Normal @Transactional (10ms) | 10ms | 10/0.01 = 1,000 RPS ✅ |

### Memory
| Scenario | Estimated heap per request | Risk |
|----------|---------------------------|------|
| findAll() returning 10k rows | ~50–100 MB | 🟠 HIGH — GC pressure |
| Paginated (page size 20) | ~1 MB | ✅ OK |

---

## 6. Recommended Actions

| Priority | Action | Owner | Blocker? |
|----------|--------|-------|----------|
| P0 🔴 | Replace loop+API with batch FeignClient call in `OrderService` | Dev | YES |
| P0 🔴 | Move FeignClient call outside `@Transactional` in `NotificationService` | Dev | YES |
| P1 🟠 | Paginate `ProductRepo.findAll()` — return `Page<Product>` | Dev | YES |
| P1 🟠 | Add `@Retry` + `@CircuitBreaker` to new `PricingClient` call | Dev | YES |
| P2 🟡 | Add `@Cacheable` to `PricingClient.getPrice()` for stable prices | Dev | NO |
| P2 🟡 | Add timeout config to FeignClient: `connectTimeout=2s, readTimeout=5s` | Dev | NO |

---

## 7. Spock Regression Guards Required

The following Spock specs must be added to prevent NFR regressions:

| Test | Spec File | Purpose |
|------|-----------|---------|
| Batch API call (not per-item) | `OrderServiceSpec.groovy` | Verifies `1 * mockClient.fetchBatch(_)` and `0 * mockClient.fetch(_)` |
| Paginated query | `ProductServiceSpec.groovy` | Verifies `Pageable` is passed to repo |
| Circuit breaker fallback | `NotificationServiceSpec.groovy` | Verifies fallback method fires on exception |

---

## 8. Sign-Off

| Check | Status |
|-------|--------|
| All CRITICAL items resolved | ☐ |
| All HIGH blockers resolved | ☐ |
| Regression Spock specs added | ☐ |
| JaCoCo threshold still met after fixes | ☐ |
| Re-run `/nfr-check` shows 0 blockers | ☐ |

**NFR Sign-Off:** ☐ Approved for merge
```

---

### 3. Save the Report File
```bash
REPORT_FILE="nfr-impact-report-$(git branch --show-current | sed 's/\//-/g').md"
# Cascade writes the report to this file in the repo root
echo "Report saved: $REPORT_FILE"
```

### 4. Append NFR Summary to PR (if PR already exists)
```bash
PR_NUMBER=$(gh pr list --head $(git branch --show-current) --json number --jq '.[0].number')
if [ -n "$PR_NUMBER" ]; then
  gh pr comment $PR_NUMBER --body "## NFR Impact Report
$(head -60 $REPORT_FILE)"
  echo "NFR summary appended to PR #$PR_NUMBER"
fi
```

### 5. Final Gate Check
If any CRITICAL or HIGH blocker items exist in the report:
```
🚫 NFR blockers prevent merge. Resolve all P0/P1 items, re-run /nfr-check, then /nfr-report.
```

If clean:
```
✅ NFR check passed — 0 blockers. Safe to proceed to /deploy-story.
```
