package com.benchmark.access;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Set;
import org.junit.jupiter.api.Test;

class AccessControllerTest {

    private final AccessController controller = new AccessController();

    @Test
    void activeUserWithPermissionCanEditUnlockedDocument() {
        User user = new User(true, Set.of("EDIT"));
        Document document = new Document(false);

        assertTrue(controller.canEditDocument(user, document));
    }

    @Test
    void activeUserWithPermissionCannotEditLockedDocument() {
        User user = new User(true, Set.of("EDIT"));
        Document document = new Document(true);

        assertFalse(controller.canEditDocument(user, document));
    }

    @Test
    void activeUserWithoutPermissionCannotEdit() {
        User user = new User(true, Set.of("VIEW"));
        Document document = new Document(false);

        assertFalse(controller.canEditDocument(user, document));
    }

    @Test
    void inactiveUserCannotEditEvenWithPermission() {
        User user = new User(false, Set.of("EDIT"));
        Document document = new Document(false);

        assertFalse(controller.canEditDocument(user, document));
    }
}
