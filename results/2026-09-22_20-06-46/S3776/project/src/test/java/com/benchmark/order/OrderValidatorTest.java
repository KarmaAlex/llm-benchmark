package com.benchmark.order;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class OrderValidatorTest {

    private final OrderValidator validator = new OrderValidator();

    @Test
    void nullOrderIsInvalid() {
        assertFalse(validator.isValid(null));
    }

    @Test
    void orderWithNoItemsIsInvalid() {
        assertFalse(validator.isValid(new TestOrder(List.of(), null)));
    }

    @Test
    void orderWithOnlyUnrestrictedValidItemsIsValid() {
        TestOrder order = new TestOrder(List.of(new TestItem(2, 10.0, false)), null);

        assertTrue(validator.isValid(order));
    }

    @Test
    void itemWithNonPositiveQuantityIsInvalid() {
        TestOrder order = new TestOrder(List.of(new TestItem(0, 10.0, false)), null);

        assertFalse(validator.isValid(order));
    }

    @Test
    void itemWithNegativePriceIsInvalid() {
        TestOrder order = new TestOrder(List.of(new TestItem(1, -1.0, false)), null);

        assertFalse(validator.isValid(order));
    }

    @Test
    void restrictedItemWithoutVerifiedCustomerIsInvalid() {
        TestOrder order = new TestOrder(List.of(new TestItem(1, 10.0, true)), new TestCustomer(false));

        assertFalse(validator.isValid(order));
    }

    @Test
    void restrictedItemWithVerifiedCustomerWithinLimitIsValid() {
        TestOrder order = new TestOrder(List.of(new TestItem(5, 10.0, true)), new TestCustomer(true));

        assertTrue(validator.isValid(order));
    }

    @Test
    void restrictedItemWithVerifiedCustomerOverLimitIsInvalid() {
        TestOrder order = new TestOrder(List.of(new TestItem(6, 10.0, true)), new TestCustomer(true));

        assertFalse(validator.isValid(order));
    }

    private record TestOrder(
            List<OrderValidator.OrderItem> items,
            OrderValidator.Customer customer) implements OrderValidator.Order {

        @Override
        public List<OrderValidator.OrderItem> getItems() {
            return items;
        }

        @Override
        public OrderValidator.Customer getCustomer() {
            return customer;
        }
    }

    private record TestItem(
            int quantity,
            double unitPrice,
            boolean restricted) implements OrderValidator.OrderItem {

        @Override
        public int getQuantity() {
            return quantity;
        }

        @Override
        public double getUnitPrice() {
            return unitPrice;
        }

        @Override
        public boolean isRestricted() {
            return restricted;
        }
    }

    private record TestCustomer(boolean verified) implements OrderValidator.Customer {

        @Override
        public boolean isVerified() {
            return verified;
        }
    }
}
