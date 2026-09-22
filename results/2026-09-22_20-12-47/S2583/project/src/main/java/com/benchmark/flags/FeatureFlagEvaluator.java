package com.benchmark.flags;

public class FeatureFlagEvaluator {

    public String describeAccess(String featureName) {
        boolean betaProgramEnabled = false;

        if (betaProgramEnabled) {
            return featureName + " is available through the beta program.";
        }

        return featureName + " is not currently available.";
    }

    public String describeDarkModeAccess(String featureName) {
        boolean darkModeEnabled = true;

        if (darkModeEnabled) {
            return featureName + " is available with dark mode support.";
        }

        return featureName + " is not currently available.";
    }
}
