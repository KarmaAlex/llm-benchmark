# SonarQube Rule: java:S1066

## Collapsible "if" statements should be merged

Merging collapsible `if` statements increases the code's readability.

For example:

```java
if (condition1) {
    if (condition2) {
        doSomething();
    }
}
```

should be written as:

```java
if (condition1 && condition2) {
    doSomething();
}
```
