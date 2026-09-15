# SonarQube Rule: java:S2093

## Try-with-resources should be used

Manually closing a resource in a `finally` block is verbose and error-prone (it's easy
to forget, or to have the `close()` call itself throw and mask the original exception).
Try-with-resources handles all of this automatically.

For example:

```java
FileInputStream inputStream = new FileInputStream(path);
try {
    properties.load(inputStream);
} finally {
    inputStream.close();
}
```

should be written as:

```java
try (FileInputStream inputStream = new FileInputStream(path)) {
    properties.load(inputStream);
}
```
