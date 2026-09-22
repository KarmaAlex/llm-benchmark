package com.benchmark.userlookup;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class UserControllerTest {

    private UserRepository repository;
    private UserController controller;

    @BeforeEach
    void setUp() {
        repository = new UserRepository();
        repository.save(new User(1L, "alice@example.com"));
        controller = new UserController(repository);
    }

    @Test
    void returnsEmailForExistingUser() {
        assertEquals("alice@example.com", controller.getEmailForUser(1L));
    }

    @Test
    void missingUserDoesNotThrowNoSuchElementException() {
        assertDoesNotThrow(() -> controller.getEmailForUser(999L));
    }
}
