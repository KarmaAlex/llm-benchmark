# Architecture Review Board Minutes — 2026-04-14

Attendees: Diane Foss, Ravi Chandran, Lena Ostrowski, Tomasz Bilski

## Discussion

The board reviewed the proposal to introduce an event bus for cross-service
notifications and discussed the tradeoffs of Kafka versus the existing SQS-based
approach. Several open questions about schema governance were raised and will be
addressed in a follow-up session.

## Decisions

- Decision: Adopt Kafka as the standard event bus for new services. Owner: Ravi Chandran. Due: 2026-05-01.
- Decision: Draft a schema governance policy for event payloads. Owner: Lena Ostrowski. Due: 2026-04-28.
- Decision: Existing SQS-based integrations will not be migrated retroactively. Owner: Diane Foss. Due: 2026-04-14.
- Decision: Schedule a follow-up session on schema governance open questions. Owner: Tomasz Bilski. Due: 2026-04-21.
