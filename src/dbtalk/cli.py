from __future__ import annotations

import io
import itertools
import os
import sys
import threading
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown

from dbtalk import agent


def _render(text: str) -> str:
    """Render markdown to an ANSI string. Console is deallocated on return, before shutdown."""
    buf = io.StringIO()
    Console(file=buf, force_terminal=True, color_system="truecolor").print(Markdown(text))
    return buf.getvalue()


def _run_with_spinner(fn, *args, **kwargs):
    """Run fn in a thread while showing a spinner on stderr. No Rich involved."""
    result_box = [None]
    error_box = [None]
    stop = threading.Event()

    def worker():
        try:
            result_box[0] = fn(*args, **kwargs)
        except Exception as exc:
            error_box[0] = exc
        finally:
            stop.set()

    def spin():
        for ch in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
            if stop.wait(0.1):
                break
            sys.stderr.write(f"\r{ch} Thinking...")
            sys.stderr.flush()
        sys.stderr.write("\r" + " " * 20 + "\r")
        sys.stderr.flush()

    worker_t = threading.Thread(target=worker, daemon=True)
    spin_t = threading.Thread(target=spin, daemon=True)
    worker_t.start()
    spin_t.start()
    worker_t.join()
    spin_t.join()

    if error_box[0] is not None:
        raise error_box[0]
    return result_box[0]



@click.group()
def cli() -> None:
    """dbtalk – ask natural language questions about your dbt project."""


@cli.command("ask")
@click.argument("question")
@click.option(
    "--manifest",
    required=True,
    type=click.Path(path_type=Path),
    help="Path to dbt manifest.json",
)
@click.option(
    "--provider",
    default="anthropic",
    type=click.Choice(["anthropic"], case_sensitive=False),
    help="LLM provider to use (default: anthropic)",
)
def ask(question: str, manifest: Path, provider: str) -> None:
    """Ask a natural language question about your dbt project."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        click.echo("Error: ANTHROPIC_API_KEY environment variable is not set.", err=True)
        sys.exit(1)

    if not manifest.exists():
        click.echo(f"Error: manifest.json not found at {manifest}", err=True)
        sys.exit(1)

    from dbtalk import agent as _agent

    try:
        if sys.stderr.isatty():
            answer = _run_with_spinner(_agent.run, question, manifest)
        else:
            answer = _agent.run(question, manifest)
    except ValueError as exc:
        click.echo(f"Manifest error: {exc}", err=True)
        sys.exit(2)
    except Exception as exc:
        click.echo(f"API error: {exc}", err=True)
        sys.exit(3)

    click.echo(_render(answer))
