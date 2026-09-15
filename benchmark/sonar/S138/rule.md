# SonarQube Rule: java:S138

## Functions and methods should not have too many lines

A method with a large number of lines is hard to understand, test, and maintain,
and is usually a sign that it's doing more than one job. Long methods should be
split into smaller methods, each with a single, clear responsibility.

For example, a single method that computes multiple unrelated statistics and
renders multiple report sections:

```java
public String generateFullReport(...) {
    // compute totals
    // compute min/max
    // compute payroll
    // render each section
    ...
}
```

should be split into focused helper methods:

```java
public String generateFullReport(...) {
    StringBuilder report = new StringBuilder();
    appendHeader(report, companyName);
    appendFinancialSummary(report, revenues, expenses);
    appendRevenueBreakdown(report, revenues);
    appendPayrollSummary(report, employeeNames, employeeSalaries);
    appendEmployeeListing(report, employeeNames, employeeSalaries);
    appendFooter(report);
    return report.toString();
}
```
