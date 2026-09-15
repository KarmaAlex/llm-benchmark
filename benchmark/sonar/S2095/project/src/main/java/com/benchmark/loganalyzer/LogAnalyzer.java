package com.benchmark.loganalyzer;

import java.io.IOException;
import java.util.List;

public class LogAnalyzer {

    public long countErrorLines(String logPath) throws IOException {
        LogFileReader reader = new LogFileReader(logPath);
        List<String> lines = reader.readAllLines();

        return lines.stream()
                .filter(line -> line.contains("ERROR"))
                .count();
    }
}
