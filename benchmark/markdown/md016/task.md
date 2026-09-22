Three files are weekly status reports from different teams. Each has a
title heading of the form `"<Team Name> — Weekly Status"`, a `**Project:**`
line, a `**Status:**` line, and a section listing open concerns — but that
section is titled differently in each file (`Blockers`, `Risks`, or
`Issues`). In every case it means the same thing: a list of items blocking
or threatening the project.

Return **only** a single JSON object keyed by team name (the text before
`" — Weekly Status"` in each file's title, e.g. `"Platform Team"`). Each
value must be an object with exactly these keys:

- `"project"`: the project name.
- `"status"`: the status value, exactly as written.
- `"blockers"`: an array of strings, one per item in that team's
  concerns section (regardless of what that section is titled), in the
  order they appear.

Example structure (not the real values):

```json
{
    "Platform Team": {
        "project": "...",
        "status": "...",
        "blockers": ["..."]
    }
}
```
