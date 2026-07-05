# Security Scanner Evidence

Use this directory for concise release evidence pointers. Do not commit scanner
artifact payloads, raw SARIF/JSON dumps, SBOM files, secrets, prompts, signed
URLs, source text, athlete identity, or raw IP addresses.

## Release Evidence Template

| Field | Value |
|-------|-------|
| Release candidate | `<tag-or-sha>` |
| Security Scan workflow run | `<GitHub Actions run URL>` |
| Release Readiness workflow run | `<GitHub Actions run URL>` |
| Scanner artifact names | `security-scan-artifacts`, `release-security-scan-artifacts` |
| SBOM artifact names | `sbom-artifacts`, `release-sbom-artifacts` |
| Blocking findings | `<none or linked issue IDs>` |
| Accepted risks | `<owner, expiry, mitigation, rollback path>` |
| Release owner | `<name>` |
| Evidence captured at | `<YYYY-MM-DD HH:MM UTC>` |

## Current Placeholder

No production release scanner evidence has been captured yet. First release
candidate evidence should link the `Security Scan` and `Release Readiness`
workflow runs plus their uploaded artifacts.
