package com.benchmark.access;

import java.util.Set;

public class User {

    private final boolean active;
    private final Set<String> permissions;

    public User(boolean active, Set<String> permissions) {
        this.active = active;
        this.permissions = permissions;
    }

    public boolean isActive() {
        return active;
    }

    public boolean hasPermission(String permission) {
        return permissions.contains(permission);
    }
}
