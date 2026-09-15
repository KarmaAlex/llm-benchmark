# SonarQube Rule: java:S2637

## "@NonNull" values should not be set to null

A field, parameter, or return value marked with a "non-null" annotation is a contract:
callers and readers are told it will never be null. Assigning `null` to such a value
breaks that contract and defeats the purpose of the annotation.

For example:

```java
@NonNull
private String email;

public void reset() {
    this.email = null; // breaks the @NonNull contract
}
```

should either avoid the null assignment (e.g. reset to a safe default) or the field
should not be annotated `@NonNull` if it legitimately needs to hold null:

```java
public void reset() {
    this.email = "";
}
```
