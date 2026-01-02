package org.demo.project.service;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import reactor.test.StepVerifier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

/**
 * Test class for UserService
 * Demonstrates testing Mono with Reactor's StepVerifier
 */
@SpringBootTest
public class UserServiceTest {

    @Autowired
    private UserService userService;

    @Test
    void testGetUserByIdReturnsValidUser() {
        StepVerifier.create(userService.getUserById(1))
                .assertNext(user -> {
                    assertEquals(1, user.getId());
                    assertNotNull(user.getName());
                    assertNotNull(user.getEmail());
                })
                .verifyComplete();
    }

    @Test
    void testGetUserByIdImmediateReturnsValidUser() {
        StepVerifier.create(userService.getUserByIdImmediate(2))
                .assertNext(user -> {
                    assertEquals(2, user.getId());
                    assertEquals("Jane Smith", user.getName());
                })
                .verifyComplete();
    }

    @Test
    void testGetUserByIdWithErrorHandlesPositiveId() {
        StepVerifier.create(userService.getUserByIdWithError(1))
                .assertNext(user -> assertEquals(1, user.getId()))
                .verifyComplete();
    }

    @Test
    void testGetUserByIdWithErrorHandlesNegativeId() {
        StepVerifier.create(userService.getUserByIdWithError(-1))
                .verifyError(IllegalArgumentException.class);
    }
}

