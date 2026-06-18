from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _read_repo_file(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_compose_defines_profiled_infinity_reranker() -> None:
    base_compose = _read_repo_file("deploy/compose/base.yml")
    local_compose = _read_repo_file("deploy/compose/local.yml")
    prod_compose = _read_repo_file("deploy/compose/prod.yml")

    assert "  reranker:" in base_compose
    assert "michaelf34/infinity:latest-cpu" in base_compose
    assert "platform: ${RERANKER_PLATFORM:-linux/amd64}" in base_compose
    assert "BAAI/bge-reranker-base" in base_compose
    assert "      - optimum" in base_compose
    assert "http://localhost:7997/health" in base_compose
    assert "      - reranker" in base_compose
    assert "reranker_cache:" in base_compose

    assert '      - "7997:7997"' in local_compose
    assert "../envs/.env.litellm.local" in local_compose
    assert '7997:7997' not in prod_compose
    assert "../envs/.env.prod" in prod_compose


def test_litellm_routes_playbook_rerank_to_infinity_alias() -> None:
    config = _read_repo_file("deploy/litellm/config.yaml")

    assert "model_name: playbook-rerank" in config
    assert "model: os.environ/LITELLM_PLAYBOOK_RERANK_MODEL" in config
    assert "api_base: os.environ/INFINITY_API_BASE" in config
    assert "api_key: os.environ/INFINITY_API_KEY" in config
    assert "huggingface/BAAI/bge-reranker-base" not in config
    assert "cohere/" not in config


def test_litellm_env_examples_include_infinity_reranker_settings() -> None:
    local_env = _read_repo_file("deploy/envs/.env.litellm.local.example")
    prod_env = _read_repo_file("deploy/envs/.env.prod.example")

    assert "LITELLM_PLAYBOOK_RERANK_MODEL=infinity/BAAI/bge-reranker-base" in local_env
    assert "RERANKER_PLATFORM=linux/amd64" in local_env
    assert "INFINITY_API_BASE=http://reranker:7997" in local_env
    assert "INFINITY_API_KEY=local-infinity-reranker-key" in local_env

    assert "LITELLM_PLAYBOOK_RERANK_MODEL=infinity/BAAI/bge-reranker-base" in prod_env
    assert "RERANKER_PLATFORM=linux/amd64" in prod_env
    assert "INFINITY_API_BASE=http://reranker:7997" in prod_env
    assert "INFINITY_API_KEY=${INFINITY_API_KEY}" in prod_env
