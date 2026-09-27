# SonarQube Rule: java:S3655

## Optional value should only be accessed after calling isPresent()

Calling `.get()` on an `Optional` without checking `isPresent()` (or using a safer
accessor) defeats the entire purpose of `Optional`: it throws a `NoSuchElementException`
whenever the value is absent, so it behaves no better than a raw `null` dereference.

Note that a method's return type does not always make it obvious that `Optional` is
involved at every call site — check the declaration of the method being called.

For example, given:

```java
public Optional<Account> findByNumber(String number) { ... }
```

this call site is noncompliant:

```java
return accountRepository.findByNumber(number).get().getBalance();
```

Handle the absent case explicitly instead, in whatever way the method's contract
requires - for example by checking `isPresent()`, or by using `map` together with
`orElse`, `orElseGet` or `orElseThrow`:

```java
Optional<Account> account = accountRepository.findByNumber(number);
if (account.isPresent()) {
    return account.get().getBalance();
}
// handle the missing account as the method's contract requires
```
