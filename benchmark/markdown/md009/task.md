The document contains multiple tables, each under its own heading ("Revenue",
"Customer Retention", "Support Metrics"). The "Summary" section at the end contains
no table and must be ignored.

Return **only** a single JSON object keyed by section heading (exactly as written).
Each value must be an array of row objects for that section's table, using the
table's header row to derive the JSON keys, converted to snake_case, lowercase, with
no special characters (e.g. "Q1 Revenue ($K)" becomes "q1_revenue_k"). Keep every
cell value as a string exactly as written in the table.

For example:

```json
{
    "Revenue": [
        {
            "product_line": "Core Platform",
            "q1_revenue_k": "4200",
            "yoy_growth": "12%"
        }
    ]
}
```
