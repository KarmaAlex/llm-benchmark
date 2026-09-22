Two files describe the on-call rotation for Q3 2026: one for the primary
track, one for the secondary (backup) track.

Return **only** a single JSON array containing every scheduled week from
both files, merged together and sorted in ascending chronological order by
week start date. Each element must be an object with exactly these keys:

- `"week_starting"`: the date exactly as written in the source document
  (e.g. `"2026-07-06"`).
- `"engineer"`: the assigned engineer's full name.
- `"track"`: `"primary"` or `"secondary"`, depending on which document the
  entry came from.

Example:

```json
[
    {"week_starting": "2026-07-06", "engineer": "Elena Cho", "track": "primary"}
]
```
