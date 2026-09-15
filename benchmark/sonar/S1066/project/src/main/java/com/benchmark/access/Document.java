package com.benchmark.access;

public class Document {

    private final boolean locked;

    public Document(boolean locked) {
        this.locked = locked;
    }

    public boolean isLocked() {
        return locked;
    }
}
