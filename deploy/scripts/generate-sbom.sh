#!/usr/bin/env bash
# Generate CycloneDX SBOM artifacts for Playbook source trees and images.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SBOM_DIR="${SBOM_ARTIFACT_DIR:-$ROOT_DIR/.artifacts/sbom}"
BUILD_IMAGES=false
RUN_IMAGE_SBOMS=true
declare -a IMAGE_REFS=()

usage() {
    cat <<'USAGE'
Usage: ./deploy/scripts/generate-sbom.sh [options]

Generates CycloneDX JSON SBOMs with Trivy and stores them in .artifacts/sbom
by default.

Options:
  --build-images       Build Playbook production images before image SBOMs.
  --image IMAGE        Generate an SBOM for an already-built image. May repeat.
  --skip-images        Generate source SBOMs only.
  --artifact-dir DIR   Override SBOM output directory.
  -h, --help           Show this help.

Environment:
  SBOM_ARTIFACT_DIR    Artifact directory override.
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
            RUN_IMAGE_SBOMS=false
            ;;
        --artifact-dir)
            if [[ $# -lt 2 ]]; then
                echo "Error: --artifact-dir requires a path." >&2
                exit 2
            fi
            SBOM_DIR="$2"
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

require_tool() {
    local tool="$1"

    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Error: missing required tool '${tool}'." >&2
        exit 127
    fi
}

safe_artifact_name() {
    local value="$1"
    value="${value//\//_}"
    value="${value//:/_}"
    value="${value//@/_}"
    echo "$value"
}

generate_fs_sbom() {
    local component="$1"
    local path="$2"

    echo "==> Generating source SBOM: $component"
    trivy fs \
        --quiet \
        --format cyclonedx \
        --output "$SBOM_DIR/${component}.cdx.json" \
        --skip-dirs "$ROOT_DIR/.git" \
        --skip-dirs "$ROOT_DIR/.artifacts" \
        --skip-dirs "$ROOT_DIR/frontend/.next" \
        --skip-dirs "$ROOT_DIR/frontend/node_modules" \
        "$path"
}

build_playbook_images() {
    require_tool docker

    echo "==> Building Playbook images for SBOM generation"
    docker build \
        --pull \
        -f "$ROOT_DIR/deploy/docker/Dockerfile.backend" \
        -t playbook/backend:sbom \
        "$ROOT_DIR/backend"
    docker build \
        --pull \
        -f "$ROOT_DIR/deploy/docker/Dockerfile.frontend" \
        -t playbook/frontend:sbom \
        "$ROOT_DIR/frontend"
    docker build \
        --pull \
        -f "$ROOT_DIR/deploy/docker/Dockerfile.kb-service" \
        -t playbook/kb-service:sbom \
        "$ROOT_DIR/kb-service"
    docker build \
        --pull \
        -f "$ROOT_DIR/deploy/docker/Dockerfile.litellm" \
        -t playbook/litellm:sbom \
        "$ROOT_DIR"

    IMAGE_REFS+=(
        "playbook/backend:sbom"
        "playbook/frontend:sbom"
        "playbook/kb-service:sbom"
        "playbook/litellm:sbom"
    )
}

generate_image_sboms() {
    if [[ "$BUILD_IMAGES" == "true" ]]; then
        build_playbook_images
    fi

    if [[ "${#IMAGE_REFS[@]}" -eq 0 ]]; then
        echo "No image references supplied; skipping image SBOMs."
        echo "Pass --build-images or one or more --image values to enable them."
        return 0
    fi

    local image_ref
    for image_ref in "${IMAGE_REFS[@]}"; do
        local artifact_name
        artifact_name="$(safe_artifact_name "$image_ref")"
        echo "==> Generating image SBOM: $image_ref"
        trivy image \
            --quiet \
            --format cyclonedx \
            --output "$SBOM_DIR/images/${artifact_name}.cdx.json" \
            "$image_ref"
    done
}

require_tool trivy
mkdir -p "$SBOM_DIR/images"

generate_fs_sbom "repository" "$ROOT_DIR"
generate_fs_sbom "backend" "$ROOT_DIR/backend"
generate_fs_sbom "frontend" "$ROOT_DIR/frontend"
generate_fs_sbom "kb-service" "$ROOT_DIR/kb-service"

if [[ "$RUN_IMAGE_SBOMS" == "true" ]]; then
    generate_image_sboms
else
    echo "==> Image SBOMs skipped with --skip-images"
fi

cat > "$SBOM_DIR/manifest.txt" <<EOF
Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Repository: $ROOT_DIR
Format: CycloneDX JSON
Source SBOMs:
  - repository.cdx.json
  - backend.cdx.json
  - frontend.cdx.json
  - kb-service.cdx.json
Image SBOM directory:
  - images/
EOF

echo
echo "SBOM generation complete. Artifacts: $SBOM_DIR"
