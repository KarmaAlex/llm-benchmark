# SonarQube Rule: java:S2789

## "Optional" value should only be accessed after confirming it contains a value

Calling `.get()` on an `Optional` without checking `isPresent()` (or using a safer
accessor) defeats the entire purpose of `Optional`: it throws a `NoSuchElementException`
whenever the value is absent, so it behaves no better than a raw `null` dereference.

Note that a method's return type does not always make it obvious that `Optional` is
involved at every call site — check the declaration of the method being called.

For example, given:

```java
public Optional<User> findById(long id) { ... }
```

this call site:

```java
return userRepository.findById(id).get().getEmail();
```

should be written as:

```java
return userRepository.findById(id)
        .map(User::getEmail)
        .orElseThrow(() -> new NoSuchElementException("No user with id " + id));
```
