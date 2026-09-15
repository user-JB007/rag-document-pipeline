# Access Control Policy

**Document ID:** POL-SEC-001  
**Owner:** Security Operations  
**Effective:** 2025-01-15  
**Review cycle:** Annual

## Purpose

This policy defines how employee and contractor accounts are provisioned, reviewed, and revoked for systems that hold customer or proprietary data.

## Account provisioning

1. Managers submit access requests through the IT service portal with a business justification and required role.
2. Security Operations approves requests within two business days for standard roles; elevated roles require director sign-off.
3. Accounts use SSO where available. Local accounts are allowed only when SSO is unsupported and must use MFA.
4. Temporary contractor accounts expire on the contract end date and are not auto-renewed.

## Access reviews

- System owners run quarterly access reviews for applications tagged `customer-data` or `production`.
- Reviewers must confirm each account still needs the assigned role.
- Orphaned accounts (no active manager or ticket) are suspended within five business days of discovery.

## Revocation

- HR offboarding tickets trigger same-day revocation for SSO-linked accounts.
- Manual revocation for local accounts must be completed within four hours of ticket creation.
- Emergency lockouts are available via the Security Operations on-call channel (`#sec-ops`).

## Exceptions

Exceptions require a written risk acceptance from the system owner and Security Operations, logged in the GRC register with an expiration date not exceeding 90 days.
