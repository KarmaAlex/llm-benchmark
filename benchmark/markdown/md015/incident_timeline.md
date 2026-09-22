# Incident Timeline — Checkout API Degradation (2026-09-14)

All times are UTC.

- 14:02 — Elevated error rate first observed by automated alerting.
- 14:06 — On-call engineer acknowledges the alert and begins investigation.
- 14:15 — Root cause identified as a misconfigured connection pool after a deploy.
- 14:20 — Rollback of the faulty deploy completes.
