package com.benchmark.catalog;

import java.util.Objects;

public class ProductKey {

    private final String sku;
    private final String warehouse;
    private final int revision;

    public ProductKey(String sku, String warehouse, int revision) {
        this.sku = sku;
        this.warehouse = warehouse;
        this.revision = revision;
    }

    public String getSku() {
        return sku;
    }

    public String getWarehouse() {
        return warehouse;
    }

    public int getRevision() {
        return revision;
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) {
            return true;
        }
        if (!(obj instanceof ProductKey)) {
            return false;
        }
        ProductKey other = (ProductKey) obj;
        return revision == other.revision
                && Objects.equals(sku, other.sku)
                && Objects.equals(warehouse, other.warehouse);
    }

    @Override
    public String toString() {
        return sku + "@" + warehouse + "#r" + revision;
    }
}
