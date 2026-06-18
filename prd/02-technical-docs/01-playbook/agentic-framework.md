# Agentic Framework

This document defines Playbook MVP agent workflows, context contracts, safety behavior, and evaluation requirements.

## Baseline

The scaffold already includes:
- LangGraph-style agent chains, nodes, graphs, executors, prompts, states, tools, retry, and guardrails.
- LLM provider abstraction for LiteLLM mode, with direct provider mode kept only as a local-development or emergency fallback.
- Knowledgebase provider abstraction that can call the local KB service.
- Observability hooks and token-budgeting utilities.

<!-- V2 CHANGE: Replace example agent with Playbook athlete chat and admin insight agents. -->

## Runtime Matrix

| Workflow | Runtime | Trigger | Primary Output |
|----------|---------|---------|----------------|
| Athlete chat agent | LangGraph in Celery worker | Athlete message task | Streamed cited answer or refusal |
| Conversation file context | Parser/retrieval helper | Athlete file upload + message | Conversation-scoped extracted context |
| Admin analytics dashboard | Deterministic service/query layer | Admin dashboard load | Metrics, anonymized query lists, filters |
| Dashboard insights agent | LangGraph or LangChain agent | Nightly cron or admin action | Curated dashboard insight cards and summaries |
| Admin chat side panel | LangGraph or LangChain agent in Celery worker | Admin dashboard question task | Streamed analytics-grounded answer |
| Evaluation harness | pytest + LLM/RAG evals | CI/release validation | Retrieval, answer, and safety scores |

## LLM Gateway

Playbook should use LiteLLM Proxy as the default LLM gateway for backend agent
generation, KB-service embeddings, and evaluation harness calls. Application
services call model aliases through the gateway's OpenAI-compatible API instead
of storing provider API keys directly.

The gateway owns:
- provider credentials,
- model aliases such as `playbook-chat`, `playbook-fast`, and `playbook-embed`,
- provider routing/fallbacks,
- token and spend tracking,
- virtual keys or service keys,
- budget and rate-limit policy,
- provider error logging and alerting.

Direct provider mode remains useful for local smoke tests and emergency
break-glass operation, but it is not the production default. No agent workflow
should require Anthropic, OpenAI, or other provider credentials in the main
backend or frontend runtime.

LangGraph agents should compile with the Postgres checkpointer enabled in
persistent environments. The checkpointer stores durable graph state keyed by
thread/session IDs so streamed or multi-step agent runs can resume safely after
process restarts.

Interactive agent generation must not run inside the request handler. Athlete
chat and admin chat message APIs persist the user/admin turn and assistant
placeholder, then dispatch a Celery task. The worker executes the agent and
publishes ordered `chunk`, `progress`, `complete`, and `error` events to Valkey
Streams under the returned `task_id`; pub/sub notifications wake the HTTP stream
endpoint, which validates conversation/message or admin session/message
ownership before subscribing. Non-interactive long-running work, such as KB
ingestion and dashboard insight generation, remains polled by task/run status.

## Athlete Chat Agent

### Inputs

```json
{
  "conversation_id": "uuid",
  "athlete_user_id": "uuid",
  "message": "Can I accept this NIL deal?",
  "attached_file_ids": ["uuid"],
  "organization_id": "uuid"
}
```

### Context Sources

1. Current user question.
2. Bounded conversation history.
3. Conversation-scoped uploaded file extractions.
4. KB search results from ready, visible documents.
5. Safety policy configuration.

Policy/process guidance must be grounded in KB or conversation file context. General model knowledge may only supply harmless background phrasing, not authoritative policy claims.

### Flow

1. Message submit API saves the user message and assistant placeholder.
2. Message submit API dispatches a Celery task and returns `task_id` plus stream metadata.
3. Celery worker loads the conversation/message context and resumes the LangGraph thread.
4. Classify topic/risk labels for analytics.
5. Run safety pre-check for emergency, medical, legal, mental-health, harassment/reporting, recruiting, NIL, and compliance risk.
6. Retrieve KB context using organization and visibility filters.
7. Retrieve conversation file context from ready, nonempty files. Attached file
   IDs narrow retrieval; when no files are attached, search all ready files in
   the conversation.
8. Rank context using semantic relevance and freshness metadata.
9. Generate answer chunks and publish stream events to Valkey Streams under `task_id`.
10. Attach bottom citations for grounded answers.
11. Persist assistant message, citations, topic/risk labels, and safety outcome.
12. Publish final completion/error event so the HTTP stream endpoint can close cleanly.

### Output Contract

```json
{
  "answer": "string",
  "answer_type": "grounded_answer | refusal | emergency_instruction | unsupported",
  "citations": [
    {
      "document_id": "uuid",
      "chunk_id": "uuid",
      "source_title": "string",
      "source_date": "date",
      "rank": 1
    }
  ],
  "topic_labels": ["nil"],
  "risk_labels": ["compliance"],
  "safety_outcome": null
}
```

## Retrieval and Conflict Rules

1. Retrieve only documents with `processing_status = ready`.
2. Apply active visibility policy; MVP policy is all athletes.
3. Preserve KB-service retrieval order for semantic, hybrid, and hybrid-rerank
   modes.
4. If retrieved sources conflict, explain that guidance appears conflicting and
   direct the athlete to the athletic department.
5. Admin-uploaded shared KB documents are official by definition for MVP;
   priority does not override retrieval order.
6. Never fabricate citations.

## Refusal and Emergency Behavior

