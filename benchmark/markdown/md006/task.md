Extract every fenced code block from the document, in the order they appear.

Return **only** a JSON array.

Each element must have the following structure:

```json
{
    "language": "bash",
    "code": "the exact code inside the fence"
}
```

If a code fence has no language tag, set "language" to `null`. Preserve the code
exactly as written, without a trailing newline.
