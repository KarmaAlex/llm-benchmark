# SonarQube Rule: java:S1206

## "equals(Object obj)" and "hashCode()" should be overridden in pairs

`equals()` and `hashCode()` form a contract: two objects that are equal must return
the same hash code. Overriding only `equals()` leaves the inherited `Object.hashCode()`
in place, which is based on identity, so two equal instances almost always hash
differently. Such objects behave incorrectly in every hash-based collection -
`HashSet` stores duplicates, and `HashMap.get()` fails to find entries that were
stored under an equal key.

For example, a class that compares its fields in `equals()`:

```java
@Override
public boolean equals(Object obj) {
    if (this == obj) {
        return true;
    }
    if (!(obj instanceof ProductKey)) {
        return false;
    }
    ProductKey other = (ProductKey) obj;
    return revision == other.revision
            && Objects.equals(sku, other.sku)
            && Objects.equals(warehouse, other.warehouse);
}
```

must also override `hashCode()` over exactly the same fields:

```java
@Override
public int hashCode() {
    return Objects.hash(sku, warehouse, revision);
}
```
