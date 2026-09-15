# Incident Response Runbook

**Document ID:** RUN-OPS-014  
**Owner:** Platform Reliability  
**Severity scale:** SEV1 (customer-facing outage) to SEV4 (informational)

## Triage

1. Acknowledge the alert in PagerDuty within 15 minutes for SEV1/SEV2.
2. Open an incident channel: `#inc-YYYYMMDD-shortname`.
3. Assign Incident Commander (IC), Communications lead, and Scribe.
4. Capture start time, impacted services, and customer-facing symptoms in the channel topic.

## Containment

- Prefer traffic shifting and feature flags over immediate restarts when the blast radius is unclear.
- For suspected credential exposure, rotate keys via the secrets manager and invalidate sessions in Auth Service.
- Database failover is authorized by the IC after confirming replica lag is under 30 seconds.

## Communication

| Severity | Internal update cadence | External status page |
|----------|-------------------------|----------------------|
| SEV1     | Every 15 minutes        | Required within 30 min |
| SEV2     | Every 30 minutes        | Required if >1 hour    |
| SEV3     | Hourly                  | Optional               |
| SEV4     | As needed               | Not required           |

Customer-facing messages must be reviewed by Communications before posting. Do not speculate on root cause in external updates.

## Resolution and handoff

1. Confirm recovery with at least two independent health checks.
2. Mark the incident resolved in PagerDuty.
3. Schedule a post-incident review within three business days for SEV1 and SEV2.
4. File follow-up tickets with owners and due dates before closing the incident channel.
