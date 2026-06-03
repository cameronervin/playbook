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
from datetime import datetime

import click

from evals.core.runner import run_spec
from evals.core.sync import sync_dataset_to_langfuse
from evals.specs import REGISTRY

# Match the app's Windows event-loop policy before any asyncio.run.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _ensure_langfuse() -> None:
    """Initialise Langfuse from settings; abort with a clear message if not ready."""
    from app.observability.langfuse_init import init_langfuse, is_langfuse_ready

    init_langfuse()
    if not is_langfuse_ready():
        raise click.ClickException(
            "Langfuse is not ready. Set LANGFUSE_ENABLED=true and provide "
            "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST in your .env."
        )


def _shutdown_langfuse() -> None:
    from app.observability.langfuse_init import shutdown_langfuse

    shutdown_langfuse()


def dataset_exists(spec: object) -> bool:
    """Whether a spec's dataset YAML is present (not-yet-authored specs are skipped)."""
    return os.path.exists(getattr(spec, "dataset_path"))


@click.group()
def cli() -> None:
    """Agent evaluation harness."""


@cli.command()
@click.option("--agent", type=click.Choice(list(REGISTRY)), required=True)
@click.option("--run-name", default=None, help="Optional explicit Langfuse run name.")
def run(agent: str, run_name: str | None) -> None:
    """Run one agent's evals and print PASS/FAIL with mean scores."""
    _ensure_langfuse()
    try:
        result = asyncio.run(run_spec(REGISTRY[agent], run_name=run_name))
        click.echo(result.summary())
    finally:
        _shutdown_langfuse()


@cli.command(name="run-all")
def run_all() -> None:
    """Run every registered agent (e.g. nightly)."""
    _ensure_langfuse()

    async def _all() -> None:
        stamp = datetime.now().strftime("%Y%m%d")
        for name, spec in REGISTRY.items():
            # Skip not-yet-authored datasets so one missing spec can't abort the
            # whole nightly run (run_spec syncs the dataset, which would 404).
            if not dataset_exists(spec):
                click.echo(f"skipped {name}: no dataset at {spec.dataset_path}")
                continue
            result = await run_spec(spec, run_name=f"{name}-nightly-{stamp}")
            click.echo(result.summary())

    try:
        asyncio.run(_all())
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


if __name__ == "__main__":
    cli()
