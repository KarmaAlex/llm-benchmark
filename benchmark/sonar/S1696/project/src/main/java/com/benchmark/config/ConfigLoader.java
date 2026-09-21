package com.benchmark.config;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class ConfigLoader {

    public String getRequiredSetting(Map<String, String> settings, String key) {
        try {
            return settings.get(key).trim();
        } catch (NullPointerException e) {
            return "";
        }
    }

    public String getOptionalSetting(Map<String, String> settings, String key, String defaultValue) {
        String value = settings.get(key);
        return value != null ? value.trim() : defaultValue;
    }

    public void requireAll(Map<String, String> settings, List<String> requiredKeys) {
        List<String> missing = new ArrayList<>();
        for (String key : requiredKeys) {
            if (settings.get(key) == null) {
                missing.add(key);
            }
        }
        if (!missing.isEmpty()) {
            throw new IllegalStateException("Missing required settings: " + missing);
        }
    }
}
