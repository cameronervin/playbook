# Evaluation Framework

This document defines Playbook MVP evaluation requirements for retrieval quality, answer quality, safety behavior, and admin insights.

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
| Conflict evals | Newest or official/priority source is preferred | US-17, US-26 |
| Admin insight evals | Query topics and risk summaries match seeded data | US-18, US-20, US-21, US-22, US-26 |

## Golden Set Categories

1. NIL process question with clear source.
2. Compliance "can I do Y?" question with clear source.
3. System process question for Teamworks/Opendorse/NILGO based on docs.
4. Unknown question with no KB support.
5. Conflicting source question where newest document should win.
6. Official/priority conflict question where metadata should win.
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
5. Admin insights identify seeded top topics and risk labels.

## Implementation Notes

- Prefer deterministic assertions where possible.
- Use LLM-as-judge only for qualitative scoring that cannot be checked structurally.
- Store eval datasets in `backend/evals/datasets/`.
- Store rubrics in `backend/evals/rubrics/`.
- Add a documented command for release validation once the implementation exists.
