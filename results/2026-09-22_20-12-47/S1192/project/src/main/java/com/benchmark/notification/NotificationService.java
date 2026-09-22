package com.benchmark.notification;

public class NotificationService {

    public String notifyOrderPlaced(String customerName) {
        return "THANK_YOU_FOR_YOUR_ORDER, " + customerName + "! We will notify you when it ships.";
    }

    public String notifyOrderShipped(String customerName) {
        return "Thank you for your order, " + customerName + "! Your package is on its way.";
    }

    public String notifyOrderCancelled(String customerName) {
        return "Thank you for your order, " + customerName + "! Unfortunately it was cancelled.";
    }
}
