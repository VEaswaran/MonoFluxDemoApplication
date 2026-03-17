# /nfr-check
**Trigger:** `/nfr-check`
**Description:** Scan the current feature branch diff for Non-Functional Requirement (NFR) violations
and performance-risk patterns. Produces a risk-annotated change list and calls `/nfr-report`
to generate the full impact document.

---

## Context
NFRs this workflow enforces:
- **Latency** — no new synchronous blocking calls inside loops; all external calls must be async or cached
- **Throughput** — loops over collections must have bounded size or pagination
- **Resource usage** — DB connections, thread pool starvation, memory allocation in hot paths
- **Cascading failure** — API calls without circuit breaker / retry
- **Call depth** — service → resource (repository/client) chain must not exceed 3 hops without caching

---

## Steps

### 1. Get the Full Diff Against Main
```bash
git diff main...HEAD --unified=5 -- "*.java" "*.groovy" > /tmp/story-diff.txt
wc -l /tmp/story-diff.txt
```

Also capture the list of changed files:
```bash
git diff main...HEAD --name-only -- "*.java" "*.groovy"
```

---

### 2. Scan Diff for NFR Trigger Patterns

For each changed file, analyse the diff (lines starting with `+`) for the following patterns.
For every match, record: **file**, **method name**, **line number**, **pattern type**, **risk level**.

#### 2a. For-Loop / Iterator Introduced Over Unbounded Collection
**Pattern:** A `for`, `forEach`, `.stream()`, `.map()`, `.flatMap()`, or `while` loop added in a
method that also contains or calls a database query, FeignClient call, or Kafka producer.

```bash
grep -n "^\+" /tmp/story-diff.txt | grep -E \
  "(for\s*\(|\.forEach|\.stream\(\)|\.map\(|\.flatMap\(|while\s*\()" \
  > /tmp/nfr-loops.txt
cat /tmp/nfr-loops.txt
```

Risk: **HIGH** if the loop body calls a repository method or FeignClient.
Risk: **MEDIUM** if loop is over an in-memory list with no external call.

Suggested fix:
- Replace row-by-row DB calls with a single `findAllById(ids)` or batch query
- Replace looped FeignClient calls with a bulk/batch API endpoint
- Add `@Cacheable` on the called method if data is stable

---

#### 2b. New Outbound API Call (FeignClient / RestTemplate / WebClient)
**Pattern:** A new method call to a FeignClient interface, `RestTemplate`, or `WebClient` added
in a service layer method.

```bash
grep -n "^\+" /tmp/story-diff.txt | grep -E \
  "(FeignClient|RestTemplate|WebClient|\.exchange\(|\.get\(\)|\.post\(\))" \
  > /tmp/nfr-api-calls.txt
cat /tmp/nfr-api-calls.txt
```

Risk: **CRITICAL** if no `@CircuitBreaker` or `@Retry` annotation is present on the calling method
or the FeignClient interface.
Risk: **HIGH** if the call is synchronous and inside a transaction (`@Transactional`).
Risk: **MEDIUM** if the call has a circuit breaker but no timeout configured.

Suggested fix:
- Add `@CircuitBreaker(name = "[service]", fallbackMethod = "...")` from Resilience4j
- Add `connectTimeout` and `readTimeout` to the FeignClient config
- Move the API call outside of `@Transactional` scope

---

#### 2c. Service → Resource Call Depth (N+1 Risk)
**Pattern:** A service method calls a repository method, which is itself called inside a loop,
or a service calls another service that calls a repository.

For each service method changed, trace the call chain:
```
Service.methodA()
  → calls RepositoryB.findByX()       ← depth 1 — OK
  → calls ServiceC.doSomething()
      → calls RepositoryD.findAll()   ← depth 2 — flag if inside loop
      → calls ExternalClient.fetch()  ← depth 2 + external — CRITICAL
```

Use Cascade's codebase understanding to trace:
1. Open each changed service method
2. List all method calls made directly
3. For each call to another `@Service` or `@Repository`, expand one level
4. Flag any chain where: loop → service call → repo call OR loop → service call → API call

Risk level:
- Loop → repo: **HIGH** (N+1 query)
- Loop → service → repo: **HIGH**
- Loop → service → API call: **CRITICAL**
- Transactional service → async service → repo: **MEDIUM** (transaction boundary risk)

---

#### 2d. Missing Pagination on Repository / API Query
**Pattern:** A new repository method returns `List<T>` (not `Page<T>` or `Slice<T>`) and is
called from a service method that does not enforce a size limit.

