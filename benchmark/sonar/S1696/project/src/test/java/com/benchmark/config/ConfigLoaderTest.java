package com.benchmark.config;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class ConfigLoaderTest {

    private final ConfigLoader loader = new ConfigLoader();

    @Test
    void requiredSettingIsTrimmedWhenPresent() {
        Map<String, String> settings = Map.of("host", "  localhost  ");

        assertEquals("localhost", loader.getRequiredSetting(settings, "host"));
    }

    @Test
    void requiredSettingIsEmptyWhenMissing() {
        Map<String, String> settings = Map.of();

        assertEquals("", loader.getRequiredSetting(settings, "host"));
    }

    @Test
    void optionalSettingFallsBackToDefault() {
        Map<String, String> settings = Map.of();

        assertEquals("8080", loader.getOptionalSetting(settings, "port", "8080"));
    }

    @Test
    void optionalSettingReturnsTrimmedValueWhenPresent() {
        Map<String, String> settings = Map.of("port", " 9090 ");

        assertEquals("9090", loader.getOptionalSetting(settings, "port", "8080"));
    }

    @Test
    void requireAllPassesWhenAllKeysPresent() {
        Map<String, String> settings = Map.of("host", "localhost", "port", "9090");

        loader.requireAll(settings, List.of("host", "port"));
    }

    @Test
    void requireAllThrowsWhenKeysMissing() {
        Map<String, String> settings = Map.of("host", "localhost");

        assertThrows(
                IllegalStateException.class,
                () -> loader.requireAll(settings, List.of("host", "port")));
    }
}
