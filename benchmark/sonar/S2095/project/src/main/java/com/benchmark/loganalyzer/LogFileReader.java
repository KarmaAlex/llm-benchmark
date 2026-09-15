package com.benchmark.loganalyzer;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

public class LogFileReader implements AutoCloseable {

    private final BufferedReader reader;

    public LogFileReader(String path) throws IOException {
        this.reader = new BufferedReader(new FileReader(path));
    }

    public List<String> readAllLines() throws IOException {
        List<String> lines = new ArrayList<>();
        String line;
        while ((line = reader.readLine()) != null) {
            lines.add(line);
        }
        return lines;
    }

    @Override
    public void close() throws IOException {
        reader.close();
    }
}
