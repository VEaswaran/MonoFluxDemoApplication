package org.demo.project.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;

/**
 * InfoController provides information about the application
 * and the differences between Mono and Flux
 */
@RestController
@RequestMapping("/api")
public class InfoController {

    /**
     * Returns information about the application
     */
    @GetMapping("/info")
    public Mono<Map<String, Object>> getInfo() {
        return Mono.fromCallable(() -> {
            Map<String, Object> info = new HashMap<>();
            info.put("application", "MonoFluxDemo");
            info.put("description", "Spring WebFlux demo to learn Mono vs Flux");
            info.put("version", "1.0.0");
            info.put("monoEndpoints", Map.of(
                    "/api/mono/user/{id}", "Get a single user (Mono - single value)",
                    "/api/mono/user-immediate/{id}", "Get user immediately (Mono - no delay)",
                    "/api/mono/user-email/{id}", "Get user email (Mono - transformation)",
                    "/api/mono/user-summary/{id}", "Get user summary (Mono - chaining)"
            ));
            info.put("fluxEndpoints", Map.of(
                    "/api/flux/products", "Get all products (Flux - multiple values)",
                    "/api/flux/products-stream", "Stream products (Flux - NDJSON)",
                    "/api/flux/products-by-price", "Filter by price (Flux - with parameter)",
                    "/api/flux/low-stock", "Low stock products (Flux - business logic)",
                    "/api/flux/product-names", "Get product names (Flux - transformation)"
            ));
            return info;
        });
    }

    /**
     * Returns explanation of Mono vs Flux
     */
        @GetMapping("/explanation")
    public Mono<Map<String, String>> getExplanation() {
        return Mono.fromCallable(() -> {
            Map<String, String> explanation = new HashMap<>();
            explanation.put("MONO",
                "Mono is a Reactive Streams Publisher that emits 0 or 1 element.\n" +
                "- Use case: Single value/response\n" +
                "- Examples: Get one user by ID, fetch single configuration, API call returning one result\n" +
                "- Performance: Best for operations with one result\n" +
                "- Memory: Minimal - handles only one value\n" +
                "- Thread model: Non-blocking, single element subscription");

            explanation.put("FLUX",
                "Flux is a Reactive Streams Publisher that emits 0 to N elements.\n" +
                "- Use case: Multiple values/streaming data\n" +
                "- Examples: Get all users, stream live data, paginated results\n" +
                "- Performance: Optimized for streaming large datasets\n" +
                "- Memory: Efficient - processes one item at a time (backpressure)\n" +
                "- Thread model: Non-blocking, multiple element subscription with back-pressure support");

            explanation.put("KEY_DIFFERENCES",
                "1. Cardinality: Mono=0-1, Flux=0-N\n" +
                "2. Response: Mono=single JSON object, Flux=JSON array or stream\n" +
                "3. Memory: Mono=small, Flux=can handle large datasets\n" +
                "4. Use: Mono=single resource, Flux=collections/streams\n" +
                "5. Backpressure: Both support it, but Flux is more critical");

            explanation.put("WHEN_TO_USE_MONO",
                "- Finding a user by ID\n" +
                "- Getting current configuration\n" +
                "- Creating a single resource\n" +
                "- Fetching count of items\n" +
                "- API calls returning single object");

            explanation.put("WHEN_TO_USE_FLUX",
                "- Fetching all users from database\n" +
                "- Streaming data in real-time\n" +
                "- Processing large datasets\n" +
                "- Server-Sent Events (SSE)\n" +
                "- Paginated/filtered results");

            return explanation;
        });
    }
}

