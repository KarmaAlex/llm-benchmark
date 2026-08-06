Extract every Markdown heading from the document.

Return **only** a JSON array.

Each element must have the following structure:

```json
{
    "level": 1,
    "text": "Heading"
}
```