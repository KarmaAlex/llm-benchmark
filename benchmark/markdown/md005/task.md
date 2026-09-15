Extract the "Departmental Headcount" table into an array of row objects.

Return **only** a JSON array.

Use the table's header row to derive the JSON keys, converted to snake_case,
lowercase, with no special characters. Numeric values (headcount, open requisitions)
must be JSON numbers, not strings. The attrition rate must stay a string exactly as
written in the table (including the "%" sign).

Each element must have the following structure:

```json
{
    "department": "Engineering",
    "headcount": 142,
    "open_requisitions": 12,
    "attrition_rate": "4.2%"
}
```
