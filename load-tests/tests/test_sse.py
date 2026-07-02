from __future__ import annotations

from playbook_load_tests.sse import iter_sse_events, terminal_event_seen


def test_iter_sse_events_parses_multiline_frames() -> None:
    lines = [
        "id: 1-0\n",
        "event: chunk\n",
        'data: {"content": "hello"}\n',
        "\n",
        "event: complete\n",
        'data: {"status": "complete"}\n',
        "\n",
    ]

    events = list(iter_sse_events(lines))

    assert events[0].stream_id == "1-0"
    assert events[0].event == "chunk"
    assert events[0].json_data == {"content": "hello"}
    assert terminal_event_seen(events) is True
