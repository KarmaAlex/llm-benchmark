# SonarQube Rule: java:S3516

## Function returns should not be invariant

When a function's logic is capable of producing different results based on input, but
every code path actually returns the exact same value, the branching is either dead
code or a bug (usually a copy-paste mistake where a value was meant to differ per branch).

For example:

```java
public double rate(String tier) {
    if (tier.equals("GOLD")) {
        return 0.20;
    } else if (tier.equals("SILVER")) {
        return 0.20;
    }
    return 0.20;
}
```

should instead use the value that was actually intended for each branch:

```java
public double rate(String tier) {
    if (tier.equals("GOLD")) {
        return 0.20;
    } else if (tier.equals("SILVER")) {
        return 0.10;
    }
    return 0.0;
}
```