| Scenario | Behavior |
|----------|----------|
| No KB support for policy/process answer | Decline and direct athlete to athletic department |
| Emergency request | Refuse advice and show emergency instructions |
| Medical/legal/mental-health request | Decline and direct to appropriate official support |
| NIL/compliance/recruiting without source support | Decline and direct athlete to athletic department |
| Harassment/reporting topic | Provide only approved reporting path if present in KB; otherwise decline |

## Admin Analytics and Insight Boundaries

Playbook has three related admin analytics surfaces:

1. **Analytics dashboard metrics**: deterministic API queries over stored
   conversation and message records. These produce base metrics such as volume,
   topic counts, risk counts, unanswered counts, and anonymized query lists.
2. **Dashboard insights agent**: asynchronous nightly/manual analysis over the
   most recent chats and analytics for a bounded time window. It writes durable
   `dashboard_insight_runs` and `dashboard_insights` records that power curated
   dashboard cards, summaries, and recommended attention areas.
3. **Admin chat side panel**: interactive admin chat over authorized analytics,
   anonymized query lists, and stored dashboard insights. It writes
   `admin_chat_sessions` and `admin_chat_messages`; it does not create or mutate
   `dashboard_insights` except by referencing existing dashboard insight records.

## Dashboard Insights Agent

### Purpose

Analyze recent athlete chats and curate dashboard insight output for admins,
focusing on:
- query volume,
- common topics,
- unanswered/declined questions,
- NIL/compliance/recruiting risk questions,
- response gaps.

The dashboard insights agent is not primarily a document drafting tool for MVP.
It is a batch/snapshot workflow, not an interactive chat surface.

### Inputs

```json
{
  "organization_id": "uuid",
  "window_start": "timestamp",
  "window_end": "timestamp",
  "trigger_type": "nightly | manual",
  "source_filters": {
    "roles": ["athlete"],
    "message_statuses": ["complete", "declined"]
  }
}
```

### Output

```json
{
  "summary": "string",
  "headline_cards": [
    {
      "title": "NIL disclosure timing confusion",
      "value": "18 related questions",
      "severity": "medium"
    }
  ],
  "topic_breakdown": [
    { "label": "NIL", "count": 42, "examples": ["anonymized query text"] }
  ],
  "unanswered_questions": [
    { "message_id": "uuid", "text": "string", "reason": "no_kb_support" }
  ],
  "risk_breakdown": [
    { "label": "recruiting", "count": 3 }
  ],
  "recommended_attention_areas": [
    "Clarify NIL disclosure timing in athlete-facing guidance."
  ]
}
```

The agent persists one `dashboard_insight_runs` row per run and one
`dashboard_insights` output row when generation completes successfully.

## Admin Chat Side Panel

The side-panel agent answers admin questions about analytics and dashboard
insight data.
It is an admin-only conversational workflow with its own persisted session and
message records.

### Inputs

```json
{
  "session_id": "uuid | null",
  "admin_user_id": "uuid",
  "organization_id": "uuid",
  "question": "What are athletes most confused about this week?",
  "window_start": "timestamp | null",
  "window_end": "timestamp | null"
}
```

### Context Sources

1. Aggregated dashboard metrics for the requested window.
2. Anonymized query text and message-level topic/risk/safety labels.
3. Stored `dashboard_insight_runs` and `dashboard_insights`.
4. Previous messages in the same `admin_chat_sessions` thread.

### Flow

1. Create or load the admin chat session.
2. Persist the admin question and assistant placeholder as `admin_chat_messages` rows.
3. Dispatch a Celery task and return `task_id` plus stream metadata.
4. Celery worker authorizes the admin against analytics permissions.
5. Retrieve only authorized analytics, anonymized query text, and dashboard insight records.
6. Generate analytics-grounded answer chunks or decline out-of-scope questions.
7. Publish stream events to Valkey Streams under `task_id`.
8. Persist the assistant answer with references to metrics, query IDs, or dashboard insight records.
9. Publish final completion/error event so the HTTP stream endpoint can close cleanly.

### Output

```json
{
  "session_id": "uuid",
  "message_id": "uuid",
  "answer": "NIL disclosure timing is the most common confusion area...",
  "answer_type": "analytics_answer | refusal | unsupported",
  "references": [
    { "type": "metric", "id": "top_topics.nil" },
    { "type": "dashboard_insight", "id": "uuid" }
  ]
}
```

Constraints:
1. It can query aggregated analytics, anonymized query text, and stored dashboard insights.
2. It cannot expose athlete names.
3. It should reference metrics or dashboard insight records when possible.
4. It should decline questions outside admin analytics scope.
5. It must not answer from raw athlete conversation owner identity.
6. It must not edit documents, change roles, or trigger dashboard insight generation.

## Evaluation Targets

| Eval Area | Target |
|-----------|--------|
| Retrieval | Expected source appears in top-K for golden questions |
| Answer quality | Accurate, concise, warm, cited |
| Citation integrity | Citations map to retrieved context |
| Refusal | Unsupported and sensitive questions decline correctly |
| Emergency | Emergency instructions appear and advice is refused |
| Conflict handling | Newest applicable source is preferred |
| Dashboard insights | Agent-curated topic/risk summaries match seeded chat data |
| Admin chat | Answers reference authorized analytics or dashboard insight records |

## Observability

Agent runs should emit:
- request ID,
- conversation ID, dashboard insight run ID, or admin chat session ID,
- organization ID,
- topic/risk labels,
- retrieval document IDs and scores,
- answer type,
- token usage,
- latency,
- non-sensitive error reason.

Logs must not include OAuth tokens, secrets, or unnecessary PII.
