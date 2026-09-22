package com.benchmark.flags;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class FeatureFlagEvaluatorTest {

    private final FeatureFlagEvaluator evaluator = new FeatureFlagEvaluator();

    @Test
    void betaProgramIsNotCurrentlyAvailable() {
        assertEquals(
                "widgets is not currently available.",
                evaluator.describeAccess("widgets"));
    }

    @Test
    void darkModeIsAvailable() {
        assertEquals(
                "widgets is available with dark mode support.",
                evaluator.describeDarkModeAccess("widgets"));
    }
}
