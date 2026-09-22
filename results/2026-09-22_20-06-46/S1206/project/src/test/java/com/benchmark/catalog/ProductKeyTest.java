package com.benchmark.catalog;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

class ProductKeyTest {

    @Test
    void keysWithTheSameFieldsAreEqual() {
        assertEquals(
                new ProductKey("SKU-1", "EAST", 2),
                new ProductKey("SKU-1", "EAST", 2));
    }

    @Test
    void keysWithADifferentRevisionAreNotEqual() {
        assertNotEquals(
                new ProductKey("SKU-1", "EAST", 2),
                new ProductKey("SKU-1", "EAST", 3));
    }

    @Test
    void equalKeysShareTheSameHashCode() {
        assertEquals(
                new ProductKey("SKU-1", "EAST", 2).hashCode(),
                new ProductKey("SKU-1", "EAST", 2).hashCode());
    }

    @Test
    void equalKeysAreDeduplicatedInAHashSet() {
        Set<ProductKey> keys = new HashSet<>();
        keys.add(new ProductKey("SKU-1", "EAST", 2));
        keys.add(new ProductKey("SKU-1", "EAST", 2));

        assertEquals(1, keys.size());
    }

    @Test
    void hashMapLookupFindsAnEquivalentKey() {
        Map<ProductKey, Integer> stockLevels = new HashMap<>();
        stockLevels.put(new ProductKey("SKU-1", "EAST", 2), 42);

        assertEquals(42, stockLevels.get(new ProductKey("SKU-1", "EAST", 2)));
    }
}
