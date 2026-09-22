package com.benchmark.invoice;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class InvoiceCalculatorTest {

    private static final double DELTA = 1e-9;

    private final InvoiceCalculator calculator = new InvoiceCalculator();

    @Test
    void regularCustomerGetsStandardDiscount() {
        assertEquals(90.0, calculator.calculateTotal(100.0, false), DELTA);
    }

    @Test
    void preferredCustomerGetsBetterDiscount() {
        assertEquals(85.0, calculator.calculateTotal(100.0, true), DELTA);
    }

    @Test
    void regularCustomerBulkOrderGetsBonusDiscount() {
        assertEquals(510.0, calculator.calculateTotal(600.0, false), DELTA);
    }

    @Test
    void preferredCustomerBulkOrderGetsBonusDiscount() {
        assertEquals(480.0, calculator.calculateTotal(600.0, true), DELTA);
    }

    @Test
    void negativeSubtotalIsRejected() {
        assertThrows(IllegalArgumentException.class, () -> calculator.calculateTotal(-1.0, false));
    }
}
