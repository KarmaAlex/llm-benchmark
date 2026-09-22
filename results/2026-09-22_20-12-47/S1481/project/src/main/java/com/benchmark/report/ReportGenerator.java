package com.benchmark.report;

import java.time.LocalDate;

public class ReportGenerator {

    public String generateSummary(String title, int itemCount) {
        String generatedOn = LocalDate.now().toString();
        StringBuilder builder = new StringBuilder();

        builder.append(title);
        builder.append(" - ");
        builder.append(formatItemCount(itemCount));

        return builder.toString();
    }

    private String formatItemCount(int itemCount) {
        if (itemCount == 0) {
            return "no items";
        }
        if (itemCount == 1) {
            return "1 item";
        }
        return itemCount + " items";
    }
}
