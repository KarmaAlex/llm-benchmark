package com.benchmark.reportgen;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class ReportGeneratorTest {

    private final ReportGenerator generator = new ReportGenerator();

    @Test
    void reportIncludesComputedFinancialAndPayrollFigures() {
        String report = generator.generateFullReport(
                "Acme Corp",
                List.of(100.0, 200.0, 300.0),
                List.of(50.0, 50.0),
                List.of("Alice", "Bob"),
                List.of(1000.0, 2000.0));

        assertTrue(report.contains("Annual Report for Acme Corp"));
        assertTrue(report.contains("Total Revenue: 600.0"));
        assertTrue(report.contains("Total Expenses: 100.0"));
        assertTrue(report.contains("Net Income: 500.0"));
        assertTrue(report.contains("Highest Monthly Revenue: 300.0"));
        assertTrue(report.contains("Lowest Monthly Revenue: 100.0"));
        assertTrue(report.contains("Employee Count: 2"));
        assertTrue(report.contains("Total Salaries: 3000.0"));
        assertTrue(report.contains("Average Salary: 1500.0"));
        assertTrue(report.contains("- Alice: 1000.0"));
        assertTrue(report.contains("- Bob: 2000.0"));
    }

    @Test
    void reportHandlesNoEmployeesWithoutDivideByZero() {
        String report = generator.generateFullReport(
                "Acme Corp",
                List.of(100.0),
                List.of(0.0),
                List.of(),
                List.of());

        assertTrue(report.contains("Employee Count: 0"));
        assertTrue(report.contains("Average Salary: 0.0"));
    }
}
