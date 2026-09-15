package com.benchmark.reportgen;

import java.util.List;

public class ReportGenerator {

    public String generateFullReport(String companyName, List<Double> revenues, List<Double> expenses,
                                      List<String> employeeNames, List<Double> employeeSalaries) {
        StringBuilder report = new StringBuilder();

        report.append("=====================================\n");
        report.append("Annual Report for ").append(companyName).append("\n");
        report.append("=====================================\n\n");

        double totalRevenue = 0;
        for (Double revenue : revenues) {
            totalRevenue += revenue;
        }

        double totalExpenses = 0;
        for (Double expense : expenses) {
            totalExpenses += expense;
        }

        double netIncome = totalRevenue - totalExpenses;

        report.append("Financial Summary\n");
        report.append("-----------------\n");
        report.append("Total Revenue: ").append(totalRevenue).append("\n");
        report.append("Total Expenses: ").append(totalExpenses).append("\n");
        report.append("Net Income: ").append(netIncome).append("\n\n");

        double highestRevenue = Double.MIN_VALUE;
        double lowestRevenue = Double.MAX_VALUE;
        for (Double revenue : revenues) {
            if (revenue > highestRevenue) {
                highestRevenue = revenue;
            }
            if (revenue < lowestRevenue) {
                lowestRevenue = revenue;
            }
        }

        report.append("Revenue Breakdown\n");
        report.append("-----------------\n");
        report.append("Highest Monthly Revenue: ").append(highestRevenue).append("\n");
        report.append("Lowest Monthly Revenue: ").append(lowestRevenue).append("\n\n");

        double totalSalaries = 0;
        for (Double salary : employeeSalaries) {
            totalSalaries += salary;
        }
        double averageSalary = employeeNames.isEmpty() ? 0 : totalSalaries / employeeNames.size();

        report.append("Payroll Summary\n");
        report.append("---------------\n");
        report.append("Employee Count: ").append(employeeNames.size()).append("\n");
        report.append("Total Salaries: ").append(totalSalaries).append("\n");
        report.append("Average Salary: ").append(averageSalary).append("\n\n");

        report.append("Employee Listing\n");
        report.append("----------------\n");
        for (int i = 0; i < employeeNames.size(); i++) {
            report.append("- ").append(employeeNames.get(i))
                    .append(": ").append(employeeSalaries.get(i)).append("\n");
        }

        report.append("\n=====================================\n");
        report.append("End of Report\n");
        report.append("=====================================\n");

        return report.toString();
    }
}
