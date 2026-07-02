# Eval rubrics

A rubric is a named set of scoring criteria. The same file works for both
judges: the LLM judge inlines the criteria into its prompt; the Ragas judge maps
criterion names to metrics.

## File naming and the `name:` field

- **Content rubric per agent** — `<spec_name>.yaml` (e.g. `example.yaml`). Its
  `name:` MUST equal the spec name. Scored by the LLM judge.
- **Shared RAG rubrics** (KB-using specs only) — `rag_retrieval.yaml` and
  `rag_generation.yaml`. Their `name:` MUST be exactly `rag_retrieval` and
  `rag_generation`. Scored by the Ragas judge.

The `name:` field is how a spec's `ScopedJudge` routes a rubric to the right
judge, so it must match — otherwise the rubric is silently skipped.

## Criterion shape

```yaml
name: example                  # must match the spec name (or rag_retrieval / rag_generation)
description: For the example workflow.
criteria:
  - name: correctness
    description: Does the answer match the reference in substance?
    scale: [0, 1]
  - name: conciseness
    description: Is it free of irrelevant filler?
    scale: [0, 1]
```

## RAG rubric criterion names → Ragas metrics

Use these exact names so the Ragas judge resolves native metrics; any other name
falls back to `AspectCritic` (uses the criterion `description` as its definition).

`rag_retrieval.yaml`:
```yaml
name: rag_retrieval
description: KB retrieval quality.
criteria:
  - {name: context_precision, description: "Retrieved chunks are relevant", scale: [0, 1]}
  - {name: context_recall,    description: "Retrieval found the needed evidence", scale: [0, 1]}
```

`rag_generation.yaml`:
```yaml
name: rag_generation
description: KB-grounded generation quality.
criteria:
  - {name: faithfulness,     description: "Answer is grounded in retrieved context", scale: [0, 1]}
  - {name: answer_relevancy, description: "Answer addresses the question asked",      scale: [0, 1]}
```

> `answer_relevancy` needs an embeddings model (`EVAL_EMBEDDINGS_MODEL`, routed
> through the LiteLLM gateway; default `playbook-embed`). If that setting is
> blank, the metric is skipped with a note; `faithfulness` still covers
> generation grounding.
