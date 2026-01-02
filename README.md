# MonoFluxDemo - Spring WebFlux Learning Project

A comprehensive Spring WebFlux project demonstrating the differences between **Mono** and **Flux** with practical endpoints and real-world examples.

## 📚 Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Mono vs Flux](#mono-vs-flux)
- [API Endpoints](#api-endpoints)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Learning Path](#learning-path)

---

## 📖 Overview

This project is designed to teach you the fundamentals of **reactive programming** in Spring WebFlux, specifically the differences between:

- **Mono**: A reactive publisher that emits 0 or 1 element (single value)
- **Flux**: A reactive publisher that emits 0 to N elements (multiple values)

### Key Features
✅ 5 Mono endpoints (single value responses)
✅ 8 Flux endpoints (multiple value responses)
✅ Comprehensive service layer with business logic
✅ Full test coverage with StepVerifier and WebTestClient
✅ Detailed documentation and examples
✅ Non-blocking async operations
✅ Production-ready Spring Boot 3.2 with Java 17

---

## 🚀 Getting Started

### Prerequisites
- **Java 17** or higher
- **Maven 3.6** or higher
- A terminal/command prompt

### Quick Start

1. **Build the project:**
```bash
mvn clean package
```

2. **Run the application:**
```bash
mvn spring-boot:run
```

3. **Access the application:**
```
http://localhost:8080/api/info
```

---

## 📁 Project Structure

```
MonoFluxDemo/
├── pom.xml                                    # Maven configuration
├── src/
│   ├── main/
│   │   ├── java/org/demo/project/
│   │   │   ├── MonoFluxDemoApplication.java  # Spring Boot entry point
│   │   │   ├── controller/
│   │   │   │   ├── MonoController.java       # Mono endpoints
│   │   │   │   ├── FluxController.java       # Flux endpoints
│   │   │   │   └── InfoController.java       # Info endpoints
│   │   │   ├── service/
│   │   │   │   ├── UserService.java          # Business logic (Mono)
│   │   │   │   └── ProductService.java       # Business logic (Flux)
│   │   │   └── model/
│   │   │       ├── User.java                 # User entity
│   │   │       └── Product.java              # Product entity
│   │   └── resources/
│   │       └── application.properties        # Spring config
│   └── test/
│       └── java/org/demo/project/
│           ├── controller/                   # Controller tests
│           └── service/                      # Service tests
```

---

## 🎯 Mono vs Flux

### MONO - Single Value (0 or 1)

**What it is:**
- Returns exactly 0 or 1 element
- Non-blocking async operation
- Complete with single value or error

**When to use:**
- Fetch single resource by ID
- Create/update single resource
- Get single computed value
- API calls returning one object

**Example:**
```java
@GetMapping("/user/{id}")
public Mono<User> getUserById(@PathVariable Integer id) {
    return userService.getUserById(id);
}

// Response: {"id": 1, "name": "John Doe", "email": "john@example.com"}
```

---

### FLUX - Multiple Values (0 to N)

**What it is:**
- Returns 0 to many elements
- Stream multiple values asynchronously
- Supports backpressure for large datasets

**When to use:**
- Fetch all resources
- Stream live data
- Server-Sent Events (SSE)
- Process large datasets efficiently

**Example:**
```java
@GetMapping("/products")
public Flux<Product> getAllProducts() {
    return productService.getAllProducts();
}

// Response: [{"id": 1, "name": "Laptop", ...}, {"id": 2, ...}, ...]
```

---

## 🔌 API Endpoints

### Info Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/info` | Get info about all endpoints |
| GET | `/api/explanation` | Get Mono vs Flux explanation |

### Mono Endpoints (Single Value)

| Method | Endpoint | Description | Returns |
|--------|----------|-------------|---------|
| GET | `/api/mono/user/{id}` | Get single user | Single User object |
| GET | `/api/mono/user-immediate/{id}` | Get user (no delay) | Single User object |
| GET | `/api/mono/user-validated/{id}` | Get user with validation | Single User or error |
| GET | `/api/mono/user-email/{id}` | Get user email | String (email) |
| GET | `/api/mono/user-summary/{id}` | Get user summary | String (summary) |

**Example Mono Request:**
```bash
curl http://localhost:8080/api/mono/user/1

# Response:
# {"id":1,"name":"John Doe","email":"john@example.com"}
```

---

### Flux Endpoints (Multiple Values)

| Method | Endpoint | Description | Returns |
|--------|----------|-------------|---------|
| GET | `/api/flux/products` | Get all products | Array of Products |
| GET | `/api/flux/products-stream` | Stream products (NDJSON) | Streamed Products |
| GET | `/api/flux/products-by-price?maxPrice=100` | Products by price | Filtered Products |
| GET | `/api/flux/products-by-price-stream?maxPrice=100` | Stream by price | Streamed Products |
| GET | `/api/flux/low-stock?threshold=20` | Low stock products | Products array |
| GET | `/api/flux/product-names` | All product names | Array of strings |
| GET | `/api/flux/product-names-stream` | Stream product names | Streamed names |
| GET | `/api/flux/products-combined` | Combined products | Array of Products |

**Example Flux Request:**
```bash
curl http://localhost:8080/api/flux/products

# Response:
# [
#   {"id":1,"name":"Laptop","price":999.99,"quantity":5},
#   {"id":2,"name":"Mouse","price":29.99,"quantity":50},
#   ...
# ]
```

---

## 🚀 Running the Application

### Start the Server
```bash
cd C:\projects\MonoFluxDemo
mvn spring-boot:run
```

The application will start on `http://localhost:8080`

### Test Endpoints

**Using cURL:**
```bash
# Test Mono endpoint
curl http://localhost:8080/api/mono/user/1

# Test Flux endpoint
curl http://localhost:8080/api/flux/products

# Test with parameters
curl "http://localhost:8080/api/flux/products-by-price?maxPrice=100"
```

**Using PowerShell:**
```powershell
# Mono
Invoke-WebRequest -Uri "http://localhost:8080/api/mono/user/1" | Select-Object -ExpandProperty Content

# Flux
Invoke-WebRequest -Uri "http://localhost:8080/api/flux/products" | Select-Object -ExpandProperty Content
```

**Using Browser:**
```
http://localhost:8080/api/info
http://localhost:8080/api/mono/user/1
http://localhost:8080/api/flux/products
```

---

## 🧪 Testing

### Run All Tests
```bash
mvn test
```

### Run Specific Tests
```bash
# Test Mono controller
mvn test -Dtest=MonoControllerTest

# Test Flux controller
mvn test -Dtest=FluxControllerTest

# Test services
mvn test -Dtest=UserServiceTest
mvn test -Dtest=ProductServiceTest
```

### Test Coverage
```bash
mvn test jacoco:report
```

### Testing Pattern Example

**Testing Mono with StepVerifier:**
```java
@Test
void testGetUserById() {
    StepVerifier.create(userService.getUserById(1))
            .assertNext(user -> assertEquals(1, user.getId()))
            .verifyComplete();
}
```

**Testing Flux Endpoint with WebTestClient:**
```java
@Test
void testGetAllProducts() {
    webTestClient.get()
            .uri("/api/flux/products")
            .exchange()
            .expectStatus().isOk()
            .expectBodyList(Product.class)
            .hasSize(5);
}
```

---

## 💻 Code Examples

### UserService - Mono Examples

```java
@Service
public class UserService {
    
    // Mono with async delay
    public Mono<User> getUserById(Integer userId) {
        return Mono.create(sink -> {
            try {
                Thread.sleep(1000);
                User user = new User(userId, "John Doe", "john@example.com");
                sink.success(user);
            } catch (InterruptedException e) {
                sink.error(e);
            }
        });
    }
    
    // Mono with immediate response
    public Mono<User> getUserByIdImmediate(Integer userId) {
        return Mono.just(new User(userId, "Jane Smith", "jane@example.com"));
    }
    
    // Mono with error handling
    public Mono<User> getUserByIdWithError(Integer userId) {
        if (userId < 0) {
            return Mono.error(new IllegalArgumentException("User ID must be positive"));
        }
        return Mono.just(new User(userId, "Valid User", "valid@example.com"));
    }
}
```

### ProductService - Flux Examples

```java
@Service
public class ProductService {
    
    private List<Product> products = Arrays.asList(
            new Product(1, "Laptop", 999.99, 5),
            new Product(2, "Mouse", 29.99, 50),
            new Product(3, "Keyboard", 79.99, 30),
            new Product(4, "Monitor", 299.99, 10),
            new Product(5, "Headphones", 149.99, 25)
    );
    
    // Flux - return all products
    public Flux<Product> getAllProducts() {
        return Flux.fromIterable(products);
    }
    
    // Flux with filtering
    public Flux<Product> getProductsByMaxPrice(Double maxPrice) {
        return Flux.fromIterable(products)
                .filter(product -> product.getPrice() <= maxPrice);
    }
    
    // Flux with transformation
    public Flux<String> getProductNames() {
        return Flux.fromIterable(products)
                .map(Product::getName);
    }
}
```

---

## 📊 Comparison Table

| Feature | Mono | Flux |
|---------|------|------|
| Elements | 0 or 1 | 0 to N |
| Response Type | Single object | Array or stream |
| Memory Usage | O(1) | O(1) streaming |
| Backpressure | Not needed | Essential |
| Use Case | Single value | Multiple values |
| Typical Endpoint | GET /user/1 | GET /users |
| Response Time | Fast | Scalable |

---

## 🎓 Learning Resources

### Concepts Covered
1. **Reactive Streams** - Non-blocking asynchronous data processing
2. **Mono** - Publisher for 0-1 elements
3. **Flux** - Publisher for 0-N elements
4. **Operators** - map, filter, flatMap, etc.
5. **Error Handling** - onErrorReturn, onErrorResume, etc.
6. **Backpressure** - Consumer-driven flow control
7. **Testing** - StepVerifier and WebTestClient

### Project Reactor Documentation
- https://projectreactor.io/docs/core/latest/reference/

### Spring WebFlux Guide
- https://spring.io/guides/gs/reactive-rest-service/

### Reactive Streams Specification
- https://www.reactive-streams.org/

---

## 🔧 Configuration

The application is configured via `application.properties`:

```properties
spring.application.name=MonoFluxDemo
spring.webflux.base-path=/
server.port=8080
logging.level.root=INFO
logging.level.org.demo.project=DEBUG
```

### Change Server Port
```properties
server.port=8081
```

### Enable Debug Logging
```properties
logging.level.org.demo.project=DEBUG
logging.level.org.springframework.web=DEBUG
```

---

## 🚨 Troubleshooting

### Port Already in Use
```bash
# Use different port
mvn spring-boot:run -Dspring-boot.run.arguments="--server.port=8081"
```

### Tests Failing
```bash
# Clean and rebuild
mvn clean install
mvn test
```

### Application Won't Start
```bash
# Check if dependencies are downloaded
mvn dependency:resolve

# Clean build
mvn clean install
```

### Endpoints Not Responding
1. Verify application is running on port 8080
2. Check logs for errors
3. Ensure correct endpoint URL format

---

## 📝 Quick Reference

### Mono Operations
```java
// Create Mono
Mono.just(value)                    // From value
Mono.empty()                        // Empty Mono
Mono.error(exception)               // Error Mono
Mono.fromCallable(() -> value)      // From callable

// Transform
mono.map(x -> x * 2)                // Transform value
mono.flatMap(x -> monoX)            // Flat map to Mono

// Handle errors
mono.onErrorReturn(defaultValue)    // Default on error
mono.onErrorResume(fallbackMono)    // Fallback Mono
mono.doOnError(e -> log(e))         // Side effect on error

// Complete
mono.subscribe()                    // Subscribe
mono.block()                        // Blocking get (use cautiously)
```

### Flux Operations
```java
// Create Flux
Flux.just(v1, v2, v3)               // From values
Flux.fromIterable(list)             // From list
Flux.range(1, 10)                   // Number range
Flux.empty()                        // Empty Flux
Flux.error(exception)               // Error Flux

// Transform
flux.map(x -> x * 2)                // Transform each
flux.filter(x -> x > 5)             // Filter elements
flux.flatMap(x -> fluxX)            // Flat map to Flux

// Combine
Flux.concat(flux1, flux2)           // Concatenate
Flux.merge(flux1, flux2)            // Merge (interleaved)
flux.distinct()                     // Remove duplicates

// Handle errors
flux.onErrorReturn(defaultValue)    // Default on error
flux.onErrorResume(fallbackFlux)    // Fallback Flux
flux.doOnError(e -> log(e))         // Side effect on error

// Complete
flux.subscribe()                    // Subscribe
flux.collectList().block()          // Collect to list (blocking)
```

---

## 🎬 Next Steps

1. **Explore the endpoints** - Use cURL or browser to test all endpoints
2. **Read the source code** - Understand implementations in service and controller classes
3. **Run the tests** - See how to test reactive code
4. **Modify the code** - Add new endpoints, operators, or business logic
5. **Integrate with database** - Use R2DBC for reactive database access
6. **Add WebSocket** - Implement real-time bidirectional communication

---

## 📞 Need Help?

- Check logs for detailed error messages
- Review source code comments for explanations
- Read official Spring WebFlux documentation
- Experiment with different operators and patterns

---

## 📄 License

MIT License - Feel free to use this project for learning and development.

---

## 🎉 Happy Learning!

This project provides a solid foundation for understanding Spring WebFlux and reactive programming. Start with the simple Mono endpoints and progress to more complex Flux operations.

**Quick start command:**
```bash
mvn spring-boot:run
```

Then visit: `http://localhost:8080/api/info`

Good luck! 🚀

