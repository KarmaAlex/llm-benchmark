# SonarQube Rule: java:S1125

## Redundant boolean literals

Boolean expressions should not be unnecessarily compared with `true` or `false`.

For example:

```java
if (dog.isWhite() == true) {
    ...
}
```

should be written as:

```Java
if (dog.isWhite()) {
    ...
}
```