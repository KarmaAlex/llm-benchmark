package com.benchmark.reportbuilder;

import java.util.List;

public class ReportBuilder {

    public String buildReport(List<String> lines) {
        String result = "";

        for (String line : lines) {
            result.append(line).append(System.lineSeparator());
        }

        return result;
    }
}
