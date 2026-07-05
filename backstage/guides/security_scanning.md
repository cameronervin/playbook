# Security Scanning Runbook

This runbook covers the OSS-only AppSec gates used before release. The CI
workflows store scanner evidence as artifacts; do not commit SARIF, JSON, or
SBOM output files unless a release owner explicitly requests a redacted evidence
snapshot.

## CI Gates

| Workflow | Trigger | Blocks On | Artifacts |
|----------|---------|-----------|-----------|
| `.github/workflows/security-scan.yml` | pull request, `main` push, weekly schedule, manual dispatch | Semgrep CE, Bandit, pip-audit, npm audit, OSV-Scanner, Gitleaks, Trivy filesystem/config/image scans | `security-scan-artifacts`, `sbom-artifacts` |
| `.github/workflows/release-readiness.yml` | pull request, `main` push, `v*` tag, published release, manual dispatch | `deploy/scripts/release-validate.sh --ci --include-scanners`, scanner gates, SBOM generation | `release-security-scan-artifacts`, `release-sbom-artifacts` |
| `.github/workflows/dast.yml` | manual dispatch against staging | OWASP ZAP baseline scans for the frontend and `/api/v1` | `dast-artifacts` |

These workflows run with read-only repository permissions and no production
secrets. The optional `live_evals` release-readiness input is off by default and
must only be enabled with approved runtime credentials.

The DAST workflow is manual because it scans real staging URLs. Use approved
staging hosts only, and store ZAP HTML/JSON/XML/Markdown output in workflow
artifacts instead of committing scanner payloads.

## Local Scanner Command

Install the same CLI families used by CI:

```bash
python -m pip install --upgrade pip
python -m pip install bandit pip-audit semgrep uv
go install github.com/gitleaks/gitleaks/v8@v8.27.2
go install github.com/google/osv-scanner/v2/cmd/osv-scanner@v2.4.0
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sudo sh -s -- -b /usr/local/bin v0.72.0
```

Run source/config/dependency/secret scans:

```bash
./deploy/scripts/security-scan.sh --skip-images
```

Run the full gate, including local Docker image builds:

```bash
./deploy/scripts/security-scan.sh --build-images
```

Artifacts are written to `.artifacts/security-scan/` unless
`SECURITY_SCAN_ARTIFACT_DIR` or `--artifact-dir` is set.

## SBOM Command

Generate CycloneDX JSON SBOMs for repository, backend, frontend, and KB-service
source trees:

```bash
./deploy/scripts/generate-sbom.sh --skip-images
```

Generate source and image SBOMs:

```bash
./deploy/scripts/generate-sbom.sh --build-images
```

Artifacts are written to `.artifacts/sbom/` unless `SBOM_ARTIFACT_DIR` or
`--artifact-dir` is set.

## Triage Rules

- Critical or high vulnerabilities must block release unless an accepted risk
  has an owner, expiry date, mitigation, and rollback path.
- Gitleaks findings must be treated as real until the value is proved to be a
  placeholder or a rotated/inactive credential.
- Do not paste raw secrets, tokens, signed URLs, prompts, source text, athlete
  identity, or raw IP addresses into issue comments, release notes, or evidence
  files.
- Scanner suppressions belong in `.gitleaks.toml`, `.semgrepignore`, or
  `.semgrep.yml` only when they are narrow, documented, and reviewed.

## Evidence Capture

For each release candidate, link the GitHub Actions run and artifact names from
`backstage/security/evidence/README.md` or the release notes. Use the workflow
artifact retention as the source of truth; keep committed docs to pointers and
triage summaries.
