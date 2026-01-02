package org.demo.project.controller;

import org.demo.project.model.User;
import org.demo.project.service.UserService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.WebFluxTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Mono;

import static org.mockito.Mockito.when;

/**
 * Test class for MonoController
 * Demonstrates testing reactive endpoints that return Mono
 */
@WebFluxTest(MonoController.class)
public class MonoControllerTest {

    @Autowired
    private WebTestClient webTestClient;

    @MockBean
    private UserService userService;

    @Test
    void testGetUserById() {
        Integer userId = 1;
        User expectedUser = new User(userId, "Test User", "test@example.com");

        when(userService.getUserById(userId))
                .thenReturn(Mono.just(expectedUser));

        webTestClient.get()
                .uri("/api/mono/user/{id}", userId)
                .exchange()
                .expectStatus().isOk()
                .expectBody(User.class)
                .isEqualTo(expectedUser);
    }

    @Test
    void testGetUserByIdImmediate() {
        Integer userId = 2;
        User expectedUser = new User(userId, "Immediate User", "immediate@example.com");

        when(userService.getUserByIdImmediate(userId))
                .thenReturn(Mono.just(expectedUser));

        webTestClient.get()
                .uri("/api/mono/user-immediate/{id}", userId)
                .exchange()
                .expectStatus().isOk()
                .expectBody()
                .jsonPath("$.id").isEqualTo(userId)
                .jsonPath("$.name").isEqualTo("Immediate User");
    }

    @Test
    void testGetUserByIdWithValidation_ValidId() {
        Integer userId = 1;
        User expectedUser = new User(userId, "Valid User", "valid@example.com");

        when(userService.getUserByIdWithError(userId))
                .thenReturn(Mono.just(expectedUser));

        webTestClient.get()
                .uri("/api/mono/user-validated/{id}", userId)
                .exchange()
                .expectStatus().isOk();
    }

    @Test
    void testGetUserByIdWithValidation_InvalidId() {
        Integer userId = -1;

        when(userService.getUserByIdWithError(userId))
                .thenReturn(Mono.error(new IllegalArgumentException("User ID must be positive")));

        webTestClient.get()
                .uri("/api/mono/user-validated/{id}", userId)
                .exchange()
                .expectStatus().is5xxServerError();
    }
}

