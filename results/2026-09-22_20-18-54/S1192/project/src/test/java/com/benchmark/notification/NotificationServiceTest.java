package com.benchmark.notification;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class NotificationServiceTest {

    private final NotificationService service = new NotificationService();

    @Test
    void orderPlacedMessage() {
        assertEquals(
                "Thank you for your order, Alice! We will notify you when it ships.",
                service.notifyOrderPlaced("Alice"));
    }

    @Test
    void orderShippedMessage() {
        assertEquals(
                "Thank you for your order, Alice! Your package is on its way.",
                service.notifyOrderShipped("Alice"));
    }

    @Test
    void orderCancelledMessage() {
        assertEquals(
                "Thank you for your order, Alice! Unfortunately it was cancelled.",
                service.notifyOrderCancelled("Alice"));
    }
}
