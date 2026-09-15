Extract every entry from the "Decisions" section into structured data. Each entry is
written as free text in the form "Decision: ..., Owner: ..., Due: ...".

Return **only** a JSON array.

Each element must have the following structure:

```json
{
    "decision": "Adopt Kafka as the standard event bus for new services.",
    "owner": "Ravi Chandran",
    "due": "2026-05-01"
}
```

The "decision" field must contain only the decision text (including its trailing
period), without the "Decision:", "Owner:", or "Due:" labels.
