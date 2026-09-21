package com.benchmark.shipping;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class ShippingCostCalculatorTest {

    private static final double DELTA = 1e-9;

    private final ShippingCostCalculator calculator = new ShippingCostCalculator();

    @Test
    void standardShippingChargesPerKilo() {
        assertEquals(15.0, calculator.calculateCost("STANDARD", 10.0), DELTA);
    }

    @Test
    void expressShippingChargesPerKilo() {
        assertEquals(15.0, calculator.calculateCost("EXPRESS", 10.0), DELTA);
    }

    @Test
    void overnightShippingChargesPerKilo() {
        assertEquals(15.0, calculator.calculateCost("OVERNIGHT", 10.0), DELTA);
    }

    @Test
    void unknownShippingMethodIsFree() {
        assertEquals(0.0, calculator.calculateCost("DRONE", 10.0), DELTA);
    }
}
