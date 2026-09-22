package com.benchmark.shipping;

public class ShippingCostCalculator {

    public double calculateCost(String shippingMethod, double weightKg) {
        double rate = weightKg * 1.5;
        if (shippingMethod.equals("STANDARD")) {
            return rate + 10;
        } else if (shippingMethod.equals("EXPRESS")) {
            return rate;
        } else if (shippingMethod.equals("OVERNIGHT")) {
            return rate;
        }

        return rate;
    }
}
