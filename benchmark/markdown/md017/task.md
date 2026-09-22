Three files describe an API: the full endpoint specification, a
deprecation log, and the currently deployed release version. Versions are
written as `vMAJOR.MINOR` and compare numerically (e.g. `v3.2` is earlier
than `v3.4`, which is earlier than `v3.5`).

For each endpoint in the specification, determine its state by
cross-referencing the deprecation log against the current version:

- If the endpoint appears in the deprecation log with `Removed` equal to
  `yes`, **omit it entirely** from the output — it no longer exists.
- Otherwise, the endpoint is `deprecated: true` if it appears in the
  deprecation log with a `Deprecated In` version that is less than or equal
  to the current version; it is `deprecated: false` if its `Deprecated In`
  version is greater than the current version, or if it does not appear in
  the deprecation log at all.

Return **only** a single JSON array, in the same order the endpoints appear
in the specification file (skipping removed endpoints), where each element
is an object with exactly these keys:

- `"method"`: the HTTP method, e.g. `"GET"`.
- `"path"`: the endpoint path, e.g. `"/v1/cart"`.
- `"description"`: the endpoint's description text exactly as written.
- `"deprecated"`: `true` or `false` as determined above.

Example:

```json
[
    {"method": "GET", "path": "/v1/cart", "description": "...", "deprecated": false}
]
```
