package org.demo.project.service;

import org.demo.project.model.User;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

/**
 * UserService demonstrates the use of Mono
 * Mono is used when you need to return a single value (0 or 1 element)
 */
@Service
public class UserService {

    /**
     * Retrieve a single user by ID
     * Returns a Mono that emits a User object or empty if not found
     *
     * Use case: Getting a single record from database, API response with one item
     */
    public Mono<User> getUserById(Integer userId) {
        // Simulate fetching from database with a delay
        return Mono.create(sink -> {
            try {
                Thread.sleep(1000); // Simulate DB query time
                User user = new User(userId, "John Doe", "john@example.com");
                sink.success(user);
            } catch (InterruptedException e) {
                sink.error(e);
            }
        });
    }

    /**
     * Alternative implementation using Mono.just() for immediate response
     */
    public Mono<User> getUserByIdImmediate(Integer userId) {
        return Mono.just(new User(userId, "Jane Smith", "jane@example.com"));
    }

    /**
     * Demonstrate Mono error handling
     */
    public Mono<User> getUserByIdWithError(Integer userId) {
        if (userId < 0) {
            return Mono.error(new IllegalArgumentException("User ID must be positive"));
        }
        return Mono.just(new User(userId, "Valid User", "valid@example.com"));
    }
}

