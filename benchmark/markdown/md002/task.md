Extract every action item from the "Action Items" checklist in the document.

Return **only** a JSON array.

Each element must have the following structure:

```json
{
    "text": "Finalize the retry-policy design doc",
    "done": true
}
```

"done" must be `true` for items checked with `[x]` and `false` for items checked with `[ ]`.
