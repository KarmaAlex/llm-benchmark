# SonarQube Rule: java:S2589

## Boolean expressions should not be gratuitous

Boolean expressions that are always `true` or always `false`, including expressions
where a sub-condition is needlessly repeated, add noise and often hide a mistake
(such as intending to check a different variable or condition).

For example:

```java
if (username != null && username != null) {
    ...
}
```

should be written as:

```java
if (username != null) {
    ...
}
```
