Four files are Q3 2026 OKR documents, one per team. Each team reports the
progress of its key results in a different format:

- Sales: `<description> — <current>/<target>`
- Marketing: `<description>. Current: <current>. Target: <target>.`
- Engineering: `<description> — completed <current> of <target>.`
- Support: a table with `Key Result`, `Current`, and `Target` columns.

Normalize every key result across all four files into one flat JSON array.
Each element must be an object with exactly these keys:

- `"team"`: the team name (the text before `" — Q3 2026 OKRs"` in the
  file's title, e.g. `"Sales Team"`).
- `"objective"`: the objective text (after `"Objective: "`).
- `"key_result"`: the key result's descriptive text only — everything up
  to (but not including) wherever its current/target figures begin (the
  em dash, `"Current:"`, `"completed"`, or the table's `Current` column),
  with any trailing period, colon, or whitespace trimmed.
- `"current"`: the current value as a JSON integer.
- `"target"`: the target value as a JSON integer.
- `"percent_complete"`: `round(current / target * 100)` as a JSON integer.

Sort the array by `"team"` alphabetically, then by the order each
objective appears within that team's document.

Example (not the real values):

```json
[
    {
        "team": "Sales Team",
        "objective": "...",
        "key_result": "...",
        "current": 10,
        "target": 20,
        "percent_complete": 50
    }
]
```
