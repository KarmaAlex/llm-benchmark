package com.benchmark.invoice;

public class InvoiceCalculator {

    public double calculateTotal(double subtotal, boolean isPreferredCustomer) {
        double discount = 0.05;
        discount = isPreferredCustomer ? 0.15 : 0.10;

        if (subtotal < 0) {
            throw new IllegalArgumentException("subtotal must not be negative");
        }

        if (subtotal > BULK_ORDER_THRESHOLD) {
            discount += BULK_ORDER_BONUS;
        }

        double total = subtotal - (subtotal * discount);
        return total;
    }

    private static final double BULK_ORDER_THRESHOLD = 500.0;
    private static final double BULK_ORDER_BONUS = 0.05;
}
