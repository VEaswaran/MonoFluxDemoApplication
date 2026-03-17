# /story-intake
**Trigger:** `/story-intake`
**Description:** Analyse a raw user story before any planning or development begins.
Validate story format, detect missing business logic, flag ambiguous acceptance criteria,
identify hidden assumptions, surface technical gaps, and produce a Developer Review Checklist
that must be signed off before `/plan-story` is allowed to run.

This workflow never writes code. Its only output is a structured analysis and a
blockers list. If blockers exist, development does not start.

---

## Philosophy
> A story that is unclear to the reader was unclear to the writer.
> Every ambiguity caught here saves hours of rework caught in review.
> The goal is not to slow down delivery — it is to ensure the first commit
> is in the right direction.

---

## Step 1 — Collect the Raw Story

Ask the developer to paste the full story exactly as written in Jira / Azure DevOps.
Do not paraphrase or interpret it yet. Capture it verbatim.

Required input fields (request each if not provided):

| Field | Example | Why It Matters |
|-------|---------|----------------|
| **Story ID** | `PROJ-123` | Traceability across all artefacts |
| **Story Title** | As a user, I want to... | Sets the actor and the goal |
| **Story Description** | Full body text from Jira | Contains context, background, edge cases |
| **Acceptance Criteria** | Given/When/Then or bullet list | Defines done — every AC becomes a Spock spec |
| **Priority / Sprint** | P1 / Sprint 14 | Informs risk level of missing detail |
| **Linked Stories / Epics** | PROJ-100, PROJ-101 | Dependency and scope context |
| **Reporter / Product Owner** | [name] | Who to raise review questions to |

If any field is missing, prompt specifically:
```
⚠️ Missing: [field name]
Please provide: [explanation of why this field is needed before analysis can begin]
```
Do not proceed to Step 2 until all fields are present.

---

## Step 2 — Story Format Validation

Validate the story title follows the standard user story format.

### 2a. Title Format Check
Expected: `As a [actor], I want [goal], so that [benefit]`

| Component | Present? | Issue if Missing |
|-----------|----------|-----------------|
| Actor (`As a...`) | ✅ / ❌ | Cannot determine who is affected — scope unclear |
| Goal (`I want...`) | ✅ / ❌ | Cannot determine what to build |
| Benefit (`so that...`) | ✅ / ❌ | Cannot validate whether implementation achieves the purpose |

If `so that` is missing:
```
🟠 WARNING — Story title missing benefit clause ("so that...").
Without knowing WHY this is needed, edge cases cannot be reasoned about.
Ask PO: "What business outcome does this enable?"
```

### 2b. INVEST Criteria Check
Rate each dimension: ✅ Pass | 🟠 Partial | 🔴 Fail

| INVEST | Question Asked | Verdict |
|--------|---------------|---------|
| **Independent** | Can this be built without dependency on an unmerged story? | |
| **Negotiable** | Is the implementation approach left open, or over-specified? | |
| **Valuable** | Is the business value stated or clearly implied? | |
| **Estimable** | Is enough detail present for a developer to size it? | |
| **Small** | Can this realistically be completed in one sprint? | |
| **Testable** | Can each AC be turned into a pass/fail Spock spec? | |

If **Estimable = FAIL**:
```
🔴 BLOCKER — Story cannot be estimated. Missing: [specific detail].
Ask PO: "[targeted question]"
```

If **Small = FAIL**:
```
🟠 WARNING — Story appears too large for one sprint.
Suggested split: [propose 2-3 sub-stories based on the content]
```

---

## Step 3 — Acceptance Criteria Deep Analysis

This is the most critical step. Every AC is interrogated individually.

For each AC, run all of the following checks:

### 3a. Completeness Check
Each AC must answer: **Given** [context] **When** [action] **Then** [outcome].

If an AC is written as a statement rather than a scenario:
```
Original AC: "User should be able to reset their password"

🔴 INCOMPLETE AC — no Given/When/Then structure.
Rewritten for clarity:
  Given: a registered user who has forgotten their password
  When: they submit their email on the forgot-password page
  Then: they receive a reset link within 2 minutes
  And: the link expires after 30 minutes
  And: clicking an expired link shows an error message

Questions for PO / developer:
  1. What is the token expiry duration? (30 min assumed — confirm)
  2. Should the link be single-use?
  3. What happens if the email is not registered?
  4. Is there a rate limit on reset requests per email?
```

