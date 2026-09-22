package com.benchmark.notification;

public class NotificationService {

    public String notifyOrderPlaced(String customerName) {
        private static final String ORDER_GREETING = "Thank you for your order, ";

return ORDER_GREETING + customerName + "! We will notify you when it ships.";
    }

    public String notifyOrderShipped(String customerName) {
        return ORDER_GREETING + customerName + "! Your package is on its way.";
    }

    public String notifyOrderCancelled(String customerName) {
        return ORDER_GREETING + customerName + "! Unfortunately it was cancelled.";
    }
}
