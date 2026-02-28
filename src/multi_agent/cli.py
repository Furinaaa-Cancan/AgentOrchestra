"""CLI entry point — ma go / ma done / ma status / ma cancel."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import click

from multi_agent.config import store_db_path, workspace_dir
from multi_agent.workspace import (
    ensure_workspace,
    read_outbox,
    save_task_yaml,
)


def _thread_id(task_id: str) -> str:
    return task_id


def _make_config(task_id: str) -> dict:
    return {"configurable": {"thread_id": _thread_id(task_id)}}


def _generate_task_id(requirement: str) -> str:
    h = hashlib.sha256(requirement.encode()).hexdigest()[:8]
    return f"task-{h}"


@click.group()
def main():
    """ma — Multi-Agent orchestration CLI."""
    pass


@main.command()
@click.argument("requirement")
@click.option("--skill", default="code-implement", help="Skill ID to use")
@click.option("--task-id", default=None, help="Override task ID")
@click.option("--retry-budget", default=2, type=int, help="Max retries")
@click.option("--timeout", default=1800, type=int, help="Timeout in seconds")
def go(requirement: str, skill: str, task_id: str | None, retry_budget: int, timeout: int):
    """Start a new task from a natural language requirement.

    Example: ma go "实现 POST /users endpoint" --skill code-implement
    """
    from multi_agent.graph import compile_graph

    ensure_workspace()

    task_id = task_id or _generate_task_id(requirement)

    initial_state = {
        "task_id": task_id,
        "requirement": requirement,
        "skill_id": skill,
        "done_criteria": [requirement],
        "expected_checks": ["lint", "unit_test"],
        "timeout_sec": timeout,
        "retry_budget": retry_budget,
        "retry_count": 0,
        "input_payload": {"requirement": requirement},
        "conversation": [],
    }

    click.echo(f"🚀 Starting task: {task_id}")
    click.echo(f"   Skill: {skill}")
    click.echo(f"   Requirement: {requirement}")
    click.echo()

    app = compile_graph()
    config = _make_config(task_id)

    # Save task marker for auto-detection
    save_task_yaml(task_id, {"task_id": task_id, "skill": skill, "status": "active"})

    # Run until first interrupt (plan → build interrupt)
    from langgraph.errors import GraphInterrupt
    try:
        result = app.invoke(initial_state, config)
    except GraphInterrupt:
        pass  # Normal — graph paused at interrupt()

    # Show next step
    snapshot = app.get_state(config)
    if snapshot and snapshot.next:
        node = snapshot.next[0]
        click.echo(f"⏸️  Graph paused at: {node}")
        if snapshot.tasks:
            interrupt_val = snapshot.tasks[0].interrupts
            if interrupt_val:
                info = interrupt_val[0].value
                click.echo(f"   Agent: {info.get('agent', '?')}")
                click.echo(f"   Inbox: {info.get('inbox', '?')}")
        click.echo()
        click.echo("📋 Next steps:")
        click.echo("   1. Open the inbox file in your IDE")
        click.echo("   2. Let the agent work")
        click.echo("   3. Run: ma done")
    else:
        click.echo("✅ Task completed (or errored). Run `ma status` to check.")


@main.command()
@click.option("--task-id", default=None, help="Task ID (auto-detect if only one active)")
@click.option("--file", "file_path", default=None, type=click.Path(exists=True), help="Read output from file")
def done(task_id: str | None, file_path: str | None):
    """Submit agent output and advance the graph.

    Reads from --file, stdin, or auto-detects from outbox/.
    """
    from multi_agent.graph import compile_graph

    app = compile_graph()

    # Auto-detect task_id from active checkpoints if not specified
    if not task_id:
        task_id = _detect_active_task(app)
        if not task_id:
            click.echo("❌ No active task found. Specify --task-id.", err=True)
            sys.exit(1)

    config = _make_config(task_id)
    snapshot = app.get_state(config)

    if not snapshot or not snapshot.next:
        click.echo("❌ No pending interrupt for this task.", err=True)
        sys.exit(1)

    # Determine which agent we're waiting for
    agent_id = None
    if snapshot.tasks and snapshot.tasks[0].interrupts:
        info = snapshot.tasks[0].interrupts[0].value
        agent_id = info.get("agent")

    # Read agent output
    output_data = None

    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            output_data = json.load(f)
    elif agent_id:
        output_data = read_outbox(agent_id)

    if output_data is None:
        # Try reading from stdin
        click.echo("📝 Paste agent JSON output (Ctrl-D to end):")
        raw = sys.stdin.read().strip()
        if raw:
            try:
                output_data = json.loads(raw)
            except json.JSONDecodeError as e:
                click.echo(f"❌ Invalid JSON: {e}", err=True)
                sys.exit(1)

    if output_data is None:
        click.echo("❌ No output found. Check outbox or provide via --file / stdin.", err=True)
        sys.exit(1)

    click.echo(f"📤 Submitting output for task {task_id} (agent: {agent_id})")

    # Resume the graph with the agent output
    from langgraph.types import Command
    from langgraph.errors import GraphInterrupt
    try:
        result = app.invoke(Command(resume=output_data), config)
    except GraphInterrupt:
        pass  # Normal — graph paused at next interrupt()

    # Check new state
    snapshot = app.get_state(config)
    if snapshot and snapshot.next:
        node = snapshot.next[0]
        click.echo(f"⏸️  Graph paused at: {node}")
        if snapshot.tasks and snapshot.tasks[0].interrupts:
            info = snapshot.tasks[0].interrupts[0].value
            click.echo(f"   Agent: {info.get('agent', '?')}")
            click.echo(f"   Inbox: {info.get('inbox', '?')}")
        click.echo("\n📋 Run `ma done` again after the agent completes.")
    else:
        vals = snapshot.values if snapshot else {}
        status = vals.get("final_status", vals.get("error", "unknown"))
        click.echo(f"🏁 Task finished. Status: {status}")


@main.command()
@click.option("--task-id", default=None, help="Task ID")
def status(task_id: str | None):
    """Show current task status."""
    from multi_agent.graph import compile_graph

    app = compile_graph()

    if not task_id:
        task_id = _detect_active_task(app)
        if not task_id:
            click.echo("No active tasks.")
            return

    config = _make_config(task_id)
    snapshot = app.get_state(config)

    if not snapshot:
        click.echo(f"No state found for task {task_id}")
        return

    vals = snapshot.values
    click.echo(f"📊 Task: {task_id}")
    click.echo(f"   Role: {vals.get('current_role', '?')}")
    click.echo(f"   Agent: {vals.get('current_agent', '?')}")
    click.echo(f"   Retry: {vals.get('retry_count', 0)}/{vals.get('retry_budget', 2)}")

    if vals.get("error"):
        click.echo(f"   ❌ Error: {vals['error']}")
    if vals.get("final_status"):
        click.echo(f"   🏁 Final: {vals['final_status']}")

    if snapshot.next:
        click.echo(f"   ⏸️  Waiting at: {snapshot.next[0]}")
    else:
        click.echo("   ✅ Graph complete")

    # Show dashboard path
    dp = workspace_dir() / "dashboard.md"
    if dp.exists():
        click.echo(f"\n📋 Dashboard: {dp}")


@main.command()
@click.option("--task-id", default=None)
@click.option("--reason", default="user cancelled")
def cancel(task_id: str | None, reason: str):
    """Cancel the current task."""
    from multi_agent.graph import compile_graph

    app = compile_graph()

    if not task_id:
        task_id = _detect_active_task(app)
        if not task_id:
            click.echo("No active task to cancel.")
            return

    # Mark task YAML as cancelled so auto-detect skips it
    save_task_yaml(task_id, {"task_id": task_id, "status": "cancelled", "reason": reason})

    # Update the dashboard
    from multi_agent.dashboard import write_dashboard
    write_dashboard(
        task_id=task_id,
        done_criteria=[],
        current_agent="",
        current_role="cancelled",
        conversation=[],
        error=f"已取消: {reason}",
    )
    click.echo(f"🛑 Task {task_id} marked as cancelled: {reason}")


def _detect_active_task(app) -> str | None:
    """Detect the active task from task YAML markers in workspace."""
    from multi_agent.config import tasks_dir
    td = tasks_dir()
    if not td.exists():
        return None
    yamls = sorted(td.glob("*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)
    for yf in yamls:
        try:
            import yaml
            data = yaml.safe_load(yf.read_text(encoding="utf-8")) or {}
            if data.get("status") == "active":
                return yf.stem
        except Exception:
            continue
    # Fallback: return most recent
    if yamls:
        return yamls[0].stem
    return None


if __name__ == "__main__":
    main()
