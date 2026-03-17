# /plan-story
**Trigger:** `/plan-story`
**Description:** Plan a user story — break it into tasks, identify affected Spring Boot components, scaffold branches and directories.

> **Pre-conditions (both must be met):**
> 1. `/story-intake` must show status `✅ READY TO DEVELOP`
> 2. `/architecture-review` must show status `✅ Architecture Confirmed` with a signed ADR
>
> If either has not been run, run them now. No story is planned without both gates.

---

## Steps

### 0. Verify Pre-Conditions
```bash
# Check story intake completed
ls story-intake-report-[STORY-ID].md 2>/dev/null || echo "MISSING — run /story-intake"

# Check architecture review completed
ls docs/adr/ADR-[STORY-ID]-*.md 2>/dev/null || echo "MISSING — run /architecture-review"
```

If either file is missing:
```
🔴 STOP — Required pre-conditions not met for [STORY-ID].
  Missing: [story-intake-report / ADR file]
  Run the missing workflow first, then return to /plan-story.
```

### 1. Load Story Details from Intake Report and ADR
Read both source documents:

**From `story-intake-report-[STORY-ID].md`:**
- Story ID, title, and confirmed description
- All confirmed ACs (only those marked ✅ or confirmed in-scope by PO)
- Technical dependency findings (what exists vs what must be created)
- Feature flag decision from the intake report

**From `docs/adr/ADR-[STORY-ID]-*.md`:**
- Confirmed communication pattern (REST / gRPC / GraphQL / Kafka / Hybrid)
- Reactive vs blocking decision (WebFlux / MVC)
- Resilience patterns required (CB / Bulkhead / Rate Limiter)
- DB access pattern (JPA / R2DBC)
- Implementation constraints checklist — these become mandatory tasks

Do not re-ask for any information already present in either document.

### 2. Decompose Story into Tasks
Break the story into clearly scoped tasks:
- Identify **API layer** changes (Controller, DTO, Request/Response models)
- Identify **Service layer** changes (business logic, orchestration)
- Identify **Repository/persistence** changes (JPA entity, queries)
- Identify **Integration points** (Kafka events, external HTTP clients via FeignClient)
- Identify **Spock test files** to create or update (unit + integration)
- Identify **Docker Compose** changes needed (new env vars, new services, health checks)
- Identify **Feature flag requirement** — does this story add new observable behaviour?
  Answer YES if any of the following are introduced:
  - A new API endpoint
  - A new Kafka producer or consumer
  - A change to an existing business rule or algorithm
  - An integration with a new external service
  Answer NO only for pure refactoring, test-only changes, or config changes.

Output a task checklist in this format:
```
## [PROJ-123] Story Title

### Acceptance Criteria
- [ ] AC1
- [ ] AC2

### Architecture (from ADR)
- Communication: [REST/gRPC/GraphQL/Kafka/Hybrid]
- Reactive:      [WebFlux Mono/Flux / Spring MVC]
- Resilience:    [Circuit Breaker / Bulkhead / Rate Limiter / Retry]
- DB access:     [JPA / R2DBC]
- Async:         [Kafka / synchronous]

### Tasks
- [ ] PROJ-123-1: Scaffold [WebFlux/MVC] controller with [REST/gRPC/GraphQL] endpoint
- [ ] PROJ-123-2: Implement service logic using [Mono/Flux / blocking]
- [ ] PROJ-123-3: Add/update repository method using [JPA / R2DBC]
- [ ] PROJ-123-4: Configure Resilience4j [CB / Bulkhead] for [dependency name]
- [ ] PROJ-123-5: Configure Kafka producer/consumer if async pattern selected
- [ ] PROJ-123-6: Write Spock specs — happy path, CB open, fallback, flag ON/OFF
- [ ] PROJ-123-7: Verify JaCoCo coverage threshold (min 80%)
- [ ] PROJ-123-8: Update docker-compose.yml if required
- [ ] PROJ-123-9: Feature flag — [YES: register flag + wrap impl / NO: not required]

### ADR Constraints (must not be violated during implementation)
- [ ] [Constraint 1 from ADR — e.g. no blocking operators on WebFlux thread]
- [ ] [Constraint 2 from ADR — e.g. all FeignClient calls behind @CircuitBreaker]
- [ ] [Constraint 3 from ADR — e.g. POST returns 202 Accepted, processing via Kafka]

### Feature Flag Decision
- Requires flag: YES / NO
- Proposed flag key: feature.[domain].[story-id]-[short-description]
- Flag OFF behaviour: [description]

### Affected Modules
- service: [module name]
- packages: [list key packages]

### Out of Scope
- [anything explicitly excluded]
```

### 3. Create Feature Branch
```bash
git checkout main && git pull
git checkout -b feature/PROJ-123-short-description
```

### 4. Scaffold Test Directory
Ensure the Spock test directories exist for this module:
```bash
mkdir -p src/test/groovy/[package]/service
mkdir -p src/test/groovy/[package]/controller
mkdir -p src/test/groovy/[package]/repository
```

### 5. Summary
Print the full task checklist and confirm with the user before proceeding.

If **Feature Flag Decision = YES** → Next step: run `/feature-flag` before `/review-story`
If **Feature Flag Decision = NO**  → Next step: run `/review-story`
