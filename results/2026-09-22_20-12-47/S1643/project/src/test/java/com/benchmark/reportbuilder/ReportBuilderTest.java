package com.benchmark.reportbuilder;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import org.junit.jupiter.api.Test;

class ReportBuilderTest {

    private final ReportBuilder builder = new ReportBuilder();

    @Test
    void emptyListProducesEmptyReport() {
        assertEquals("", builder.buildReport(List.of()));
    }

    @Test
    void singleLineIsFollowedByLineSeparator() {
        assertEquals("first" + System.lineSeparator(), builder.buildReport(List.of("first")));
    }

    @Test
    void multipleLinesAreEachTerminated() {
        String expected = "first" + System.lineSeparator() + "second" + System.lineSeparator();

        assertEquals(expected, builder.buildReport(List.of("first", "second")));
    }
}
