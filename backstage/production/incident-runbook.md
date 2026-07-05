# Incident Runbook

Last updated: July 2, 2026

## Purpose

This runbook defines the default Playbook response process for production
security, privacy, availability, abuse, and data-handling incidents.

It follows the NIST SP 800-61r3 framing: Govern, Identify, and Protect support
readiness; Detect, Respond, and Recover handle active incidents; lessons learned
feed continuous improvement.

## Roles

| Role | Default responsibility |
|------|------------------------|
| Incident Commander | Own severity, coordination, timeline, and closure. |
| Engineering Lead | Own technical triage, containment, recovery, and verification. |
| Product/Customer Lead | Own customer/institution updates and user-impact assessment. |
| Legal/Comms | Own external notification language, regulatory review, and counsel coordination. |
| Security Reviewer | Own evidence handling, root-cause review, and control follow-up. |

Name the assigned people in the incident ticket before starting containment
work unless immediate action is needed to protect users or data.

## Severity Levels

| Severity | Examples | Target response |
|----------|----------|-----------------|
| SEV-1 | Active data exposure, credential compromise, production outage for most users, unsafe AI behavior at scale. | Incident Commander assigned immediately; containment starts immediately; executive/legal review. |
| SEV-2 | Limited privacy exposure, significant feature outage, repeated auth/rate-limit bypass, KB data integrity issue. | Owner assigned within 1 hour; containment plan documented same day. |
| SEV-3 | Isolated bug with security/privacy relevance, monitoring gap, failed scanner gate with no known exploitation. | Owner assigned within 1 business day; remediation tracked. |
| SEV-4 | Low-risk finding, documentation/evidence gap, planned hardening task. | Track in backlog with owner and due date. |

## Communication Path

- Primary coordination: incident ticket plus approved internal incident channel.
- Customer/institution updates: Product/Customer Lead drafts; Legal/Comms
  approves when privacy, security, contractual, or regulatory issues may apply.
- Security mailbox/vulnerability reports: triage into the incident ticket and
  preserve the original report without adding secrets to committed docs.
- Status updates must avoid prompts, source text, signed URLs, tokens, secrets,
  athlete identity, and raw IP addresses.

## Response Steps

1. Declare severity, assign roles, and create the incident ticket.
2. Capture initial facts: detection source, time observed, affected services,
   suspected data classes, active mitigations, and evidence locations.
3. Contain the issue with the smallest effective action: disable feature flag,
   revoke key/session, block abusive route, roll back deploy, pause worker,
   quarantine upload/object, or disable affected integration.
4. Preserve evidence before destructive cleanup when safe: workflow run IDs,
   sanitized logs, audit IDs, release SHA, deploy timestamps, scanner names,
   Sentry/Langfuse issue IDs, and object/database identifiers.
5. Eradicate root cause through code/config changes, secret rotation,
   permission reduction, data cleanup, or vendor action.
6. Recover service and verify with health checks, targeted tests, release
   validation, monitoring smoke events, and customer-impact checks.
7. Complete post-incident review and track follow-up work.

## Secret Rotation

Rotate relevant secrets when compromise is suspected or cannot be ruled out:

- OAuth client secrets and callback configuration.
- App `SECRET_KEY` and session-related secrets.
- KB service bearer token and webhook signing secret.
- LiteLLM virtual keys, master key, salt key, and provider keys.
- S3/MinIO access keys and signed URL configuration.
- Sentry, Langfuse, database, Valkey, and CI/deploy credentials.

Record only the secret name, rotation time, owner, and verification outcome in
the ticket. Never paste secret values into tickets or committed docs.

## Evidence Capture

Use pointers, not raw payloads:

| Evidence | Safe pointer |
|----------|--------------|
| CI/release validation | Workflow URL, run ID, artifact names. |
| Scanner findings | Tool name, finding ID, triage ticket. |
| Logs/traces | Sentry/Langfuse issue or trace ID after privacy review. |
| Database/object state | Sanitized row/object IDs and checksum where needed. |
| Customer impact | Count/range and affected feature; no athlete identity in docs. |

## Post-Incident Review

Complete within 5 business days for SEV-1/SEV-2 and within 10 business days for
SEV-3. Include timeline, root cause, impact, containment, recovery evidence,
user/customer communications, missed detections, and follow-up tasks with owner
and due date.
