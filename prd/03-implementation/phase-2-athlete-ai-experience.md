# Phase 2: Athlete AI Experience

## Scope boundary for this phase

Phase 2 builds the core athlete-facing AI loop: streamed chat, grounded answers, citations, conversation history, conversation-scoped file upload, and safety refusal behavior.

| Status | Goal | User Stories | Validation | PRD Docs |
|--------|------|-------------|------------|----------|
| ☐ | **Persist conversation history** — create/list/load athlete-owned conversations and messages | US-06, US-10 | POST `/api/v1/conversations` creates conversation -> GET list returns only athlete-owned conversations -> GET detail returns messages/citations/files -> cross-user access returns 403/404 | prd/02-technical-docs/api-specification.md |
| ☐ | **Implement streamed chat generation** — submit messages and stream assistant response chunks | US-06, US-07 | POST message returns assistant_message_id and stream_url -> stream emits chunks -> completed stream persists assistant message -> interrupted stream shows recoverable UI state | prd/02-technical-docs/agentic-framework.md |
| ☐ | **Implement KB-grounded answer generation** — retrieve ready KB context and generate concise cited answers | US-06, US-08, US-17 | NIL golden question retrieves expected doc -> answer includes bottom citation -> citation maps to retrieved chunk -> no-source question declines | prd/02-technical-docs/agentic-framework.md, prd/02-technical-docs/_kb-service-architecture.md |
| ☐ | **Implement conversation file upload context** — allow PDF/DOCX/PPTX/XLSX files to support a single conversation | US-09 | POST file stores attachment -> extraction status updates -> message can reference attached file context -> file appears in conversation history -> shared KB search excludes conversation file | prd/02-technical-docs/integration-spec.md |
| ☐ | **Implement safety and refusal policy** — handle unknown, NIL/compliance without support, recruiting risk, medical/legal/mental-health, harassment/reporting, and emergency prompts | US-11, US-25 | Emergency prompt returns emergency instructions -> unsupported compliance prompt declines -> medical/legal prompt declines -> safety outcome is stored on message metadata | prd/02-technical-docs/security.md, prd/02-technical-docs/agentic-framework.md |

## Definition of Done

- [ ] Athletes can create, revisit, and continue conversations.
- [ ] Assistant responses stream and persist correctly.
- [ ] Grounded answers include citations.
- [ ] Unsupported and sensitive prompts decline safely.
- [ ] Conversation file uploads work without adding files to shared KB.
- [ ] Phase 2 tests and relevant eval smoke checks pass.
