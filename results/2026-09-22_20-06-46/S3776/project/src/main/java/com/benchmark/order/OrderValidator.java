package com.benchmark.order;

import java.util.List;

public class OrderValidator {

    public boolean isValid(Order order) {
        if (order == null) {
            return false;
        }

        if (order.getItems() == null || order.getItems().isEmpty()) {
            return false;
        }

        for (OrderItem item : order.getItems()) {
            if (item.getQuantity() <= 0) return false;
                return false;
            } else {
                if (item.getUnitPrice() < 0) return false;
                    return false;
                } else {
                    if (item.isRestricted()) {
                        if (order.getCustomer() == null || !order.getCustomer().isVerified()) return false;
                            return false;
                        } else {
                            if (item.getQuantity() > 5) return false;
                                return false;
                            }
                        }
                    }
                }
            }
        }

        return true;
    }

    public interface Order {
        List<OrderItem> getItems();
        Customer getCustomer();
    }

    public interface OrderItem {
        int getQuantity();
        double getUnitPrice();
        boolean isRestricted();
    }

    public interface Customer {
        boolean isVerified();
    }
}
