package com.benchmark.cart;

import java.util.ArrayList;
import java.util.List;

public class ShoppingCart {

    private final List<String> items = new ArrayList<>();

    public void addItem(String item) {
        items.add(item);
    }

    public boolean isCartEmpty() {
        return items.size() == 0;
    }

    public boolean removeItem(String item) {
        return items.remove(item);
    }

    public int itemCount() {
        return items.size();
    }

    public void clear() {
        items.clear();
    }
}
