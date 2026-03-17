# /deploy-story
**Trigger:** `/deploy-story`
**Description:** Build, validate, and deploy the feature using Docker Compose. Smoke test, capture logs, and open a PR.

---

## Steps

### 1. Pre-Deploy Checklist
Confirm all of the following before building:
- [ ] `git status` — working tree is clean
- [ ] All Spock specs pass: `./mvnw test -pl [module] -q`
- [ ] JaCoCo threshold met: `./mvnw verify -pl [module] -q`
- [ ] No `TODO` or `FIXME` left in files changed in this branch:
  ```bash
  git diff main --name-only | xargs grep -l "TODO\|FIXME" 2>/dev/null
  ```

### 2. Build the Spring Boot JAR
```bash
./mvnw clean package -pl [module] -DskipTests -q
```
Confirm JAR exists:
```bash
ls -lh [module]/target/*.jar
```

### 3. Build Docker Image
```bash
docker build \
  --build-arg JAR_FILE=[module]/target/[artifact]-*.jar \
  -t [image-name]:[story-id] \
  -f [module]/Dockerfile \
  .
```

Verify image was built:
```bash
docker images [image-name]
```

#### Expected Dockerfile pattern (Spring Boot layered JAR)
```dockerfile
FROM eclipse-temurin:21-jre-alpine AS runtime
WORKDIR /app
ARG JAR_FILE
COPY ${JAR_FILE} app.jar
EXPOSE 8080
ENTRYPOINT ["java", \
  "-Djava.security.egd=file:/dev/./urandom", \
  "-jar", "app.jar"]
```

### 4. Update docker-compose.yml (if required by plan)
If the plan or review identified Docker Compose changes:
- Add/update service definition
- Add new environment variables
- Add health check if missing:
```yaml
healthcheck:
  test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:8080/actuator/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```
- Ensure the new image tag is referenced:
```yaml
services:
  [service-name]:
    image: [image-name]:[story-id]
    # OR for local build:
    build:
      context: .
      dockerfile: [module]/Dockerfile
```

### 5. Start / Restart with Docker Compose
Bring up only the changed service (avoid full restart if possible):
```bash
docker compose up -d --no-deps [service-name]
```

Watch startup logs:
```bash
docker compose logs -f [service-name] --tail=60
```

Wait for healthy status:
```bash
docker compose ps [service-name]
# Expected: STATUS = Up (healthy)
```

If startup fails:
```bash
docker compose logs [service-name] --tail=100
# Fix issue, rebuild, and retry from step 3
```

### 6. Smoke Tests
Run basic endpoint checks against the running container:

```bash
# Health check
curl -sf http://localhost:8080/actuator/health | jq .

# Key business endpoint (replace with actual)
curl -sf -X [METHOD] http://localhost:[PORT]/[endpoint] \
  -H "Content-Type: application/json" \
  -d '[request body if POST/PUT]' | jq .
```

Expected:
- Health: `{"status":"UP"}`
- Endpoint: HTTP 2xx with correct response shape

### 7. Capture Coverage Report Path
```bash
echo "JaCoCo report: $(pwd)/[module]/target/site/jacoco/index.html"
```
Note this path for the PR description.

### 8. Stop Local Stack (optional)
```bash
docker compose down
```
Or leave up if integration testing continues.

### 9. Push Branch and Open PR
```bash
git push origin feature/[PROJ-123]-short-description
```

Create PR via GitHub CLI:
```bash
gh pr create \
  --title "[PROJ-123] Story title" \
  --body "## Summary
Implements [story title].

## Acceptance Criteria
- [x] AC1: [description]
- [x] AC2: [description]

## Test Coverage
- Spock specs added: [list]
- JaCoCo line coverage: [X]%
- JaCoCo branch coverage: [Y]%

## Docker
- Image: \`[image-name]:[story-id]\`
- Docker Compose: [changed / no changes]

## Checklist
- [x] All Spock specs pass
- [x] JaCoCo threshold met (≥80% line, ≥75% branch)
- [x] No TODOs left in changed files
- [x] docker compose up smoke test passed
" \
  --base main
```

### 10. Deploy Summary
Output a final summary:
```
## Deploy Summary — [PROJ-123]

✅ JAR built:    [module]/target/[artifact].jar
✅ Image:        [image-name]:[story-id]
✅ Compose:      [service-name] Up (healthy)
✅ Smoke test:   HTTP 200 on /[endpoint]
✅ Coverage:     Line [X]% | Branch [Y]%
✅ PR opened:    [PR URL]
```
