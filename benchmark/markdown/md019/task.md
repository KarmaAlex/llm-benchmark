Four files together describe a set of requirements and their release
readiness: the requirements list, a design document stating which
requirements it covers, a test plan stating which requirements have test
cases, and a log of defects (each linked to a requirement, with a status of
`open` or `closed`).

For each requirement `REQ-1` through `REQ-5`, determine:

- `"has_design"`: `true` if the design document lists that requirement as
  covered, `false` otherwise.
- `"has_tests"`: `true` if the test plan lists that requirement as having
  test cases, `false` otherwise.
- `"open_defect_count"`: the number of defects in the defect log linked to
  that requirement with status `open` (defects with status `closed` do not
  count).
- `"ready_for_release"`: `true` if and only if `has_design` is `true`,
  `has_tests` is `true`, **and** `open_defect_count` is `0`.

Return **only** a single JSON array, one object per requirement in
`REQ-1`..`REQ-5` order, with exactly these keys: `"id"`, `"has_design"`,
`"has_tests"`, `"open_defect_count"`, `"ready_for_release"`.

Example:

```json
[
    {"id": "REQ-1", "has_design": true, "has_tests": true, "open_defect_count": 0, "ready_for_release": true}
]
```
