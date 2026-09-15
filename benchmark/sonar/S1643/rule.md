# SonarQube Rule: java:S1643

## Strings should not be concatenated using '+' in a loop

Since `String` is immutable in Java, using `+` or `+=` to build up a string inside a
loop allocates a new `String` object on every iteration and copies all previously
accumulated characters into it, making the loop quadratic in the number of iterations.
`StringBuilder` should be used instead.

For example:

```java
String result = "";
for (String line : lines) {
    result += line;
}
```

should be written as:

```java
StringBuilder result = new StringBuilder();
for (String line : lines) {
    result.append(line);
}
```
