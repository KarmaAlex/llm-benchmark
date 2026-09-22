package com.benchmark.settings;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Properties;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class SettingsLoaderTest {

    private final SettingsLoader loader = new SettingsLoader();

    @Test
    void loadsPropertiesFromFile(@TempDir Path tempDir) throws IOException {
        Path file = tempDir.resolve("settings.properties");
        Files.writeString(file, "host=localhost\nport=9090\n");

        Properties properties = loader.loadFrom(file.toString());

        assertEquals("localhost", properties.getProperty("host"));
        assertEquals("9090", properties.getProperty("port"));
    }

    @Test
    void loadRequiredKeysSucceedsWhenAllPresent(@TempDir Path tempDir) throws IOException {
        Path file = tempDir.resolve("settings.properties");
        Files.writeString(file, "host=localhost\nport=9090\n");

        Properties properties = loader.loadRequiredKeys(file.toString(), List.of("host", "port"));

        assertEquals("localhost", properties.getProperty("host"));
    }

    @Test
    void loadRequiredKeysFailsWhenKeyMissing(@TempDir Path tempDir) throws IOException {
        Path file = tempDir.resolve("settings.properties");
        Files.writeString(file, "host=localhost\n");

        assertThrows(
                IOException.class,
                () -> loader.loadRequiredKeys(file.toString(), List.of("host", "port")));
    }
}