### 3b. Missing Edge Cases — Auto-Detection
For each AC, systematically generate edge cases that are NOT explicitly covered:

Run this checklist against every AC:

**Input edge cases:**
- [ ] What happens with a null or empty input?
- [ ] What happens with an input at the maximum allowed length?
- [ ] What happens with special characters, Unicode, or SQL injection patterns?
- [ ] What happens if a required field is missing?

**State edge cases:**
- [ ] What if the entity does not exist? (404 path)
- [ ] What if the entity is in an unexpected state? (e.g. already cancelled, already fulfilled)
- [ ] What if a concurrent request modifies the entity between read and write?
- [ ] What if a dependency (external API, Kafka, DB) is unavailable?

**Business rule edge cases:**
- [ ] What is the behaviour at boundary values? (e.g. quantities of 0, 1, max)
- [ ] Are there time-sensitive rules? (expiry, deadlines, cut-off times, time zones)
- [ ] Are there user permission / role rules that constrain behaviour?
- [ ] Are there multi-tenancy or data isolation rules?

**Integration edge cases:**
- [ ] What if the downstream API returns an unexpected status code?
- [ ] What if the Kafka topic does not exist or the broker is unreachable?
- [ ] What is the idempotency guarantee? (can this be called twice with the same result?)

For every edge case NOT covered by an existing AC, output:
```
⚠️ MISSING EDGE CASE — [AC number or title]
Scenario not defined: "[describe the gap]"
Proposed AC addition:
  Given: [context]
  When: [action]
  Then: [expected outcome]
Action required: Confirm with PO / developer before development begins.
```

### 3c. Contradiction Detection
Compare all ACs against each other and against the story description.
Flag any pair that contradict:

```
🔴 CONTRADICTION — AC3 vs AC7
  AC3 states: "user is redirected to dashboard on success"
  AC7 states: "user receives a confirmation email and stays on the page"
  These cannot both be true. Clarify which is correct before proceeding.
```

### 3d. Testability Check
For each AC, verify it can be expressed as a deterministic Spock `given/when/then` block.
Flag any AC that is subjective or unmeasurable:

```
🔴 UNTESTABLE AC — "The response should be fast"
  "Fast" is not measurable. Replace with a specific SLA:
  "The API response time must be < 200ms at p95 under 100 concurrent users"
  OR
  "The page must load within 3 seconds on a 4G connection"
```

```
🔴 UNTESTABLE AC — "The UI should look good"
  This is outside the scope of a backend story. Remove or move to a UI story.
```

---

## Step 4 — Business Logic Gap Analysis

Beyond the ACs, analyse the story description for hidden assumptions and undefined behaviour.

### 4a. Data Flow Questions
Trace the implied data flow end-to-end and flag every gap:

```
Implied flow: User submits form → API receives request → service processes → DB persists → response

Gap analysis:
❓ What is the API request schema? (fields, types, validation rules)
❓ What is the API response schema on success?
❓ What is the API response schema on validation failure?
❓ Which DB table(s) are written to? Are there FK constraints?
❓ Are there any events emitted to Kafka after persistence?
❓ Is there a downstream service that consumes this data?
```

### 4b. Authorization and Security Questions
```
❓ Which roles can perform this action? (ADMIN only / any authenticated user / public)
❓ Is there a data ownership check? (can user A access user B's data?)
❓ Are there any PII fields that must be masked in logs?
❓ Does this endpoint require CSRF protection or idempotency keys?
```

### 4c. Idempotency Question
For any write operation (POST, PUT, Kafka produce, DB insert):
```
❓ IDEMPOTENCY — What happens if this request is submitted twice?
  Options:
  A) Returns the existing result (idempotent) — requires idempotency key
  B) Creates a duplicate — is that acceptable?
  C) Returns 409 Conflict — requires unique constraint
  Confirm which behaviour is expected.
```

### 4d. Pagination / Volume Question
For any read operation returning a list:
```
❓ VOLUME — How many records can this query return?
  If unbounded: "All orders" could mean 10 or 10,000,000.
  Does this need pagination? What is the default page size?
  What is the sort order?
```

