# SonarQube Rule: java:S1192

## String literals should not be duplicated

Duplicated string literals make maintenance more difficult: if the text needs to
change, every occurrence has to be found and updated consistently, which is
error-prone. Repeated literals should be extracted into a single named constant.

For example:

```java
return "Thank you for your order, " + name + "! We will notify you when it ships.";
...
return "Thank you for your order, " + name + "! Your package is on its way.";
...
return "Thank you for your order, " + name + "! Unfortunately it was cancelled.";
```

should be written as:

```java
private static final String ORDER_GREETING = "Thank you for your order, ";

return ORDER_GREETING + name + "! We will notify you when it ships.";
...
return ORDER_GREETING + name + "! Your package is on its way.";
...
return ORDER_GREETING + name + "! Unfortunately it was cancelled.";
```
