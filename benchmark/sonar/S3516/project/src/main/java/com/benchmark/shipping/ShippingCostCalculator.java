package com.benchmark.shipping;

public class ShippingCostCalculator {

    public double calculateCost(String shippingMethod, double weightKg) {
        if (shippingMethod.equals("STANDARD")) {
            return weightKg * 1.5;
        } else if (shippingMethod.equals("EXPRESS")) {
            return weightKg * 1.5;
        } else if (shippingMethod.equals("OVERNIGHT")) {
            return weightKg * 1.5;
        }

        return 0.0;
    }
}
