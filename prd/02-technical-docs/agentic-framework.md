# Agentic Framework

This document defines Playbook MVP agent workflows, context contracts, safety behavior, and evaluation requirements.

## Baseline

The scaffold already includes:
- LangGraph-style agent chains, nodes, graphs, executors, prompts, states, tools, retry, and guardrails.
- LLM provider abstraction for direct provider mode or LiteLLM gateway mode.
- Knowledgebase provider abstraction that can call the local KB service.
- Observability hooks and token-budgeting utilities.

<!-- V2 CHANGE: Replace example agent with Playbook athlete chat and admin insight agents. -->

## Runtime Matrix

| Workflow | Runtime | Trigger | Primary Output |
|----------|---------|---------|----------------|
| Athlete chat agent | LangGraph | Athlete message | Streamed cited answer or refusal |
| Conversation file context | Parser/retrieval helper | Athlete file upload + message | Conversation-scoped extracted context |
| Admin query insights agent | LangGraph or LangChain agent | Nightly cron or admin action | Query/topic/risk insight summary |
| Talk-to-your-data side panel | LangGraph or LangChain agent | Admin dashboard question | Analytics-grounded answer |
| Evaluation harness | pytest + LLM/RAG evals | CI/release validation | Retrieval, answer, and safety scores |

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

1. Save user message.
2. Classify topic/risk labels for analytics.
3. Run safety pre-check for emergency, medical, legal, mental-health, harassment/reporting, recruiting, NIL, and compliance risk.
4. Retrieve KB context using organization and visibility filters.
5. Retrieve conversation file context if file IDs are present.
6. Rank context using freshness, official-source, and priority metadata.
7. Generate streamed answer.
8. Attach bottom citations for grounded answers.
9. Persist assistant message, citations, topic/risk labels, and safety outcome.

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
      "is_official": true,
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
3. Rank by semantic score first, then official/priority metadata, then source date.
4. If sources conflict, prefer newest applicable document by default.
5. Official or priority metadata may override freshness.
6. If conflict cannot be resolved, explain that guidance appears conflicting and direct the athlete to the athletic department.
7. Never fabricate citations.

## Refusal and Emergency Behavior

| Scenario | Behavior |
|----------|----------|
| No KB support for policy/process answer | Decline and direct athlete to athletic department |
| Emergency request | Refuse advice and show emergency instructions |
| Medical/legal/mental-health request | Decline and direct to appropriate official support |
| NIL/compliance/recruiting without source support | Decline and direct athlete to athletic department |
| Harassment/reporting topic | Provide only approved reporting path if present in KB; otherwise decline |

## Admin Query Insights Agent

### Purpose

Summarize recent user questions and queries for admins, focusing on:
- query volume,
- common topics,
- unanswered/declined questions,
- NIL/compliance/recruiting risk questions,
- response gaps.

The insights agent is not primarily a document drafting tool for MVP.

### Inputs

```json
{
  "organization_id": "uuid",
  "window_start": "timestamp",
  "window_end": "timestamp",
  "trigger_type": "nightly | manual"
}
```

### Output

```json
{
  "summary": "string",
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

## Talk-to-Your-Data Side Panel

The side-panel agent answers admin questions about analytics and insight data.

Constraints:
1. It can query aggregated analytics, anonymized query text, and stored insight runs.
2. It cannot expose athlete names.
3. It should reference metrics or insight records when possible.
4. It should decline questions outside admin analytics scope.

## Evaluation Targets

| Eval Area | Target |
|-----------|--------|
| Retrieval | Expected source appears in top-K for golden questions |
| Answer quality | Accurate, concise, warm, cited |
| Citation integrity | Citations map to retrieved context |
| Refusal | Unsupported and sensitive questions decline correctly |
| Emergency | Emergency instructions appear and advice is refused |
| Conflict handling | Newest or official/priority source is preferred |
| Admin insights | Topics/risk summaries match seeded query data |

## Observability

Agent runs should emit:
- request ID,
- conversation ID or insight run ID,
- organization ID,
- topic/risk labels,
- retrieval document IDs and scores,
- answer type,
- token usage,
- latency,
- non-sensitive error reason.

Logs must not include OAuth tokens, secrets, or unnecessary PII.
