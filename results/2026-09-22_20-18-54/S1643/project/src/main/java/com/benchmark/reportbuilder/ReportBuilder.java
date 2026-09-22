package com.benchmark.reportbuilder;

import java.util.List;

public class ReportBuilder {

    public String buildReport(List<String> lines) {
        StringBuilder result = new StringBuilder();

        for (String line : lines) {
            result.append(line).append(System.lineSeparator());
        }

        return result.toString();
    }
}
