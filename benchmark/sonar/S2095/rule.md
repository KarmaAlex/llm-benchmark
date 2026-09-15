# SonarQube Rule: java:S2095

## Resources should be closed

Connections, streams, files, and other classes that implement `Closeable` or
`AutoCloseable` hold onto operating system resources. If they are not closed, those
resources leak, which can eventually exhaust file handles, sockets, or memory.

Note that a class may implement `AutoCloseable` even though that isn't obvious from
how it's used at the call site — check the class declaration.

For example, given:

```java
public class LogFileReader implements AutoCloseable { ... }
```

this call site:

```java
LogFileReader reader = new LogFileReader(logPath);
List<String> lines = reader.readAllLines();
```

should be written using try-with-resources so the resource is always closed, even if
an exception is thrown:

```java
try (LogFileReader reader = new LogFileReader(logPath)) {
    List<String> lines = reader.readAllLines();
    ...
}
```
