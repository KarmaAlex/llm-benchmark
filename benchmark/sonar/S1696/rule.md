# SonarQube Rule: java:S1696

## "NullPointerException" should not be caught

Catching `NullPointerException` is a way to mask a bug rather than fix it: it hides
the actual location and cause of the null dereference, and can also silently swallow
unrelated null pointer errors that happen to occur in the same try block. Code should
check for null explicitly instead of relying on catching the exception.

For example:

```java
try {
    return settings.get(key).trim();
} catch (NullPointerException e) {
    return "";
}
```

should be written as:

```java
String value = settings.get(key);
return value != null ? value.trim() : "";
```
