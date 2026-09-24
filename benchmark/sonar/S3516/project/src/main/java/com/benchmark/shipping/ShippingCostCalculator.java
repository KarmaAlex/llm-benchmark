package com.benchmark.shipping;

public class ShippingCostCalculator {

    /**
     * Calculates the cost of shipping a parcel.
     *
     * STANDARD, EXPRESS and OVERNIGHT shipping are charged at 1.5 per kilogram.
     * Any other shipping method is free.
     *
     * @param shippingMethod the shipping method requested by the customer
     * @param weightKg the parcel weight in kilograms
     * @return the shipping cost, or 0 for any other shipping method
     */
    public double calculateCost(String shippingMethod, double weightKg) {
        double rate = weightKg * 1.5;
        if (shippingMethod.equals("STANDARD")) {
            return rate;
        } else if (shippingMethod.equals("EXPRESS")) {
            return rate;
        } else if (shippingMethod.equals("OVERNIGHT")) {
            return rate;
        }

        return rate;
    }
}
