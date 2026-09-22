package com.benchmark.validation;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class InputValidatorTest {

    private final InputValidator validator = new InputValidator();

    @Test
    void acceptsValidUsername() {
        assertTrue(validator.isValidUsername("alice_99"));
    }

    @Test
    void rejectsNullUsername() {
        assertFalse(validator.isValidUsername(null));
    }

    @Test
    void rejectsBlankUsername() {
        assertFalse(validator.isValidUsername("   "));
    }

    @Test
    void rejectsTooShortUsername() {
        assertFalse(validator.isValidUsername("ab"));
    }

    @Test
    void rejectsTooLongUsername() {
        assertFalse(validator.isValidUsername("a".repeat(21)));
    }

    @Test
    void rejectsUsernameWithDisallowedCharacters() {
        assertFalse(validator.isValidUsername("alice!"));
    }
}
