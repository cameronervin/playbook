# Agent Eval Harness

Code-based evals for the Playbook agent layer. Tracks runs in Langfuse v4,
executes dataset items through the Langfuse Experiment Runner SDK, and scores
with deterministic release gates, an LLM-as-judge for qualitative criteria, and
Ragas retrieval/generation metrics for KB-using chains.

## Install

Installed on top of the backend env (shares `app.*`; not an isolated venv):

```bash
cd backend
uv sync --group evals          # runtime, dev, and eval deps
```

Langfuse is a backend runtime dependency because the API and backend Celery
workers can attach runtime traces. The `evals` dependency group adds `ragas` and
`click`; harness modules import eval-only dependencies lazily, so
`python -m compileall evals` succeeds even before the group is installed.

## Run

Set in `.env`: `LANGFUSE_ENABLED=true`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_BASE_URL`, `LITELLM_BASE_URL`, `LITELLM_API_KEY`, and `KB_PROVIDER_MODE`
(`local` for real RAG scoring; `mock` only smoke-tests the pipe). For strict
RAG scoring, prefer a scoped `EVAL_LITELLM_API_KEY` with access to
`playbook-chat`, `playbook-fast`, and `playbook-embed`; the harness falls back
to `LITELLM_API_KEY` when the eval key is blank. `EVAL_EMBEDDINGS_MODEL`
defaults to the LiteLLM alias `playbook-embed`.

Author or update the dataset + rubric YAMLs first (see `datasets/README.md`,
`rubrics/README.md`). Offline dataset validation does not require Langfuse:

```bash
cd backend
uv run --group evals python -m evals.cli release-checks     # deterministic release gates
uv run --group evals python -m evals.cli validate-datasets
uv run --group evals python -m evals.cli sync-datasets  # mirror datasets into Langfuse
uv run --group evals python -m evals.cli run --agent athlete_chat --max-concurrency 5
uv run --group evals python -m evals.cli run --agent admin_chat --max-concurrency 5
uv run --group evals python -m evals.cli run --agent dashboard_insights --max-concurrency 5
DEBUG=true RAGAS_DO_NOT_TRACK=true uv run --group evals python -m evals.cli run-all --strict --max-concurrency 5
```

`--max-concurrency` controls concurrent dataset item execution per spec. It
defaults to `5`, accepts values from `1` through `50`, and can also be set with
`EVAL_MAX_CONCURRENCY=5`. `run-all` still runs specs one after another so total
LLM/KB load stays bounded; each spec's items run concurrently.

`--agent` choices: `athlete_chat`, `admin_chat`, `dashboard_insights`,
`conversation_title`.

The runner uses the current Langfuse v4 `run_experiment(data=dataset.items, ...)`
API and falls back to the legacy `dataset=` keyword for older SDKs.
The Ragas judge sets `RAGAS_DO_NOT_TRACK=true` before importing Ragas so release
evals do not make Ragas usage-telemetry calls.

`release-checks` is offline and does not initialize Langfuse. It validates
dataset YAML, the non-secret LiteLLM virtual-key budget/rate policy manifest,
runtime copy for protected university affiliation claims, observability/redaction
anchors, and production rate-limit env posture. The broader release wrapper is:

```bash
./deploy/scripts/release-validate.sh
./deploy/scripts/release-validate.sh --live-evals   # also run strict Langfuse evals
```

`athlete_chat` runs deterministic retrieval/citation/behavior/privacy release
gates, LLM answer-quality judging, and Ragas metrics. `admin_chat` runs
deterministic behavior/reference/privacy gates plus LLM qualitative judging.
`dashboard_insights` remains a deterministic structural golden spec for seeded
analytics windows. `conversation_title` covers compact first-turn title quality
and privacy.

## Release thresholds

Release thresholds are target gates, not baseline scores. Do not lower them to
make weak current behavior pass; fix prompts, adapters, fixtures, or product
behavior and rerun the full strict suite.

- `athlete_chat`: retrieval hit `0.85`; citation integrity, source freshness,
  and privacy leakage `1.0`; expected behavior `0.95`; athlete accuracy `4.25`;
  concision and warmth `4.0`; context precision `0.75`; context recall `0.80`;
  faithfulness `0.90`; answer relevancy `0.80`.
- `admin_chat`: expected behavior `0.95`; reference integrity and privacy
  leakage `1.0`; usefulness and specificity `4.0`; scope control `4.25`.
- `dashboard_insights`: all deterministic structural gates `1.0`.
- `conversation_title`: expected answer `0.9`; privacy leakage `1.0`; title
  relevance and brevity `4.0`; title privacy `4.5`.

## Latest calibration evidence

- 2026-07-02: `uv run --group evals pytest tests/unit/evals -q` passed
  (`55 passed`), `validate-datasets` returned `datasets valid`, and
  `release-checks` returned `PASS release checks (0 issue(s))`.
- 2026-07-02: focused live runs passed through Langfuse v4:
  `dashboard_insights-2026-07-02T18:18:24+00:00` and
  `conversation_title-2026-07-02T18:19:29+00:00`. The title run passed after
  prompt tightening with `expected_answer: 1.000`, `privacy_leakage: 1.000`,
  `title_brevity: 5.000`, `title_privacy: 5.000`, and
  `title_relevance: 4.667`.
- 2026-07-02: the full strict suite was attempted with
  `DEBUG=true RAGAS_DO_NOT_TRACK=true uv run --group evals python -m evals.cli run-all --strict --max-concurrency 5`;
  `athlete_chat-nightly-20260702` wrote result artifacts but failed strict
  thresholds and exposed one repeated `search_conversation_files` loop-guard
  error on a legal-boundary item with no ready uploaded files. Athlete chat
  prompt/tool guidance now mirrors the admin-chat stop criteria. A later
  `admin_chat` run-all phase hit async DB/event-loop concurrency during seeding,
  so keep the release eval gate open until the full suite completes cleanly.

> The CLI initialises Langfuse via `app.observability.langfuse_init`
> (`init_langfuse`, `is_langfuse_ready`, `shutdown_langfuse`) and the chain
> adapter optionally attaches a handler via `create_langfuse_handler`. Provide
> these in your app's observability layer — they are imported lazily, only when a
> command runs.

## Results & resilience

Every run writes a JSON + Markdown summary to `results/` (gitignored) for review
after the run: mean scores, threshold failures, run metadata, per-item scores,
and isolated judging errors. See `results/README.md`.

Failures are isolated so one item's agent crash or one rubric's judge failure is
logged and recorded in the result's `errors` list rather than aborting the rest
of the run. Isolated errors fail the aggregate release gate by default, and the
CLI exits non-zero when thresholds fail. To keep the judge prompt within the
judge model's context window,
each prompt block (`input`/`output`/`trajectory`/`expected`) is truncated to a
character budget (`LLMJudge.block_char_budget`, default 24k chars; output gets 2×).

Playbook executor specs auto-seed synthetic org/user/conversation/admin rows
when a YAML item does not already include executor IDs. If `retrieved_source_ids`
is present, the athlete-chat adapter uses the curated KB fixture chunks and
records them into `GraphRun.events` for deterministic and Ragas scoring. Inject
a real KB provider/seeder when you want the same specs to validate a populated
KB-service environment. The legacy example adapter is retained only as scaffold
reference and is not part of release `run-all`.
