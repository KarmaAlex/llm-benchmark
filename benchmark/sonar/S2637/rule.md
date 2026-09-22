# SonarQube Rule: java:S2637

## "@Nonnull" values should not be set to null

A field, parameter, or return value marked with a "non-null" annotation (such as
`javax.annotation.Nonnull`) is a contract: callers and readers are told it will never
be null. Leaving such a field uninitialized in a constructor, or explicitly assigning
it `null`, breaks that contract and defeats the purpose of the annotation.

For example:

```java
@Nonnull
private String email;

public CustomerProfile() {
    // email is never assigned here, so it stays null despite the @Nonnull contract
}

public CustomerProfile(String email) {
    this.email = email;
}
```

should ensure every constructor establishes a non-null value for the field, e.g. by
delegating to the constructor that requires one:

```java
public CustomerProfile() {
    this("");
}

public CustomerProfile(String email) {
    this.email = email;
}
```
