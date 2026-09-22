package com.benchmark.loganalyzer;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class LogAnalyzerTest {

    private final LogAnalyzer analyzer = new LogAnalyzer();

    @Test
    void countsOnlyLinesContainingError(@TempDir Path tempDir) throws IOException {
        Path logFile = tempDir.resolve("app.log");
        Files.writeString(logFile, "INFO starting up\nERROR disk full\nINFO done\nERROR timeout\n");

        assertEquals(2, analyzer.countErrorLines(logFile.toString()));
    }

    @Test
    void returnsZeroWhenNoErrorLinesPresent(@TempDir Path tempDir) throws IOException {
        Path logFile = tempDir.resolve("app.log");
        Files.writeString(logFile, "INFO starting up\nINFO done\n");

        assertEquals(0, analyzer.countErrorLines(logFile.toString()));
    }

    @Test
    void canAnalyzeTheSameFileRepeatedlyWithoutExhaustingHandles(@TempDir Path tempDir) throws IOException {
        Path logFile = tempDir.resolve("app.log");
        Files.writeString(logFile, "ERROR one\nINFO two\n");

        for (int i = 0; i < 50; i++) {
            assertEquals(1, analyzer.countErrorLines(logFile.toString()));
        }
    }
}
