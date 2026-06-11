# Athlete Streaming Flow

This guide explains the Phase 2 athlete assistant stream path. The stream is
SSE over HTTP, backed by Valkey Streams for durable ordering and reconnects.

## Shape

```text
POST /conversations/{id}/messages
        |
        v
ConversationService.submit_message
        |
        +--> conversation_messages: user row
        +--> conversation_messages: assistant placeholder with metadata.task_id
        |
        v
AthleteChatTaskDispatcher.dispatch
        |
        v
Celery run_athlete_chat_task
        |
        v
AgentStreamService.publish_*
        |
        v
Valkey Stream: agent-stream:<task_id>:events
        |
        v
GET /conversations/{id}/messages/{assistant_id}/stream?task_id=...
        |
        v
StreamingResponse text/event-stream
```

## Sequence

```text
Athlete UI       FastAPI API        ConversationService      Celery Worker      Valkey
   |                 |                       |                    |              |
   | POST message    |                       |                    |              |
   |---------------->| submit_message        |                    |              |
   |                 |---------------------->| create user msg    |              |
   |                 |                       | create assistant   |              |
   |                 |                       | placeholder/task_id|              |
   |                 |                       | dispatch task      |              |
   |                 |<----------------------|                    |              |
   |<----------------| 202 + stream_url      |                    |              |
   |                 |                       |                    | publish event|
   | GET stream      |                       |                    |------------->|
   |---------------->| validate_message_stream                    xadd + publish |
   |                 |---------------------->|                    |              |
   |                 | iter_task_events      |                    |              |
   |                 |--------------------------------------------------------->|
   |                 |<---------------------------------------------------------|
   |<----------------| SSE: progress/chunk/complete/error                     |
```

## Numbered Flow

1. The athlete posts a follow-up message.

```python
async def submit_message(...):
    return await service.submit_message(...)
```

2. `ConversationService.submit_message(...)` verifies ownership and creates the
   user message.

```python
conversation = await conversation_repo.get_for_athlete(...)

user_message = await message_repo.create(
    conversation_id=conversation.id,
    role="user",
    content=request.content,
    status="complete",
)
```

3. The same service creates the assistant placeholder and binds it to a
   generated `task_id`.

```python
assistant_message = await message_repo.create(
    conversation_id=conversation.id,
    role="assistant",
    content="",
    status="streaming",
    metadata={"task_id": task_id, "user_message_id": str(user_message.id)},
)
```

4. The service dispatches the worker task with the same `task_id`.

```python
run_athlete_chat_task.apply_async(
    kwargs=payload.to_kwargs(),
    task_id=task_id,
)
```

5. The submit response gives the frontend the stream URL.

```json
{
  "assistant_message_id": "uuid",
  "task_id": "celery-task-id",
  "stream_url": "/api/v1/conversations/uuid/messages/uuid/stream?task_id=celery-task-id"
}
```

6. The frontend opens the SSE endpoint.

```http
GET /api/v1/conversations/{conversation_id}/messages/{assistant_message_id}/stream?task_id=...
```

7. `stream_message(...)` validates that the athlete owns the conversation and
   that the assistant message is bound to the supplied `task_id`.

```python
await service.validate_message_stream(
    athlete=athlete,
    conversation_id=conversation_id,
    message_id=message_id,
    task_id=task_id,
)
```

The binding check is:

```python
message.conversation_id == conversation.id
message.role == "assistant"
message.message_metadata.get("task_id") == task_id
```

8. The endpoint returns an SSE `StreamingResponse`.

```python
return StreamingResponse(
    _iter_sse_events(stream_service=stream_service, task_id=task_id, after_id=cursor),
    media_type="text/event-stream",
)
```

9. The worker publishes events through `AgentStreamService`.

```python
await stream_service.publish_progress(task_id, status="scaffold_started")
await stream_service.publish_error(
    task_id,
    message="Athlete chat agent is not implemented yet.",
    code="agent_not_implemented",
)
```

10. `AgentStreamService._publish(...)` wraps each payload in `AgentStreamEvent`.

```python
event = AgentStreamEvent(
    task_id=task_id,
    event_type=event_type,
    data=data,
)
await provider.publish_event(event)
```

11. `ValkeyAgentStreamProvider.publish_event(...)` stores the event and sends a
    wakeup notification.

```python
stream_id = await client.xadd(
    "agent-stream:<task_id>:events",
    event.to_stream_fields(),
)
await client.publish("agent-stream:<task_id>:notify", stream_id)
```

Valkey Streams are the source of truth. Pub/sub is only a wakeup path.

12. `ValkeyAgentStreamProvider.iter_events(...)` reads ordered records after the
    current cursor.

```python
response = await client.xread(
    streams={stream_key: last_id},
    count=read_count,
    block=block_ms,
)
```

13. Each Valkey record is decoded and yielded.

```python
event = AgentStreamEvent.from_stream_fields(fields)
yield AgentStreamRecord(stream_id=stream_id, event=event)
```

14. `_iter_sse_events(...)` converts each record into an SSE frame.

```python
async for record in stream_service.iter_task_events(task_id, after_id=after_id):
    yield format_sse_record(record)
```

Example SSE frame:

```text
id: 1749560000000-0
event: progress
data: {"stream_id":"1749560000000-0","task_id":"...","event_type":"progress","data":{"status":"scaffold_started"}}
```

15. The stream closes when a terminal event arrives.

```python
if event.is_terminal:
    return
```

Terminal event types are `complete` and `error`.

## Reconnects

The endpoint accepts either `after_id` or the browser SSE `Last-Event-ID`
header. `Last-Event-ID` wins.

```http
Last-Event-ID: 1749560000000-0
```

The next `xread` starts after that stream ID, so already delivered events are
not replayed.

## Future LangGraph Handoff

The future agent worker should publish LangGraph stream parts through
`AgentStreamService.publish_langgraph_part(...)`.

```python
async for part in graph.astream(
    inputs,
    stream_mode=["messages", "updates", "custom"],
    version="v2",
):
    await stream_service.publish_langgraph_part(task_id, part)
```

Mapping:

```text
LangGraph messages -> chunk
LangGraph custom   -> progress, unless it declares chunk/complete/error
LangGraph updates  -> graph_update progress with safe node metadata only
```

The HTTP SSE endpoint does not need to change when the real LangGraph agent is
added.
