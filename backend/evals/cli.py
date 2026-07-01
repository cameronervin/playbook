"""Single entry point for the eval harness.

    python -m evals.cli sync-datasets            # push YAML datasets into Langfuse
    python -m evals.cli run --agent example
    python -m evals.cli run-all                   # every registered agent

``run_spec`` is async, so ``asyncio.run`` lives only here. Each command
initialises Langfuse from settings first and flushes/shuts down on exit so
queued scores are sent before the process ends.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

import click

from evals.core.runner import DEFAULT_MAX_CONCURRENCY, run_spec
from evals.core.sync import sync_dataset_to_langfuse
from evals.specs import REGISTRY

# Match the app's Windows event-loop policy before any asyncio.run.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _ensure_langfuse() -> None:
    """Initialise Langfuse from settings; abort with a clear message if not ready."""
    from app.observability.langfuse_init import init_langfuse, is_langfuse_ready  # noqa: I001, PLC0415

    init_langfuse()
    if not is_langfuse_ready():
        raise click.ClickException(
            "Langfuse is not ready. Set LANGFUSE_ENABLED=true and provide "
            "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL in "
            "your .env."
        )


def _shutdown_langfuse() -> None:
    from app.observability.langfuse_init import shutdown_langfuse  # noqa: PLC0415

    shutdown_langfuse()


def dataset_exists(spec: object) -> bool:
    """Whether a spec's dataset YAML is present (not-yet-authored specs are skipped)."""
    return os.path.exists(getattr(spec, "dataset_path"))  # noqa: B009


def validate_specs(specs: list[object]) -> list[object]:
    """Validate on-disk eval datasets without initializing Langfuse."""
    from evals.core.validation import validate_specs as _validate_specs  # noqa: PLC0415

    return list(_validate_specs(specs))


def _raise_if_failed(result: object) -> None:
    if getattr(result, "passed", False):
        return
    failures = list(getattr(result, "failures", []) or [])
    message = "\n".join(failures) if failures else "eval run failed"
    raise click.ClickException(message)


@click.group()
def cli() -> None:
    """Agent evaluation harness."""


@cli.command()
@click.option("--agent", type=click.Choice(list(REGISTRY)), required=True)
@click.option("--run-name", default=None, help="Optional explicit Langfuse run name.")
@click.option(
    "--max-concurrency",
    envvar="EVAL_MAX_CONCURRENCY",
    type=click.IntRange(1, 50),
    default=DEFAULT_MAX_CONCURRENCY,
    show_default=True,
    help="Maximum concurrent dataset item executions for this spec.",
)
def run(agent: str, run_name: str | None, max_concurrency: int) -> None:
    """Run one agent's evals and print PASS/FAIL with mean scores."""
    _ensure_langfuse()
    try:
        result = asyncio.run(
            run_spec(
                REGISTRY[agent],
                run_name=run_name,
                max_concurrency=max_concurrency,
            )
        )
        click.echo(result.summary())
        _raise_if_failed(result)
    finally:
        _shutdown_langfuse()


@cli.command(name="run-all")
@click.option(
    "--max-concurrency",
    envvar="EVAL_MAX_CONCURRENCY",
    type=click.IntRange(1, 50),
    default=DEFAULT_MAX_CONCURRENCY,
    show_default=True,
    help="Maximum concurrent dataset item executions per spec.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Fail on missing datasets or any failed spec; use for release gates.",
)
def run_all(max_concurrency: int, strict: bool) -> None:
    """Run every registered agent (e.g. nightly)."""
    _ensure_langfuse()

    async def _all() -> list[str]:
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        failures: list[str] = []
        for name, spec in REGISTRY.items():
            # Skip not-yet-authored datasets so one missing spec can't abort the
            # whole nightly run (run_spec syncs the dataset, which would 404).
            if not dataset_exists(spec):
                message = f"missing {name}: no dataset at {spec.dataset_path}"
                if strict:
                    click.echo(message)
                    failures.append(message)
                else:
                    click.echo(f"skipped {name}: no dataset at {spec.dataset_path}")
                continue
            result = await run_spec(
                spec,
                run_name=f"{name}-nightly-{stamp}",
                max_concurrency=max_concurrency,
            )
            click.echo(result.summary())
            if strict and not result.passed:
                failures.append(f"{name} failed release thresholds")
        return failures

    try:
        failures = asyncio.run(_all())
        if failures:
            raise click.ClickException("\n".join(failures))
    finally:
        _shutdown_langfuse()


@cli.command(name="sync-datasets")
@click.option("--agent", type=click.Choice(list(REGISTRY)), default=None,
              help="Sync one agent's dataset; default syncs all.")
def sync_datasets(agent: str | None) -> None:
    """Mirror on-disk YAML datasets into Langfuse (idempotent)."""
    _ensure_langfuse()
    specs = [REGISTRY[agent]] if agent else list(REGISTRY.values())
    try:
        for spec in specs:
            # Skip not-yet-authored datasets when syncing all; a single --agent
            # still surfaces the missing file as an error.
            if agent is None and not dataset_exists(spec):
                click.echo(f"skipped {spec.name}: no dataset at {spec.dataset_path}")
                continue
            count = sync_dataset_to_langfuse(spec.dataset_path, spec.name)
            click.echo(f"synced {spec.name}: {count} items")
    finally:
        _shutdown_langfuse()


@cli.command(name="validate-datasets")
@click.option(
    "--agent",
    type=click.Choice(list(REGISTRY)),
    default=None,
    help="Validate one agent's dataset; default validates all registered specs.",
)
def validate_datasets(agent: str | None) -> None:
    """Validate local eval datasets without Langfuse credentials."""
    specs = [REGISTRY[agent]] if agent else list(REGISTRY.values())
    issues = validate_specs(specs)
    if not issues:
        click.echo("datasets valid")
        return

    for issue in issues:
        severity = getattr(issue, "severity", "error")
        path = getattr(issue, "path", "?")
        message = getattr(issue, "message", str(issue))
        click.echo(f"{severity}: {path}: {message}")
    raise click.ClickException(f"{len(issues)} dataset validation issue(s)")


if __name__ == "__main__":
    cli()