### 4e. Audit / Compliance Questions
```
❓ Does this change require an audit trail? (who changed what, when)
❓ Are there regulatory constraints? (GDPR data retention, financial record keeping)
❓ Does this story affect any field that is subject to data masking or encryption at rest?
```

---

## Step 5 — Technical Dependency Check

Cross-reference the story against the existing codebase.

```bash
# Check if the implied entities already exist
find src/main/java -name "*.java" | xargs grep -l "[EntityName]" 2>/dev/null

# Check if the implied endpoints already exist
grep -rn "@GetMapping\|@PostMapping\|@PutMapping\|@DeleteMapping" \
  src/main/java --include="*.java" | grep "[implied-path]"

# Check if the implied Kafka topics are already configured
grep -rn "kafka.topics\|@KafkaListener" src/main/resources src/main/java \
  --include="*.yml" --include="*.java" | grep "[implied-topic]"

# Check for existing feature flags in the same domain
grep -rn "FeatureFlags\." src/main/java --include="*.java" | grep "[domain]"
```

Output:

```
## Technical Dependency Scan

| Assumed Component | Exists? | Risk |
|-------------------|---------|------|
| OrderEntity.java | ✅ found at com.example.order.domain | None |
| POST /orders/express endpoint | ❌ not found | Must be created — not just modified |
| Kafka topic: order-express-events | ❌ not in application.yml | Must be provisioned |
| FeatureFlags.ORDER_EXPRESS_CHECKOUT | ❌ not found | Feature flag must be created |
| OrderExpressRepository | ❌ not found | New interface needed |
```

Any `❌` where the story ASSUMED `✅` is a gap that must be clarified.

---

## Step 6 — Non-Functional Requirement Check

Check whether the story mentions performance, reliability, or observability expectations.
If any of the following are missing, flag them as questions (not blockers, unless SLA-sensitive):

```
## NFR Checklist — Defined in Story?

| NFR | Defined? | Default Assumption | Action |
|-----|----------|--------------------|--------|
| Response time SLA | ❌ | < 200ms p95 assumed | Confirm with PO |
| Throughput expectation | ❌ | Not stated | Confirm if > 100 RPS expected |
| Data retention | ❌ | Follows existing policy | Confirm if GDPR-sensitive |
| Availability SLA | ❌ | Follows service SLA | No action if standard |
| Observability | ❌ | @Timed + ELK logging added by default | No action needed |
| Feature flag required | [YES/NO from AC analysis] | See /feature-flag workflow | Action if YES |
```

---

## Step 7 — Generate Developer Review Checklist

Compile everything into a single structured output.
This document is handed to the developer AND the Product Owner.
**Nothing in `/plan-story` or beyond runs until all 🔴 items are resolved.**

