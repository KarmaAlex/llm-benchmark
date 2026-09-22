package com.benchmark.notification;

public class NotificationService {

    private static final String ORDER_GREETING = "Thank you for your order, ";

    public String notifyOrderPlaced(String customerName) {
        return ORDER_GREETING + customerName + "! We will notify you when it ships.";
    }

    public String notifyOrderShipped(String customerName) {
        return ORDER_GREETING + customerName + "! Your package is on its way.";
    }

    public String notifyOrderCancelled(String customerName) {
        return ORDER_GREETING + customerName + "! Unfortunately it was cancelled.";
    }
}
