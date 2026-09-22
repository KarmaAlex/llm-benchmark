# SonarQube Rule: java:S1181

## Throwable and Error should not be caught

`Error` and its subclasses represent conditions the JVM raises when it is no longer
in a recoverable state, such as `StackOverflowError` or `OutOfMemoryError`. Catching
`Throwable` also catches those, so a handler intended for ordinary failures silently
swallows unrecoverable JVM errors and lets the program limp on in a broken state.

Only `Exception` (or a more specific type) should be caught.

For example:

```java
try {
    return task.execute();
} catch (Throwable t) {
    return "failed: " + t.getMessage();
}
```

should be written as:

```java
try {
    return task.execute();
} catch (Exception e) {
    return "failed: " + e.getMessage();
}
```