```bash
grep -n "^\+" /tmp/story-diff.txt | grep -E \
  "List<.*> find|findAll\(\)" \
  > /tmp/nfr-unbounded-queries.txt
cat /tmp/nfr-unbounded-queries.txt
```

Risk: **HIGH** — could return millions of rows under production load.

Suggested fix:
- Change return type to `Page<T>` with `Pageable` parameter
- Or add a `LIMIT` clause via `@Query`

---

#### 2e. Synchronous Call Inside @Transactional
**Pattern:** A method annotated `@Transactional` now contains a FeignClient call, `RestTemplate`
call, or a `Thread.sleep`.

```bash
grep -n "^\+" /tmp/story-diff.txt | grep -E \
  "(RestTemplate|FeignClient|\.exchange\(|Thread\.sleep)" \
  > /tmp/nfr-transactional-api.txt
cat /tmp/nfr-transactional-api.txt
```

Cross-reference: check if the calling method in the diff has `@Transactional`.

Risk: **CRITICAL** — holds DB connection open during an external network call; connection pool
exhaustion under load.

---

#### 2f. Thread-Blocking Patterns
**Pattern:** `Thread.sleep`, `CountDownLatch.await`, `CompletableFuture.get()` (blocking get)
added in a method called from the request thread.

```bash
grep -n "^\+" /tmp/story-diff.txt | grep -E \
  "(Thread\.sleep|\.await\(|CompletableFuture.*\.get\(\)|\.join\(\))" \
  > /tmp/nfr-blocking.txt
cat /tmp/nfr-blocking.txt
```

Risk: **CRITICAL** if on request thread (Controller → Service → here).
Risk: **MEDIUM** if in a background `@Scheduled` method.

---

### 2g. Missing Retry Mechanism on New Integration Points
**Pattern:** A new FeignClient call, KafkaTemplate.send(), or Repository.save() was added
in this story but has no retry annotation.

```bash
# Find new integration calls without retry
grep -n "^\+" /tmp/story-diff.txt | grep -E \
  "(FeignClient|kafkaTemplate\.send|repository\.save|RestTemplate\.exchange)" \
  > /tmp/nfr-new-integrations.txt

# Check for retry annotations in the same file
grep -n "@Retry\|@Retryable\|@CircuitBreaker" [ChangedFile].java
```

Risk: **CRITICAL** if a new integration call has no retry at all.
Risk: **HIGH** if retry exists but max-attempts is not explicitly set to 3.
Risk: **MEDIUM** if retry exists but no fallback/recover method is defined.

```
🔴 CRITICAL: [ClassName].[method]() — new [API/Kafka/DB] call with no @Retry annotation
🟠 HIGH:     [ClassName].[method]() — @Retry present but maxAttempts not set to 3
🟡 MEDIUM:   [ClassName].[method]() — @Retry present but no fallback method defined
```

---



For each changed service method, trace upward to find which Controller endpoint(s) invoke it:

```bash
# Find controller methods that call the changed service methods
grep -rn "[ServiceClassName]\." src/main/java --include="*.java" \
  | grep -E "(Controller|Resource)" \
  > /tmp/nfr-impacted-apis.txt
cat /tmp/nfr-impacted-apis.txt
```

Build the impact list:
```
## Impacted API Endpoints
| HTTP Method | Path | Controller Method | Calls Changed Service Method | Risk |
|-------------|------|-------------------|------------------------------|------|
| POST | /orders | OrderController.createOrder | OrderService.processOrder | CRITICAL |
| GET  | /orders/{id} | OrderController.getOrder | OrderService.loadOrder | LOW |
```

---

### 4. Produce NFR Risk Summary (Console)

Output this table before calling `/nfr-report`:

```
## NFR Pre-Check Summary — [PROJ-123]

| # | File | Method | NFR Pattern | Risk | Blocker? |
|---|------|--------|-------------|------|----------|
| 1 | OrderService.java | processOrder() | Loop → FeignClient call | CRITICAL | YES |
| 2 | ProductService.java | findAll() | Unbounded List<> query | HIGH | YES |
| 3 | NotificationService.java | notify() | API call inside @Transactional | CRITICAL | YES |
| 4 | ReportService.java | buildReport() | N+1: loop → repo call | HIGH | YES |

Blockers found: 4
✅ Safe to proceed: NO — resolve CRITICAL and HIGH items before merging

Impacted API endpoints: [N]
```

If blockers exist, do NOT proceed to `/deploy-story`. Fix each issue and re-run `/nfr-check`.

---

### 5. Generate NFR Report
Call the next workflow:
```
/nfr-report
```
