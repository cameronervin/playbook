# Agent Eval Harness

Code-based evals for the agent layer. Tracks runs in Langfuse v3, executes
dataset items through the Langfuse Experiment Runner SDK, and scores with an
LLM-as-judge (every agent) plus Ragas retrieval/generation metrics (the KB-using
chains). The scaffold ships a single `example` agent; add more by writing a
`specs/<name>.py` and registering it in `specs/__init__.py`.

## Install

Installed on top of the backend env (shares `app.*`; not an isolated venv):

```bash
cd backend
uv sync --group evals          # runtime, dev, and eval deps
```

The `evals` dependency group pulls `ragas`, `langfuse`, and `click`. The harness modules
import these lazily, so `python -m compileall evals` succeeds even before the
group is installed.

## Run

Set in `.env`: `LANGFUSE_ENABLED=true`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_HOST`, `LITELLM_BASE_URL`, `LITELLM_API_KEY`, and `KB_PROVIDER_MODE`
(`local` for real RAG scoring; `mock` only smoke-tests the pipe).

Author the dataset + rubric YAMLs first (see `datasets/README.md`, `rubrics/README.md`).

```bash
cd backend
uv run --group evals python -m evals.cli sync-datasets  # mirror datasets into Langfuse
uv run --group evals python -m evals.cli run --agent example --max-concurrency 5
uv run --group evals python -m evals.cli run-all --max-concurrency 5
```

`--max-concurrency` controls concurrent dataset item execution per spec. It
defaults to `5`, accepts values from `1` through `50`, and can also be set with
`EVAL_MAX_CONCURRENCY=5`. `run-all` still runs specs one after another so total
LLM/KB load stays bounded; each spec's items run concurrently.

`--agent` choices: `example`.

> The CLI initialises Langfuse via `app.observability.langfuse_init`
> (`init_langfuse`, `is_langfuse_ready`, `shutdown_langfuse`) and the chain
> adapter optionally attaches a handler via `create_langfuse_handler`. Provide
> these in your app's observability layer — they are imported lazily, only when a
> command runs.

## Results & resilience

Every run writes a JSON + Markdown summary to `results/` (gitignored) for review
after the run — mean scores, threshold failures, and any isolated judging errors.
See `results/README.md`.

Failures are isolated: one item's agent crash, or one rubric's judge failure
(e.g. the judge model rejecting an oversized prompt), is logged and recorded in
the result's `errors` list rather than aborting the rest of the run or the rest
of `run-all`. To keep the judge prompt within the judge model's context window,
each prompt block (`input`/`output`/`trajectory`/`expected`) is truncated to a
character budget (`LLMJudge.block_char_budget`, default 24k chars; output gets 2×).

The legacy scaffold's KB-context capture uses a process-wide patch and is guarded
by a lock when `capture_kb=True`; real Playbook KB eval specs should use
per-item injected providers/source registries before relying on fully parallel
RAG-context capture.
