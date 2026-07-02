#!/usr/bin/env bash
# OSS AppSec scanner wrapper for CI and local release evidence.
#
# Default mode runs code, dependency, secret, filesystem, and IaC scans and
# writes artifacts under .artifacts/security-scan. Image scans are opt-in for
# local use because they require Docker builds; CI calls --build-images.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARTIFACT_DIR="${SECURITY_SCAN_ARTIFACT_DIR:-$ROOT_DIR/.artifacts/security-scan}"
SEVERITY="${SECURITY_SCAN_SEVERITY:-HIGH,CRITICAL}"
BUILD_IMAGES=false
RUN_IMAGE_SCANS=true
ALLOW_MISSING_TOOLS=false
OSV_ENABLED=true
declare -a IMAGE_REFS=()
SCAN_STATUS=0

usage() {
    cat <<'USAGE'
Usage: ./deploy/scripts/security-scan.sh [options]

Runs OSS security gates and stores artifacts in .artifacts/security-scan by
default. Findings at configured blocking severity return a non-zero exit code.

Options:
  --build-images          Build Playbook production images before image scans.
  --image IMAGE           Scan an already-built image. May be passed multiple times.
  --skip-images           Skip Trivy image scans.
  --skip-osv              Skip OSV-Scanner.
  --allow-missing-tools   Warn instead of failing when an optional CLI is missing.
  --artifact-dir DIR      Override artifact output directory.
  -h, --help              Show this help.

Environment:
  SECURITY_SCAN_ARTIFACT_DIR   Artifact directory override.
  SECURITY_SCAN_SEVERITY       Trivy blocking severities, default HIGH,CRITICAL.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --build-images)
            BUILD_IMAGES=true
            ;;
        --image)
            if [[ $# -lt 2 ]]; then
                echo "Error: --image requires an image reference." >&2
                exit 2
            fi
            IMAGE_REFS+=("$2")
            shift
            ;;
        --skip-images)
            RUN_IMAGE_SCANS=false
            ;;
        --skip-osv)
            OSV_ENABLED=false
            ;;
        --allow-missing-tools)
            ALLOW_MISSING_TOOLS=true
            ;;
        --artifact-dir)
            if [[ $# -lt 2 ]]; then
                echo "Error: --artifact-dir requires a path." >&2
                exit 2
            fi
            ARTIFACT_DIR="$2"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

mkdir -p \
    "$ARTIFACT_DIR/bandit" \
    "$ARTIFACT_DIR/gitleaks" \
    "$ARTIFACT_DIR/npm-audit" \
    "$ARTIFACT_DIR/osv" \
    "$ARTIFACT_DIR/pip-audit" \
    "$ARTIFACT_DIR/requirements" \
    "$ARTIFACT_DIR/semgrep" \
    "$ARTIFACT_DIR/trivy"

log_step() {
    echo
    echo "==> $1"
}

mark_failure() {
    local label="$1"
    local code="$2"

    SCAN_STATUS=1
    echo "FAIL: ${label} exited with status ${code}" >&2
}

require_tool() {
    local tool="$1"

    if command -v "$tool" >/dev/null 2>&1; then
        return 0
    fi

    if [[ "$ALLOW_MISSING_TOOLS" == "true" ]]; then
        echo "WARN: missing ${tool}; skipping dependent scan." >&2
        return 127
    fi

    echo "Error: missing required tool '${tool}'." >&2
    return 127
}

run_gate() {
    local label="$1"
    shift

    log_step "$label"
    if "$@"; then
        echo "PASS: $label"
    else
        mark_failure "$label" "$?"
    fi
}

safe_artifact_name() {
    local value="$1"
    value="${value//\//_}"
    value="${value//:/_}"
    value="${value//@/_}"
    echo "$value"
}

export_requirements() {
    local project_name="$1"
    local project_dir="$2"
    local output_file="$ARTIFACT_DIR/requirements/${project_name}.requirements.txt"

    require_tool uv || return $?
    (
        cd "$project_dir"
        uv export --locked --all-groups --no-hashes \
            --format requirements-txt \
            --output-file "$output_file"
    )
}

run_semgrep() {
    require_tool semgrep || return $?

    semgrep scan \
        --config "$ROOT_DIR/.semgrep.yml" \
        --error \
        --json \
        --output "$ARTIFACT_DIR/semgrep/semgrep.json" \
        "$ROOT_DIR"
}

run_bandit() {
    require_tool bandit || return $?

    bandit \
        -r "$ROOT_DIR/backend/app" "$ROOT_DIR/kb-service/app" \
        -lll \
        -ii \
        -f json \
        -o "$ARTIFACT_DIR/bandit/bandit.json"
}

run_pip_audit_project() {
    local project_name="$1"
    local project_dir="$2"
    local requirements_file="$ARTIFACT_DIR/requirements/${project_name}.requirements.txt"

    require_tool pip-audit || return $?
    export_requirements "$project_name" "$project_dir" || return $?

    pip-audit \
        -r "$requirements_file" \
        --format json \
        --output "$ARTIFACT_DIR/pip-audit/${project_name}.json"
}

run_npm_audit() {
    require_tool npm || return $?

    (
        cd "$ROOT_DIR/frontend"
        npm audit --audit-level=high --json > "$ARTIFACT_DIR/npm-audit/frontend.json"
    )
}

run_gitleaks() {
    require_tool gitleaks || return $?

    gitleaks git \
        --source "$ROOT_DIR" \
        --config "$ROOT_DIR/.gitleaks.toml" \
        --report-format sarif \
        --report-path "$ARTIFACT_DIR/gitleaks/gitleaks.sarif" \
        --redact \
        --verbose
}

run_osv_scanner() {
    require_tool osv-scanner || return $?

    osv-scanner scan source \
        -r "$ROOT_DIR" \
        --format json \
        --output "$ARTIFACT_DIR/osv/osv-scanner.json"
}

run_trivy_fs() {
    require_tool trivy || return $?

    trivy fs \
        --quiet \
        --scanners vuln \
        --severity "$SEVERITY" \
        --exit-code 1 \
        --format sarif \
        --output "$ARTIFACT_DIR/trivy/trivy-fs.sarif" \
        --skip-dirs "$ROOT_DIR/.git" \
        --skip-dirs "$ROOT_DIR/.artifacts" \
        --skip-dirs "$ROOT_DIR/frontend/.next" \
        --skip-dirs "$ROOT_DIR/frontend/node_modules" \
        "$ROOT_DIR"
}

run_trivy_config() {
    require_tool trivy || return $?

    trivy config \
        --quiet \
        --severity "$SEVERITY" \
        --exit-code 1 \
        --format sarif \
        --output "$ARTIFACT_DIR/trivy/trivy-config.sarif" \
        "$ROOT_DIR/deploy"
}

build_playbook_images() {
    require_tool docker || return $?

    docker build \
        --pull \
        -f "$ROOT_DIR/deploy/docker/Dockerfile.backend" \
        -t playbook/backend:security-scan \
        "$ROOT_DIR/backend"
    docker build \
        --pull \
        -f "$ROOT_DIR/deploy/docker/Dockerfile.frontend" \
        -t playbook/frontend:security-scan \
        "$ROOT_DIR/frontend"
    docker build \
        --pull \
        -f "$ROOT_DIR/deploy/docker/Dockerfile.kb-service" \
        -t playbook/kb-service:security-scan \
        "$ROOT_DIR/kb-service"
    docker build \
        --pull \
        -f "$ROOT_DIR/deploy/docker/Dockerfile.litellm" \
        -t playbook/litellm:security-scan \
        "$ROOT_DIR"

    IMAGE_REFS+=(
        "playbook/backend:security-scan"
        "playbook/frontend:security-scan"
        "playbook/kb-service:security-scan"
        "playbook/litellm:security-scan"
    )
}

run_trivy_image_scans() {
    require_tool trivy || return $?

    if [[ "$BUILD_IMAGES" == "true" ]]; then
        build_playbook_images || return $?
    fi

    if [[ "${#IMAGE_REFS[@]}" -eq 0 ]]; then
        echo "No image references supplied; skipping image scans."
        echo "Pass --build-images or one or more --image values to enable them."
        return 0
    fi

    local image_ref
    for image_ref in "${IMAGE_REFS[@]}"; do
        local artifact_name
        artifact_name="$(safe_artifact_name "$image_ref")"
        trivy image \
            --quiet \
            --severity "$SEVERITY" \
            --exit-code 1 \
            --format sarif \
            --output "$ARTIFACT_DIR/trivy/${artifact_name}.sarif" \
            "$image_ref"
    done
}

echo "Security scan artifact directory: $ARTIFACT_DIR"
echo "Blocking Trivy severities: $SEVERITY"

run_gate "Semgrep CE SAST" run_semgrep
run_gate "Bandit Python SAST" run_bandit
run_gate "pip-audit backend dependencies" run_pip_audit_project "backend" "$ROOT_DIR/backend"
run_gate "pip-audit KB-service dependencies" run_pip_audit_project "kb-service" "$ROOT_DIR/kb-service"
run_gate "npm audit frontend dependencies" run_npm_audit
run_gate "Gitleaks secret scan" run_gitleaks

if [[ "$OSV_ENABLED" == "true" ]]; then
    run_gate "OSV dependency scan" run_osv_scanner
else
    echo
    echo "==> OSV dependency scan"
    echo "SKIP: disabled with --skip-osv"
fi

run_gate "Trivy filesystem vulnerability scan" run_trivy_fs
run_gate "Trivy deploy/IaC misconfiguration scan" run_trivy_config

if [[ "$RUN_IMAGE_SCANS" == "true" ]]; then
    run_gate "Trivy image vulnerability scans" run_trivy_image_scans
else
    echo
    echo "==> Trivy image vulnerability scans"
    echo "SKIP: disabled with --skip-images"
fi

echo
if [[ "$SCAN_STATUS" -eq 0 ]]; then
    echo "Security scan passed. Artifacts: $ARTIFACT_DIR"
else
    echo "Security scan failed. Review artifacts: $ARTIFACT_DIR" >&2
fi

exit "$SCAN_STATUS"
