# Project Charter: Customer Data Platform Migration

Document ID: PC-2026-0091
Owner: Marcus Webb
Sponsor: VP Engineering
Status: Approved
Start Date: 2026-03-02
Target End Date: 2026-08-28

## Background

The current customer data platform runs on infrastructure that is being deprecated by
the end of the year. This project migrates all customer profile data to the new
platform with zero downtime.

## Objectives

- Migrate all customer profile records without data loss
- Maintain API backward compatibility for downstream consumers
- Decommission the legacy platform by the target end date

## Stakeholders

The Data Platform team, the API Gateway team, and the Customer Support team are all
affected by this migration and will be kept informed via the weekly status report.
