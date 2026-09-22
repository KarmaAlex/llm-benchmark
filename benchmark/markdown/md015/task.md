One file is an incident timeline (a list of timestamped events), the other
is a service metrics log (a table of timestamped measurements). The metrics
log contains more rows than there are timeline events — only use the rows
whose timestamp exactly matches a timeline event.

Return **only** a single JSON array, one element per timeline event, in the
same order the events appear in the timeline document. Each element must be
an object with exactly these keys:

- `"time"`: the event's timestamp exactly as written (e.g. `"14:02"`).
- `"event"`: the event description text exactly as written, excluding the
  leading timestamp.
- `"error_rate_pct"`: the matching metrics row's `Error Rate (%)` value, as
  a JSON number.
- `"latency_ms"`: the matching metrics row's `Latency (ms)` value, as a
  JSON integer.

Example:

```json
[
    {"time": "14:02", "event": "...", "error_rate_pct": 4.8, "latency_ms": 340}
]
```
