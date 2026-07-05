"""Shared repository sentinels for partial updates."""


class _UnsetType:
    """Sentinel type for omitted partial-update values."""


_UNSET = _UnsetType()

__all__ = ["_UNSET", "_UnsetType"]
