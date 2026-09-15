# SonarQube Rule: java:S1854

## Dead stores should be removed

A value assigned to a variable that is never subsequently read, either because it is
overwritten before use or because the variable goes out of scope, is a "dead store".
Dead stores are useless and often indicate a mistake such as a missing branch or a
leftover from earlier refactoring.

For example:

```java
int discount = 5;
discount = computeDiscount(); // the previous assignment is never read
```

should be written as:

```java
int discount = computeDiscount();
```
