package com.benchmark.reportbuilder;

import java.util.List;

public class ReportBuilder {

    public String buildReport(List<String> lines) {
        String result = "";

        for (String line : lines) {
            result += line + System.lineSeparator();
        }

        return result;
    }
}
