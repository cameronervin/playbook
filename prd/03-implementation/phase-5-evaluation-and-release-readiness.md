# Phase 5: Evaluation and Release Readiness

## Scope Boundary For This Phase

Phase 5 creates the quality, safety, security, observability, and affiliation
gates needed before an athlete-facing prototype is considered ready. It should
package release validation into documented commands that future contributors can
run locally and in CI.

| Status | Build Area | What To Build | Current Implementation | Validation | Source Specs |
|--------|------------|---------------|------------------------|------------|--------------|
| ◐ | Eval harness foundation | Keep the backend eval package, dataset/rubric locations, CLI shape, and result storage ready for real Playbook cases. | `backend/evals/` exists with CLI/core modules, sample dataset, sample rubrics, and result folders. MVP golden datasets are not complete. | Eval loader validates sample files -> CLI can run a small local/spec suite -> result files are written in documented location. | `prd/02-technical-docs/01-playbook/eval-framework.md` |
| ☐ | Golden datasets | Create golden cases for NIL, compliance, internal process, unknown/no-source, conflict/newer-source, emergency, admin analytics, and admin chat scenarios. | Only sample/example eval assets exist. | Golden dataset files exist -> each case maps expected source/behavior/refusal -> schema validation fails on malformed cases -> dataset coverage maps to user stories. | `prd/02-technical-docs/01-playbook/eval-framework.md`, `prd/01-user-stories/epic-5-safety-governance-and-release-readiness.md` |
| ☐ | Retrieval and citation evals | Verify expected docs are retrieved and cited, and fabricated citations fail. | KB service/vector tests exist, but Playbook golden retrieval/citation evals are not implemented. | Expected source appears in top-K -> cited source was retrieved -> no fabricated citation passes -> failed docs are excluded from retrieval evals. | `prd/02-technical-docs/01-playbook/eval-framework.md`, `prd/02-technical-docs/02-kb-service/retrieval.md` |
| ☐ | Answer/refusal/emergency evals | Verify answer quality, no-source refusal, sensitive-topic refusal, and emergency instructions. | Message metadata can store safety outcomes; safety graph/policy evals are not implemented. | NIL/compliance answers decline without KB support -> emergency prompts refuse advice and show emergency instructions -> medical/legal/mental-health prompts decline -> refusal labels persist. | `prd/02-technical-docs/01-playbook/security.md`, `prd/02-technical-docs/01-playbook/agentic-framework.md` |
| ☐ | Admin analytics and chat evals | Validate dashboard insight summaries and admin chat answers against seeded analytics data. | Phase 4 feature implementation and evals are not present yet. | Seeded analytics produce expected dashboard insight themes -> admin chat references authorized analytics/insight records -> admin chat declines out-of-scope questions. | `prd/02-technical-docs/01-playbook/eval-framework.md`, `prd/02-technical-docs/01-playbook/agentic-framework.md` |
| ☐ | Security and audit release checks | Validate route guards, API auth, analytics anonymization, audit immutability, and service-to-service auth. | Phase 1 role dependencies and audit model/service exist; release-level security suite is not complete. | Athlete admin APIs return 403 -> super-admin-only routes enforce role -> admin analytics omits names/emails -> audit mutation route unavailable -> KB service rejects invalid service token. | `prd/02-technical-docs/01-playbook/security.md` |
| ☐ | Observability and affiliation checks | Verify useful logs/traces and scan product copy for explicit university affiliation claims. | Request context and structured logs exist; no release-level log/copy scan command exists. | Logs include request IDs and product IDs without tokens/secrets -> chat/retrieval/ingestion/insight events are traceable -> copy scan finds no protected affiliation claims. | `prd/02-technical-docs/01-playbook/agentic-framework.md`, `prd/02-technical-docs/01-playbook/security.md` |
| ☐ | Release validation command and docs | Document one local/CI release command or checklist for tests, evals, security checks, and smoke tests. | Backend tests and Ruff can run locally through `backend/.venv`; frontend and KB-service verification were not runnable in this shell due missing dependencies/tooling. | Documented command/checklist runs backend, frontend, KB-service, eval, security, observability, and copy checks -> failures point to actionable logs/results. | `docs/guides/setup.md`, `docs/guides/deployment.md`, `docs/development/bug-log.md`, `docs/development/tech-debt-tracker.md` |

## Definition of Done

- [ ] Golden evals exist and run with a documented command.
- [ ] Retrieval, citation, answer, refusal, emergency, admin insight, and admin chat checks pass.
- [ ] Security and audit validation passes.
- [ ] Observability validation confirms no secrets/tokens are logged.
- [ ] Affiliation-copy check passes.
- [ ] Full release validation command or checklist is documented.
