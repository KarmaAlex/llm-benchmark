package com.benchmark.shipping;

public class ShippingCostCalculator {

    public double calculateCost(String shippingMethod, double weightKg) {
        double rate = weightKg * 1.5;
        if (shippingMethod.equals("STANDARD")) {
            return rate * 1.2;
        } else if (shippingMethod.equals("EXPRESS")) {
            return rate * 1.8;
        } else if (shippingMethod.equals("OVERNIGHT")) {
            return rate * 3.0;
        }

        return rate;
    }
}
