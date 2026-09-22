package com.benchmark.cart;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class ShoppingCartTest {

    private ShoppingCart cart;

    @BeforeEach
    void setUp() {
        cart = new ShoppingCart();
    }

    @Test
    void newCartIsEmpty() {
        assertTrue(cart.isCartEmpty());
        assertEquals(0, cart.itemCount());
    }

    @Test
    void addingItemMakesCartNonEmpty() {
        cart.addItem("book");

        assertFalse(cart.isCartEmpty());
        assertEquals(1, cart.itemCount());
    }

    @Test
    void removingExistingItemSucceeds() {
        cart.addItem("book");

        assertTrue(cart.removeItem("book"));
        assertTrue(cart.isCartEmpty());
    }

    @Test
    void removingMissingItemFails() {
        assertFalse(cart.removeItem("book"));
    }

    @Test
    void clearEmptiesTheCart() {
        cart.addItem("book");
        cart.addItem("pen");

        cart.clear();

        assertTrue(cart.isCartEmpty());
        assertEquals(0, cart.itemCount());
    }
}
