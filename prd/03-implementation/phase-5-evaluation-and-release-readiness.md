# Phase 5: Evaluation and Release Readiness

## Scope boundary for this phase

Phase 5 creates the quality and safety gates needed before an athlete-facing prototype is considered ready.

| Status | Goal | User Stories | Validation | PRD Docs |
|--------|------|-------------|------------|----------|
| ☐ | **Create golden evaluation datasets** — cover NIL, compliance, process, unknown, conflict, emergency, and admin-insight scenarios | US-26 | Golden dataset files exist -> each scenario maps expected behavior/source -> dataset loader validates schema | prd/02-technical-docs/01-playbook/eval-framework.md |
| ☐ | **Implement retrieval and citation evals** — verify expected docs are retrieved and cited | US-08, US-17, US-26 | Expected source appears in top-K -> cited document was retrieved -> fabricated citation test fails correctly | prd/02-technical-docs/01-playbook/eval-framework.md, prd/02-technical-docs/02-kb-service/retrieval.md |
| ☐ | **Implement refusal and emergency evals** — verify unsafe/unsupported prompts decline correctly | US-11, US-25, US-26 | Emergency prompt refuses advice and shows instructions -> unsupported NIL prompt declines -> medical/legal prompts decline | prd/02-technical-docs/01-playbook/security.md, prd/02-technical-docs/01-playbook/eval-framework.md |
| ☐ | **Validate security and audit controls** — test route guards, API auth, analytics anonymization, and audit immutability | US-04, US-19, US-24 | Athlete admin API returns 403 -> admin analytics omits names -> role change audit exists -> audit mutation route unavailable | prd/02-technical-docs/01-playbook/security.md |
| ☐ | **Validate observability and affiliation controls** — ensure logs are useful and product copy remains unaffiliated | US-27, US-28 | Logs contain request IDs without tokens/secrets -> chat/retrieval/ingestion/insight events are traceable -> product copy scan finds no protected affiliation claims | prd/02-technical-docs/01-playbook/agentic-framework.md, prd/02-technical-docs/01-playbook/security.md |

## Definition of Done

- [ ] Golden evals exist and run with documented command.
- [ ] Retrieval, citation, refusal, emergency, and admin insight checks pass.
- [ ] Security and audit validation passes.
- [ ] Observability validation confirms no secrets/tokens are logged.
- [ ] Affiliation-copy check passes.
- [ ] Full release validation command is documented.
