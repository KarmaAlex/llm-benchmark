package com.benchmark.customer;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import org.junit.jupiter.api.Test;

class CustomerProfileTest {

    @Test
    void constructorPopulatesFields() {
        CustomerProfile profile = new CustomerProfile("alice@example.com", "555-1234");

        assertEquals("alice@example.com", profile.getEmail());
        assertEquals("555-1234", profile.getPhoneNumber());
    }

    @Test
    void resetClearsThePhoneNumber() {
        CustomerProfile profile = new CustomerProfile("alice@example.com", "555-1234");

        profile.reset();

        assertNull(profile.getPhoneNumber());
    }

    @Test
    void resetMustNotClearTheNonNullEmail() {
        CustomerProfile profile = new CustomerProfile("alice@example.com", "555-1234");

        profile.reset();

        assertEquals(
                "alice@example.com",
                profile.getEmail(),
                "email is @NonNull and must survive reset()");
    }
}
