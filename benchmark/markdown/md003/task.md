Extract the document metadata block that appears right after the title (the lines of
the form "Key: Value", before the "Background" section).

Return **only** a single JSON object.

Use these exact keys: "document_id", "owner", "sponsor", "status", "start_date", "target_end_date".

For example:

```json
{
    "document_id": "PC-2026-0091",
    "owner": "Marcus Webb",
    "sponsor": "VP Engineering",
    "status": "Approved",
    "start_date": "2026-03-02",
    "target_end_date": "2026-08-28"
}
```
