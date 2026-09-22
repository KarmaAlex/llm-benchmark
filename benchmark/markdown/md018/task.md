Three files relate to the company expense policy: the v1 policy's daily
limits table, a Q2 2026 amendment that changes a subset of categories and
adds one new category, and a policy FAQ.

The FAQ is **not authoritative** — it says so explicitly — and must not be
used as a source of any limit value. Only the v1 policy table and the Q2
amendment determine the effective limits: the amendment overrides the v1
value for any category it mentions, and the v1 value stands unchanged for
any category the amendment does not mention.

Return **only** a single flat JSON object mapping each category name
(exactly as written) to its effective daily limit as a JSON integer (no
`$` sign), including every v1 category plus any new category introduced by
the amendment.

Example shape (not the real values):

```json
{
    "Travel": 400,
    "Meals": 50
}
```
