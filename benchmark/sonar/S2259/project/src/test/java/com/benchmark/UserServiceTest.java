package com.benchmark;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class UserServiceTest {

    private final UserService service = new UserService();

    @Test
    void displayNameForKnownUserIsTheirName() {
        User user = new User("Alice");

        assertEquals("Alice", service.getDisplayName(user));
    }

    @Test
    void displayNameForNullUserIsUnknown() {
        assertEquals("Unknown", service.getDisplayName(null));
    }

    @Test
    void nameLengthForKnownUserIsCorrect() {
        User user = new User("Alice");

        assertEquals(5, service.getNameLength(user));
    }

    @Test
    void nameLengthForNullUserDoesNotThrow() {
        assertEquals(0, service.getNameLength(null));
    }
}
