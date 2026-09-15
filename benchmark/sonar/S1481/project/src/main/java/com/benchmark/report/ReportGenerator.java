package com.benchmark.report;

import java.time.LocalDate;

public class ReportGenerator {

    public String generateSummary(String title, int itemCount) {
        LocalDate generatedOn = LocalDate.now();
        StringBuilder builder = new StringBuilder();

        builder.append(title);
        builder.append(" - ");
        builder.append(itemCount);
        builder.append(" items");

        return builder.toString();
    }
}
