"""Small SSE parser used by live Locust scenarios."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SSEEvent:
    """One parsed Server-Sent Event frame."""

    stream_id: str | None
    event: str
    data: str
    json_data: Any


def iter_sse_events(lines: Iterable[str | bytes]) -> Iterator[SSEEvent]:
    """Yield parsed SSE frames from response lines."""
    frame: list[str] = []
    for raw_line in lines:
        line = (
            raw_line.decode("utf-8", errors="replace")
            if isinstance(raw_line, bytes)
            else raw_line
        )
        line = line.rstrip("\r\n")
        if line == "":
            if frame:
                yield _parse_frame(frame)
                frame = []
            continue
        frame.append(line)
    if frame:
        yield _parse_frame(frame)


def terminal_event_seen(events: Iterable[SSEEvent]) -> bool:
    """Return whether a complete or error terminal event appears."""
    return any(event.event in {"complete", "error"} for event in events)


def _parse_frame(lines: list[str]) -> SSEEvent:
    stream_id: str | None = None
    event = "message"
    data_parts: list[str] = []
    for line in lines:
        if line.startswith("id:"):
            stream_id = line.removeprefix("id:").strip()
        elif line.startswith("event:"):
            event = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_parts.append(line.removeprefix("data:").strip())
    data = "\n".join(data_parts)
    try:
        json_data = json.loads(data) if data else None
    except json.JSONDecodeError:
        json_data = None
    return SSEEvent(stream_id=stream_id, event=event, data=data, json_data=json_data)
