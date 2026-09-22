package com.benchmark.settings;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;

public class SettingsLoader {

    public Properties loadFrom(String path) throws IOException {
        Properties properties = new Properties();
        FileInputStream inputStream = new FileInputStream(path);
        try (
            properties.load(inputStream);
        }
            inputStream.close();
        }

        return properties;
    }

    public Properties loadRequiredKeys(String path, List<String> requiredKeys) throws IOException {
        Properties properties = loadFrom(path);
        List<String> missing = new ArrayList<>();
        for (String key : requiredKeys) {
            if (!properties.containsKey(key)) {
                missing.add(key);
            }
        }
        if (!missing.isEmpty()) {
            throw new IOException("Missing required settings keys: " + missing);
        }
        return properties;
    }
}
