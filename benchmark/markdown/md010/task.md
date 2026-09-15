This document is an incident postmortem containing three different kinds of
information: its heading structure, an action-item checklist, and a decision log.

Return **only** a single JSON object with exactly these three keys:

- `"summary_headings"`: every heading in the document, in order, as a flat array of
  `{"level": 1, "text": "..."}` objects (same shape as a flat heading extraction).
- `"action_items"`: every entry from the "Action Items" checklist, as an array of
  `{"text": "...", "done": true}` objects (`done` is `true` for `[x]`, `false` for `[ ]`).
- `"decisions"`: every entry from the "Decisions" section, as an array of
  `{"decision": "...", "owner": "...", "due": "..."}` objects, where "decision" is
  only the decision text (no "Decision:"/"Owner:"/"Due:" labels).

Example structure (not the real values):

```json
{
    "summary_headings": [
        {"level": 1, "text": "Postmortem: Checkout Service Outage — 2026-06-11"}
    ],
    "action_items": [
        {"text": "Roll back the faulty deploy", "done": true}
    ],
    "decisions": [
        {"decision": "...", "owner": "...", "due": "..."}
    ]
}
```
