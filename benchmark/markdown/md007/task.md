Extract the document's heading structure as a nested tree instead of a flat list.

Return **only** a JSON array containing the top-level headings (level 1). Each
heading must have this structure, with "children" containing any headings nested
directly beneath it (one level deeper), recursively:

```json
{
    "level": 1,
    "text": "Employee Handbook",
    "children": [
        {
            "level": 2,
            "text": "Getting Started",
            "children": []
        }
    ]
}
```

A heading with no subheadings underneath it must still include an empty "children" array.
