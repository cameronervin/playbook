"""Sync on-disk YAML datasets into Langfuse (idempotent).

Datasets are source-of-truth on disk and version-controlled; this mirrors them
into Langfuse. A stable id derived from each item's input makes re-syncing an
upsert rather than a duplicate. ``get_client()`` is accessed lazily so importing
this module never binds a disabled client before ``init_langfuse()`` runs.

Oversized items: Langfuse hard-caps each ``create_dataset_item`` request body at
1MB (server-side, not raisable on the shared gateway). Some items embed a large
input field (e.g. an uploaded document) that exceeds it, producing an opaque 413.
To preserve eval fidelity (the synced ``input`` is fed verbatim to the agent at
run time), sync externalizes oversized ``input`` fields to local sidecar blobs
and stores a lightweight ``{"$blob_ref": ...}`` placeholder in the synced item.
The chain adapter resolves the ref back to full content before invoking the agent
(see ``resolve_blob_refs``). A size guard raises a clear error if an item is still
too big after externalization.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger(__name__)

# Langfuse caps each create_dataset_item request body at 1MB. Externalize against
# a slightly lower budget so the JSON envelope + ref placeholders stay clear of it.
LANGFUSE_ITEM_LIMIT_BYTES = 1_000_000
_EXTERNALIZE_BUDGET_BYTES = 900_000

BLOB_REF_KEY = "$blob_ref"
_BLOB_DIRNAME = "_blobs"


def _stable_id(item: dict) -> str:
    """Deterministic id from the input so re-syncing upserts instead of duplicating.

    Computed from the ORIGINAL (pre-externalization) input so the id is tied to
    real content and stays stable regardless of blob paths.
    """
    raw = json.dumps(item["input"], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _serialized_size(obj: object) -> int:
    return len(json.dumps(obj, default=str).encode("utf-8"))


def _largest_externalizable_field(input_obj: dict) -> str | None:
    """Key of the largest externalizable field under ``input`` by serialized size.

    Any field except the agent prompt (``question``/``query``) and existing blob
    refs is a candidate, whether it is a string or a nested structure (e.g. an
    uploaded document keyed by file id). Returns None when nothing is left to
    externalize.
    """
    candidates = {
        k: v
        for k, v in input_obj.items()
        if k not in ("question", "query")
        and not (isinstance(v, dict) and BLOB_REF_KEY in v)
    }
    if not candidates:
        return None
    return max(candidates, key=lambda k: _serialized_size(candidates[k]))


def _write_blob(value: object, blob_dir: Path, item_id: str, key: str) -> tuple[Path, str]:
    """Write a field value to a sidecar blob. Strings stay text; others go JSON.

    Returns (path, ref) where ref encodes whether the blob is JSON so the
    resolver restores the original type.
    """
    blob_dir.mkdir(parents=True, exist_ok=True)
    is_json = not isinstance(value, str)
    suffix = "json" if is_json else "txt"
    blob_path = blob_dir / f"{item_id}_{key}.{suffix}"
    text = json.dumps(value, ensure_ascii=False) if is_json else value
    blob_path.write_text(text, encoding="utf-8")
    return blob_path, f"{_BLOB_DIRNAME}/{blob_path.name}"


def externalize_oversized(
    item: dict, *, blob_dir: Path, item_id: str
) -> tuple[dict, list[Path]]:
    """Return a Langfuse-safe copy of ``item`` plus the sidecar blob paths written.

    Externalizes the largest non-prompt ``input`` field (string or nested object)
    repeatedly until the item fits the budget. Raises ``ValueError`` if it still
    exceeds the hard 1MB limit afterwards (e.g. an oversized non-input field).
    """
    if _serialized_size(item) <= _EXTERNALIZE_BUDGET_BYTES:
        return item, []

    prepared = dict(item)
    prepared["input"] = dict(item.get("input") or {})
    written: list[Path] = []

    while _serialized_size(prepared) > _EXTERNALIZE_BUDGET_BYTES:
        key = _largest_externalizable_field(prepared["input"])
        if key is None:
            break  # nothing left to externalize -> guard below fires
        blob_path, ref = _write_blob(prepared["input"][key], blob_dir, item_id, key)
        written.append(blob_path)
        prepared["input"][key] = {BLOB_REF_KEY: ref}

    if _serialized_size(prepared) > LANGFUSE_ITEM_LIMIT_BYTES:
        raise ValueError(
            f"Dataset item {item_id!r} is {_serialized_size(prepared) / 1_000_000:.2f}MB "
            f"after externalizing all input fields, still over the Langfuse 1MB "
            f"per-item limit. The oversized payload is outside ``input`` (e.g. "
            f"expected_output or metadata); trim it in the dataset or split the item."
        )
    return prepared, written


def resolve_blob_refs(input_obj: object, *, base_dir: Path) -> object:
    """Inverse of externalization: replace any ``{"$blob_ref": path}`` with content.

    Used by the chain adapter so the agent receives the full original input.
    A ``.json`` blob is parsed back to its structure; a ``.txt`` blob stays a
    string. Non-ref values pass through unchanged.
    """
    if not isinstance(input_obj, dict):
        return input_obj
    ref = input_obj.get(BLOB_REF_KEY)
    if ref is not None:
        text = (base_dir / ref).read_text(encoding="utf-8")
        return json.loads(text) if str(ref).endswith(".json") else text
    return {k: resolve_blob_refs(v, base_dir=base_dir) for k, v in input_obj.items()}


def sync_dataset_to_langfuse(yaml_path: str, dataset_name: str) -> int:
    """Create the dataset (if absent) and upsert every item. Returns item count."""
    from langfuse import get_client

    langfuse = get_client()
    langfuse.create_dataset(name=dataset_name)  # idempotent: no-op if it exists

    dataset_path = Path(yaml_path)
    blob_dir = dataset_path.parent / _BLOB_DIRNAME
    with open(dataset_path, encoding="utf-8") as fh:
        items = yaml.safe_load(fh) or []

    for item in items:
        item_id = _stable_id(item)  # from original input -> stable across syncs
        prepared, _ = externalize_oversized(item, blob_dir=blob_dir, item_id=item_id)
        langfuse.create_dataset_item(
            dataset_name=dataset_name,
            id=item_id,  # stable id => upsert, not duplicate
            input=prepared["input"],
            expected_output=prepared.get("expected_output"),
            metadata=prepared.get("metadata"),
        )
    langfuse.flush()
    logger.info("dataset_synced", dataset=dataset_name, items=len(items))
    return len(items)
