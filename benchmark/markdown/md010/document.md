# Postmortem: Checkout Service Outage — 2026-06-11

## Summary

On 2026-06-11 the checkout service experienced a 38-minute partial outage caused by
an exhausted database connection pool following a deploy that removed connection
pool tuning parameters.

## Timeline

A detailed timeline of the incident is provided below.

### Detection

The alert fired 4 minutes after the faulty deploy completed.

### Mitigation

The on-call engineer rolled back the deploy, which restored service within 12 minutes
of the rollback starting.

## Action Items

- [x] Roll back the faulty deploy
- [x] Restore the connection pool tuning parameters
- [ ] Add a regression test for connection pool configuration
- [ ] Add an alert for connection pool saturation before it causes errors
- [ ] Document the connection pool tuning parameters in the service README

## Decisions

- Decision: Require a peer review specifically for connection pool configuration changes. Owner: Grace Liu. Due: 2026-06-18.
- Decision: Add connection pool saturation to the standard pre-deploy checklist. Owner: Amir Hassan. Due: 2026-06-25.

## Follow-Up

The engineering team will review progress on the above action items at the next
incident review meeting.