```markdown
# Story Intake Report — [STORY-ID]: [Title]

**Date:** [today]
**Analysed by:** Cascade /story-intake
**Status:** 🔴 BLOCKED / 🟠 NEEDS REVIEW / ✅ READY

---

## Story Quality Score

| Dimension | Score | Notes |
|-----------|-------|-------|
| Format (As a / I want / so that) | [✅/🟠/🔴] | [detail] |
| INVEST — Independent | [✅/🟠/🔴] | [detail] |
| INVEST — Estimable | [✅/🟠/🔴] | [detail] |
| INVEST — Small | [✅/🟠/🔴] | [detail] |
| INVEST — Testable | [✅/🟠/🔴] | [detail] |
| AC completeness | [X/Y ACs fully defined] | |
| Edge cases covered | [X missing] | |
| Business logic gaps | [N gaps] | |
| Technical dependencies clear | [✅/🟠/🔴] | |

**Overall: READY TO DEVELOP / NEEDS REVIEW / BLOCKED**

---

## 🔴 Blockers — Must Be Resolved Before /plan-story

> These are gaps that will cause incorrect implementation or wasted rework.
> The developer must not write a single line of code until these are answered.

| # | Type | Description | Owner | Resolution |
|---|------|-------------|-------|------------|
| 1 | Missing AC | What happens when reset link is expired? | PO | Add AC: Given expired link, When clicked, Then show error message |
| 2 | Contradiction | AC3 says redirect to dashboard, AC7 says stay on page | PO | Decide which is correct |
| 3 | Undefined behaviour | Idempotency not defined for POST /orders/express | PO + Dev | Decide: 409 Conflict OR return existing order |
| 4 | Missing constraint | No role restriction stated — can any user call this? | PO | Confirm: ADMIN only or all authenticated users |

---

## 🟠 Warnings — Should Be Reviewed Before Development

> These won't block development but will likely surface as PR comments or test failures.

| # | Type | Description | Recommended Action |
|---|------|-------------|-------------------|
| 1 | Missing edge case | Null email not handled in AC | Add AC or confirm existing global validation handles it |
| 2 | Volume | findAll() implied — no pagination defined | Add page size param or confirm bounded result |
| 3 | NFR | No response time SLA stated | Confirm or accept < 200ms p95 default |
| 4 | Missing benefit | "so that" clause absent from title | PO to add for team understanding |

---

## 🟡 Proposed AC Additions

> These are edge cases not covered by any existing AC.
> The developer should confirm with PO before treating these as in-scope.

**Proposed AC [N+1]:**
```
Given: a user submits a password reset request for an unregistered email
When: the request is processed
Then: the system returns HTTP 200 (do not reveal whether email exists — security)
And: no reset email is sent
```
Confirm: in scope for this story? YES / NO

**Proposed AC [N+2]:**
```
Given: a user requests a password reset more than 5 times in 10 minutes
When: the 6th request is submitted
Then: HTTP 429 Too Many Requests is returned
```
Confirm: in scope? Or a separate rate-limiting story?

---

## ✅ What Is Clear — Safe to Implement

> These parts of the story are unambiguous and ready for Spock specs.

- [AC1]: Happy path — password reset email sent to valid registered user ✅
- [AC2]: Token stored with expiry timestamp in DB ✅
- [AC5]: Existing password reset token invalidated when new one is issued ✅

---

## Questions for Developer Review (Technical)

> These are technical questions the developer should resolve independently
> before starting implementation. No PO involvement needed.

1. Does `UserRepository` already have a `findByEmail()` method, or must it be added?
2. Is there an existing `Token` entity, or must a new `PasswordResetToken` be created?
3. What email template engine is used? (Thymeleaf / FreeMarker / plain text)
4. Is there an existing `NotificationService` for sending emails, or must a new one be created?
5. Should the token be stored as a hash (bcrypt) or plaintext in the DB?

---

## Questions for Product Owner Review (Business)

> These must be answered before development begins.
> Copy this section into a Jira comment or Slack message to the PO.

1. **Token expiry duration** — 30 minutes assumed. Is this correct?
2. **Single-use tokens** — should clicking the link invalidate it immediately?
3. **Unregistered email behaviour** — return 200 silently (security best practice) or 404?
4. **Role restriction** — is this endpoint available to all authenticated users?
5. **Rate limiting** — is there a limit on reset requests per email per time window?
6. **Audit logging** — does a password reset need to be recorded in the audit log?

---

## Recommended Story Split (if story is too large)

> Only present if INVEST-Small failed.

| Sub-story | Title | Scope |
|-----------|-------|-------|
| [STORY-ID]-A | Password reset token generation | POST /password-reset → generate + store token + send email |
| [STORY-ID]-B | Password reset token consumption | POST /password-reset/confirm → validate token + update password |
| [STORY-ID]-C | Token expiry and rate limiting | Background job + 429 handling |

---

## Next Steps

- [ ] PO to answer all 🔴 blocker questions (target: [date])
- [ ] Developer to answer technical questions independently
- [ ] Proposed ACs confirmed in/out of scope with PO
- [ ] Story updated in Jira with resolved ACs
- [ ] Re-run `/story-intake` if significant changes were made
- [ ] Once status = ✅ READY → run `/plan-story`
```

---

## Step 8 — Re-Run Gate

After the developer and PO have resolved the blockers, re-run `/story-intake` with the
updated story. Only when the report outputs:

```
## Status: ✅ READY TO DEVELOP — 0 blockers, 0 contradictions
All ACs are complete, testable, and non-contradictory.
Proceed to: /plan-story
```

...is the story considered safe to plan and implement.
