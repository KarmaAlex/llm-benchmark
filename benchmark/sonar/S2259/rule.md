# java:S2259 — Null pointers should not be dereferenced

A `NullPointerException` can occur when a reference that may contain `null` is
dereferenced without first establishing that it is non-null.

A dereference includes, among other operations:

- Calling an instance method on a reference.
- Accessing an instance field.
- Accessing a member through a reference.
- Passing a potentially null reference to code that requires a non-null value.

When static analysis determines that a reference may be `null` at a particular
point in the execution, the code should not dereference that reference before
handling the null case.

For example, this code is unsafe:

```java
String name = user.getName();

if (user == null) {
    return;
}
```

The null check occurs after user has already been dereferenced. If user is
null, user.getName() throws a NullPointerException before the check can
execute.

The null check must occur before the dereference:
```java
if (user == null) {
    return;
}

String name = user.getName();
```