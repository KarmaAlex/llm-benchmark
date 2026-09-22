One file is an employee directory table, the other is a badge access log
table. Both tables share an `Employee ID` column.

Join the two tables on `Employee ID` and return **only** a single JSON array
of the merged records, sorted in ascending order by `Employee ID`. Each
element must be an object with exactly these keys, all string values taken
verbatim from the source tables:

- `"employee_id"`
- `"name"`
- `"department"`
- `"badge_level"`
- `"last_access_date"`

Example:

```json
[
    {
        "employee_id": "E1001",
        "name": "Grace Liu",
        "department": "Engineering",
        "badge_level": "L3",
        "last_access_date": "2026-09-01"
    }
]
```
