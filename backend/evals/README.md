# Agent Eval Harness

Code-based evals for the Playbook agent layer. Tracks runs in Langfuse v3,
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
(`local` for real RAG scoring; `mock` only smoke-tests the pipe).

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
uv run --group evals python -m evals.cli run-all --strict --max-concurrency 5
```

`--max-concurrency` controls concurrent dataset item execution per spec. It
defaults to `5`, accepts values from `1` through `50`, and can also be set with
`EVAL_MAX_CONCURRENCY=5`. `run-all` still runs specs one after another so total
LLM/KB load stays bounded; each spec's items run concurrently.

`--agent` choices: `athlete_chat`, `admin_chat`, `dashboard_insights`,
`conversation_title`.

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
