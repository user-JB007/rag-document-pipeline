# Data Retention Policy

**Document ID:** POL-DATA-002  
**Owner:** Compliance  
**Effective:** 2025-03-01

## Scope

This policy covers customer content, application logs, backups, and employee workspace data stored in company-managed systems.

## Retention periods

| Data class              | Active retention | Post-deletion hold | Notes                                      |
|-------------------------|------------------|--------------------|--------------------------------------------|
| Customer content        | Contract term    | 30 days            | Soft-delete then purge                     |
| Application logs        | 90 days          | None               | Hot storage 14 days, then cold             |
| Security audit logs     | 365 days         | None               | Immutable; write-once storage              |
| Database backups        | 35 days          | None               | Daily snapshots; weekly retained 5 weeks   |
| Employee email          | Employment + 90d | None               | Legal hold overrides                       |

## Customer-initiated deletion

When a customer requests deletion through Support or the Admin API:

1. Soft-delete content within 48 hours.
2. Purge from active stores after 30 days unless a legal hold applies.
3. Confirm purge to the requester with ticket reference.

## Legal holds

Legal holds suspend normal retention clocks. Holds are managed by Legal in the hold register and must list affected systems and custodians. Engineering must not purge held data without written release from Legal.
