package com.benchmark.report;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class ReportGeneratorTest {

    private final ReportGenerator generator = new ReportGenerator();

    @Test
    void noItemsIsDescribedExplicitly() {
        assertEquals("Weekly Digest - no items", generator.generateSummary("Weekly Digest", 0));
    }

    @Test
    void singleItemUsesSingularWording() {
        assertEquals("Weekly Digest - 1 item", generator.generateSummary("Weekly Digest", 1));
    }

    @Test
    void multipleItemsUsePluralWording() {
        assertEquals("Weekly Digest - 5 items", generator.generateSummary("Weekly Digest", 5));
    }
}
