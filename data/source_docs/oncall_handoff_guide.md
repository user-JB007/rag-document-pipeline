# On-Call Handoff Guide

**Document ID:** RUN-OPS-022  
**Owner:** Platform Reliability  
**Audience:** Primary and secondary on-call engineers

## Shift boundaries

Primary on-call runs Monday 10:00 to the following Monday 10:00 (Asia/Kolkata). Secondary covers the same window and escalates only when primary is unreachable for 10 minutes on a SEV1/SEV2 page.

## Pre-shift checklist

- Confirm PagerDuty schedule shows your name for the upcoming week.
- Verify laptop VPN, bastion access, and production kubeconfig are working.
- Skim the last 7 days of `#inc-*` channels and open SEV tickets.
- Read the current Known Issues board before accepting the page.

## During the shift

- Acknowledge pages within 15 minutes (SEV1/SEV2) or 60 minutes (SEV3).
- Keep the incident channel updated; do not debug only in DMs.
- Escalate to secondary if you will be offline for more than 30 minutes during business hours.
- Log every page outcome in the on-call journal (resolved, false positive, escalated).

## Handoff meeting

At Monday 10:00, primary and secondary meet for 15 minutes:

1. Review open incidents and unfinished follow-ups.
2. Transfer any in-progress war-room ownership.
3. Confirm secondary is ready and PagerDuty override is cleared.
4. Post a short handoff note in `#platform-oncall`.

## Escalation path

Primary → Secondary → Team lead → Director of Engineering. Customer-facing SEV1 may also page Communications after the IC is assigned.
