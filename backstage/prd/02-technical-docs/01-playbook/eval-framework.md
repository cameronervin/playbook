# Evaluation Framework

This document defines Playbook MVP evaluation requirements for retrieval quality, answer quality, safety behavior, dashboard insights, and admin chat.

## Purpose

Playbook should not be considered ready for athlete use until core answer behaviors can be checked against repeatable scenarios.

<!-- V2 CHANGE: Establish Playbook-specific golden sets for NIL, compliance, process, unknown, conflict, and emergency scenarios. -->

## Eval Suites

| Suite | Purpose | User Stories |
|-------|---------|--------------|
| Retrieval evals | Expected source appears in retrieved context | US-08, US-17, US-26 |
| Answer evals | Answers are accurate, concise, cited, and warm | US-06, US-08, US-26 |
| Refusal evals | Unsupported/sensitive questions decline correctly | US-11, US-25, US-26 |
| Emergency evals | Emergency prompts refuse advice and show instructions | US-11, US-25, US-26 |
| Conflict evals | Newest applicable source is preferred | US-17, US-26 |
| Dashboard insight evals | Agent-curated topics and risk summaries match seeded data | US-18, US-20, US-21, US-26 |
| Admin chat evals | Admin chat answers cite authorized analytics or dashboard insight records | US-22, US-26 |

Phase 4 includes the first concrete dashboard insight eval spec:
`dashboard_insights`, a deterministic structural golden set with NIL,
compliance, recruiting, and unanswered support-gap cases. It verifies expected
topic/risk labels, source-message grounding, and bounded metrics without an
external judge model.

## Golden Set Categories

1. NIL process question with clear source.
2. Compliance "can I do Y?" question with clear source.
3. System process question for Teamworks/Opendorse/NILGO based on docs.
4. Unknown question with no KB support.
5. Conflicting source question where newest document should win.
6. Near-similar conflict question where source freshness should win.
7. Emergency request.
8. Medical/legal/mental-health request.
9. Recruiting-risk question.
10. Admin analytics seeded topic/risk scenario.

## Metrics

| Metric | Definition |
|--------|------------|
| Retrieval hit rate | Expected document appears in top-K retrieved results |
| Citation integrity | Cited source was present in retrieved context |
| Groundedness | Answer claims are supported by citations |
| Refusal accuracy | Unsafe/unsupported prompts decline correctly |
| Emergency correctness | Emergency prompts show configured instructions and no advice |
| Conflict correctness | Correct source is preferred under freshness/metadata rules |
| Admin topic accuracy | Generated topic counts match seeded data within tolerance |

## Release Gate

Minimum MVP release gate:
1. Retrieval hit rate passes configured threshold on golden set.
2. Citation integrity has no known critical failures.
3. Emergency and unsupported prompts pass deterministic checks.
4. NIL/compliance answers do not answer without KB support.
5. Dashboard insights identify seeded top topics and risk labels.
6. Admin chat answers reference only authorized analytics or dashboard insight records.
7. Deterministic release checks pass for dataset validity, LiteLLM budget/rate
   policy shape, runtime affiliation copy, observability anchors, and production
   rate-limit env posture.

Configured thresholds are release targets rather than empirical baselines. The
strict suite gates deterministic safety/privacy/reference checks at or near
perfect scores, qualitative LLM-judge rubrics at target 4.x/5 floors, and Ragas
retrieval/generation metrics at target 0.75-0.90 floors. Prompt, fixture, or
agent behavior should be fixed when current runs miss these gates.

## Implementation Notes

- Prefer deterministic assertions where possible.
- Use LLM-as-judge only for qualitative scoring that cannot be checked structurally.
- Store eval datasets in `backend/evals/datasets/`.
- Store rubrics in `backend/evals/rubrics/`.
- Run offline gates with
  `uv run --group evals python -m evals.cli release-checks`.
- Run the broader local/CI wrapper with `./deploy/scripts/release-validate.sh`;
  add `--live-evals` only when Langfuse, LiteLLM, and KB-service are configured.
- The eval runner uses Langfuse v4 `run_experiment(data=dataset.items, ...)`
  and retains a legacy `dataset=` fallback for older SDKs.
- 2026-07-02 calibration evidence: eval unit tests, dataset validation, and
  deterministic release checks pass; focused live `dashboard_insights` and
  `conversation_title` runs pass target thresholds. The full strict suite
  remains a P0 evidence gap because repeated local attempts stalled during
  `athlete_chat` external DNS resolution before a result artifact was written.
