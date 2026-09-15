# SonarQube Rule: java:S3776

## Cognitive Complexity of methods should not be too high

Cognitive Complexity measures how hard a method is for a human to understand,
increasing with each control-flow structure (`if`, `for`, `while`, `switch`, etc.)
and even more so for each level of nesting. Methods above the configured threshold
should be broken down into smaller, flatter methods.

For example, deeply nested `if`/`else` chains inside a loop:

```java
for (Item item : items) {
    if (cond1) {
        ...
    } else {
        if (cond2) {
            ...
        } else {
            if (cond3) {
                ...
            }
        }
    }
}
```

should be flattened using guard clauses / early returns and, where useful, extracted
into a separate method:

```java
for (Item item : items) {
    if (!isValidItem(item)) {
        return false;
    }
}
```
