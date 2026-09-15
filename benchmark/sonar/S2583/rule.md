# SonarQube Rule: java:S2583

## Conditions should not unconditionally evaluate to "true" or "false"

Some conditions never evaluate to `true` or `false` at runtime, given the values the
operands can take. Having conditions that are always false or always true is problematic,
since the associated branch is dead code and likely does not reflect the developer's intent.

For example:

```java
boolean enabled = false;
if (enabled) { // always false
    doSomething();
}
```

A common fix is to source the value dynamically instead of hardcoding it, e.g. accept
it as a parameter or read it from configuration:

```java
public void process(boolean enabled) {
    if (enabled) {
        doSomething();
    }
}
```
