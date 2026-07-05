from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _read_repo_file(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _service_block(compose_text: str, service_name: str) -> str:
    marker = f"  {service_name}:\n"
    start = compose_text.index(marker)
    next_service = re.search(r"\n  [A-Za-z0-9_-]+:\n", compose_text[start + len(marker) :])
    if next_service is None:
        return compose_text[start:]
    return compose_text[start : start + len(marker) + next_service.start()]


def test_compose_defines_profiled_infinity_reranker() -> None:
    base_compose = _read_repo_file("deploy/compose/base.yml")
    local_compose = _read_repo_file("deploy/compose/local.yml")
    dev_compose = _read_repo_file("deploy/compose/dev.yml")
    prod_compose = _read_repo_file("deploy/compose/prod.yml")
    base_reranker = _service_block(base_compose, "reranker")
    local_reranker = _service_block(local_compose, "reranker")
    dev_reranker = _service_block(dev_compose, "reranker")
    prod_reranker = _service_block(prod_compose, "reranker")

    assert "  reranker:" in base_compose
    assert "image: michaelf34/infinity:latest-cpu" in base_reranker
    assert "platform: ${RERANKER_PLATFORM:-linux/amd64}" not in base_reranker
    assert "BAAI/bge-reranker-base" in base_reranker
    assert "      - optimum" in base_reranker
    assert "http://localhost:7997/health" in base_reranker
    assert "      - reranker" in base_reranker
    assert "reranker_cache:" in base_compose

    assert "image: michaelf34/infinity:0.0.75" in local_reranker
    assert "mixedbread-ai/mxbai-rerank-xsmall-v1" in local_reranker
    assert "BAAI/bge-reranker-base" not in local_reranker
    assert "      - torch" in local_reranker
    assert "      - optimum" not in local_reranker
    assert '      - "7997:7997"' in local_compose
    assert "restart: \"no\"" in local_reranker
    assert "path: ../envs/.env.reranker.local" in local_reranker
    assert "required: false" in local_reranker
    assert "../envs/.env.litellm.local" not in local_reranker

    assert "../envs/.env.reranker.dev" in dev_reranker
    assert "restart: unless-stopped" in dev_reranker
    assert '7997:7997' not in prod_compose
    assert "../envs/.env.reranker.prod" in prod_reranker
    assert "restart: unless-stopped" in prod_reranker


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
    reranker_env = _read_repo_file("deploy/envs/.env.reranker.example")
    prod_env = _read_repo_file("deploy/envs/.env.prod.example")

    assert "LITELLM_PLAYBOOK_RERANK_MODEL=infinity/rerank" in local_env
    assert "INFINITY_API_BASE=http://reranker:7997" in local_env
    assert "INFINITY_API_KEY=local-infinity-reranker-key" in local_env
    assert "RERANKER_PLATFORM=linux/amd64" not in local_env

    assert "INFINITY_API_KEY=local-infinity-reranker-key" in reranker_env
    assert "DO_NOT_TRACK=1" in reranker_env
    assert "INFINITY_ANONYMOUS_USAGE_STATS=0" in reranker_env
    assert "OPENAI_API_KEY" not in reranker_env
    assert "LITELLM_MASTER_KEY" not in reranker_env

    assert "LITELLM_PLAYBOOK_RERANK_MODEL=infinity/rerank" in prod_env
    assert "INFINITY_API_BASE=http://reranker:7997" in prod_env
    assert "INFINITY_API_KEY=${INFINITY_API_KEY}" in prod_env
    assert "RERANKER_PLATFORM=linux/amd64" not in prod_env
