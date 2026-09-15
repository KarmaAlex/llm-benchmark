# SonarQube Rule: java:S1481

## Unused local variables should be removed

A local variable that is declared but never used clutters the code and often signals
an incomplete change or a mistake (e.g. the variable was meant to be used but the code
that would have read it was removed or never written).

For example:

```java
public void process() {
    int unused = computeValue(); // never read
    doSomethingElse();
}
```

should be written as:

```java
public void process() {
    doSomethingElse();
}
```

(If `computeValue()` has a needed side effect, keep the call but drop the assignment.)
