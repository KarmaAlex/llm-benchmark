package com.benchmark.settings;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.Properties;

public class SettingsLoader {

    public Properties loadFrom(String path) throws IOException {
        Properties properties = new Properties();
        FileInputStream inputStream = new FileInputStream(path);
        try {
            properties.load(inputStream);
        } finally {
            inputStream.close();
        }

        return properties;
    }
}
