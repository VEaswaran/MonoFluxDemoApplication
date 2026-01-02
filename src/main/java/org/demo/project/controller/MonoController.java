package org.demo.project.controller;

import org.demo.project.model.User;
import org.demo.project.service.UserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

/**
 * MonoController demonstrates endpoints that return Mono
 * Mono returns a single response (0 or 1 element)
 *
 * Endpoints in this controller are ideal for:
 * - Fetching a single resource by ID
 * - Getting one result from an API
 * - Returning single computed values
 */
@RestController
@RequestMapping("/api/mono")
public class MonoController {

    @Autowired
    private UserService userService;

    /**
     * Endpoint that returns a single user as JSON
     * Response type: Single JSON object
     * Use Mono when: You expect exactly 0 or 1 result
     *
     * Example: GET /api/mono/user/1
     * Response: { "id": 1, "name": "John Doe", "email": "john@example.com" }
     */
    @GetMapping("/user/{id}")
    public Mono<User> getUserById(@PathVariable Integer id) {
        return userService.getUserById(id);
    }

    /**
     * Endpoint that returns a user immediately without delay
     * Demonstrates Mono.just() usage
     *
     * Example: GET /api/mono/user-immediate/2
     * Response: Immediate JSON response
     */
    @GetMapping("/user-immediate/{id}")
    public Mono<User> getUserByIdImmediate(@PathVariable Integer id) {
        return userService.getUserByIdImmediate(id);
    }

    /**
     * Endpoint that demonstrates error handling with Mono
     * Returns an error if ID is negative
     *
     * Example: GET /api/mono/user-validated/1 (success)
     * Example: GET /api/mono/user-validated/-1 (error)
     */
    @GetMapping("/user-validated/{id}")
    public Mono<User> getUserByIdWithValidation(@PathVariable Integer id) {
        return userService.getUserByIdWithError(id);
    }

    /**
     * Endpoint that shows Mono transformation
     * Transforms the User object to extract just the email
     *
     * Example: GET /api/mono/user-email/1
     * Response: "john@example.com"
     */
    @GetMapping("/user-email/{id}")
    public Mono<String> getUserEmail(@PathVariable Integer id) {
        return userService.getUserById(id)
                .map(User::getEmail)
                .defaultIfEmpty("User not found");
    }

    /**
     * Endpoint that demonstrates Mono chaining
     * Gets user and applies transformations
     *
     * Example: GET /api/mono/user-summary/1
     * Response: "User: John Doe (john@example.com)"
     */
    @GetMapping("/user-summary/{id}")
    public Mono<String> getUserSummary(@PathVariable Integer id) {
        return userService.getUserById(id)
                .map(user -> String.format("User: %s (%s)", user.getName(), user.getEmail()))
                .onErrorReturn("Error fetching user");
    }
}

