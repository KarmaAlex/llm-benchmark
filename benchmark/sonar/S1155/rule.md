# SonarQube Rule: java:S1155

## Collection.isEmpty() should be used to test for emptiness

Testing `collection.size() == 0` to check whether a collection is empty works, but
`collection.isEmpty()` communicates the intent more clearly and can be more efficient
for some collection implementations.

For example:

```java
if (items.size() == 0) {
    ...
}
```

should be written as:

```java
if (items.isEmpty()) {
    ...
}
```
