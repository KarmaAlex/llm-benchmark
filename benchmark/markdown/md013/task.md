One file is a product catalog, the other lists inventory quantities per
warehouse. A SKU may appear in multiple warehouses in the inventory file.

For every SKU in the product catalog, return **only** a single JSON array
of objects with exactly these keys, sorted in ascending order by `sku`:

- `"sku"`: the SKU exactly as written.
- `"product_name"`: from the catalog.
- `"category"`: from the catalog.
- `"total_quantity"`: an integer equal to the sum of `Quantity On Hand`
  across every warehouse row for that SKU in the inventory file.
- `"warehouses"`: an array of `{"warehouse": "...", "quantity": <int>}`
  objects, one per warehouse row for that SKU, in the same order those rows
  appear in the inventory file.

Example:

```json
[
    {
        "sku": "SKU-100",
        "product_name": "Wireless Mouse",
        "category": "Peripherals",
        "total_quantity": 165,
        "warehouses": [
            {"warehouse": "West", "quantity": 120},
            {"warehouse": "East", "quantity": 45}
        ]
    }
]
```
