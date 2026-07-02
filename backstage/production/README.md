# Production Operations

Last updated: July 2, 2026

This folder holds rollout-ready operational documents for Playbook production
readiness. Keep these files concise, evidence-based, and safe to commit.

Do not commit raw scanner payloads, SBOMs, prompts, source text, signed URLs,
tokens, secrets, athlete identity, or raw IP addresses here. Link to workflow
runs, artifact names, tickets, and sanitized summaries instead.

## Documents

| Document | Purpose |
|----------|---------|
| [Coverage Policy](coverage-policy.md) | Risk-based test coverage standard and evidence command set. |
| [Coverage Manifest](coverage-policy.yaml) | Machine-readable P1 risk-surface evidence checked by `evals.cli release-checks`. |
| [Incident Runbook](incident-runbook.md) | Severity model, roles, communication, containment, rotation, evidence, and post-incident review. |
| [Data Lifecycle](data-lifecycle.md) | Retention/deletion/export/audit/eval data rules with approval placeholders. |
| [External Review Plan](external-review-plan.md) | Scoped app security review packet and scheduling evidence requirements. |

## Gate Closure Rules

- Mark the P1 coverage policy gate done only when the manifest passes release
  checks and the referenced tests/docs exist.
- Mark the incident runbook gate done when the runbook exists and names the
  default internal response roles.
- Keep data lifecycle open until retention periods and approval owners are
  filled by counsel or the rollout owner.
- Keep external review open until there is scheduling evidence with owner,
  date/window, scope, and tracking link.
