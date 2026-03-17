# /review-story
**Trigger:** `/review-story`
**Description:** Pre-development review — validate existing test coverage gaps, check code quality, confirm acceptance criteria are testable before writing a single line of implementation.

---

## Steps

### 1. Load Story Context
Read the task checklist produced by `/plan-story`. If not available, ask the user to run `/plan-story` first or provide the Story ID and acceptance criteria.

### 2. Review Existing Tests for Affected Classes
For each affected class identified in the plan, check if a Spock spec already exists:
```bash
find src/test/groovy -name "*Spec.groovy" | grep -i [ClassName]
```
For each found spec:
- List existing `given/when/then` blocks
- Identify acceptance criteria NOT yet covered by an existing test
- Flag any tests that are stubs (no assertions or empty `then:` blocks)

### 3. Check Current JaCoCo Coverage Baseline
Run coverage report to capture the before-state:
```bash
./mvnw clean verify -pl [module] jacoco:report -q
```
Open the report and note:
- Current line coverage % for affected packages
- Current branch coverage % for affected packages
- Any classes already below the 80% threshold

Report format:
```
## Coverage Baseline — [module]
| Package | Line Coverage | Branch Coverage | Status |
|---------|--------------|-----------------|--------|
| com.example.service | 74% | 68% | ⚠️ Below threshold |
| com.example.controller | 91% | 85% | ✅ OK |
```

### 4. Validate Acceptance Criteria Testability
For each acceptance criterion, confirm it can be expressed as a Spock `given/when/then` block.
If any AC is ambiguous, output:
```
⚠️ AC [N] is unclear — "[text]"
Suggested clarification: [rewrite as a concrete scenario]
```
Do not proceed until all ACs are testable.

### 5. Detect Code Smells in Affected Files
For each affected Java/Groovy file:
- Flag methods longer than 30 lines
- Flag classes with more than 10 injected dependencies (`@Autowired`, constructor injection)
- Flag missing `@Transactional` on repository-calling service methods where needed
- Flag missing Resilience4j annotations on FeignClient calls

### 6. Review docker-compose.yml (if changes flagged in plan)
If the plan identified Docker Compose changes:
- Read current `docker-compose.yml`
- Confirm required services, env vars, and ports are present or note what needs adding
- Confirm health checks exist for any new dependencies (DB, Kafka, Redis)

### 7. Feature Flag Audit

If the plan identified **Feature Flag = YES**, verify the following before development starts:

```bash
# Confirm FeatureFlags.java constant was added
grep -n "[DOMAIN]_[FEATURE_NAME]" src/main/java/**/FeatureFlags.java

# Confirm local fallback exists in application.yml
grep "feature.[domain].[story-id]" src/main/resources/application.yml

# Confirm Azure App Configuration bootstrap is wired
grep -n "azure.appconfiguration\|spring.cloud.azure.appconfiguration" \
  src/main/resources/bootstrap.yml
```

Flag any of the following as **blockers** — do not proceed to `/develop-story` until resolved:

```
🔴 BLOCKER: FeatureFlags.java constant missing for feature.[domain].[story-id]-[desc]
🔴 BLOCKER: application.yml missing local fallback — feature.[domain].[story-id]-[desc]: false
🔴 BLOCKER: No Azure App Configuration connection in bootstrap.yml
🟠 WARNING: Flag not yet registered in Azure App Configuration (Terraform / CLI)
```

Add to the Review Summary:
```
### Feature Flag
- Key: feature.[domain].[story-id]-[short-description]
- Constant: FeatureFlags.[DOMAIN]_[FEATURE_NAME]
- Local fallback: ✅ present / 🔴 MISSING
- Azure registered: ✅ confirmed / 🟠 pending
- Flag OFF behaviour: [description]
```

### 8. Review Summary

Output:
```
## Pre-Development Review — [PROJ-123]

### Test Gaps (must write Spock specs for these)
- [ClassName]: AC2, AC4 not covered

### Coverage Risk
- [package]: currently at 74%, adding code may drop below 80%

### Code Smell Flags
- [ServiceClass]: 45-line method — consider extracting

### Docker Compose
- Need to add: SMTP_HOST env var to app service

### Feature Flag
- Key: feature.[domain].[story-id]-[short-description]
- Constant: FeatureFlags.[CONSTANT] ✅ / 🔴 MISSING
- Local fallback in application.yml: ✅ / 🔴 MISSING
- Azure App Configuration registered: ✅ / 🟠 pending

### ✅ Ready to develop: YES / ⚠️ Blockers: [list]
```

Next step → run `/develop-story`
