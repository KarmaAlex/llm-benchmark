package com.benchmark.config;

import java.util.Map;

public class ConfigLoader {

    public String getRequiredSetting(Map<String, String> settings, String key) {
        try {
            return settings.get(key).trim();
        } catch (NullPointerException e) {
            return "";
        }
    }
}
