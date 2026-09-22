package com.benchmark.access;

public class AccessController {

    public boolean canEditDocument(User user, Document document) {
if (user.isActive() && user.hasPermission("EDIT")) {
    return !document.isLocked();
}        }

        return false;
    }
}
