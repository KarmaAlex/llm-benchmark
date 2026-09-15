package com.benchmark.invoice;

public class InvoiceCalculator {

    public double calculateTotal(double subtotal, boolean isPreferredCustomer) {
        double discount = 0.05;
        discount = isPreferredCustomer ? 0.15 : 0.10;

        double total = subtotal - (subtotal * discount);
        return total;
    }
}
