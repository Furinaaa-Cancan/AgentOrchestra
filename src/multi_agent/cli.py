"""CLI entry point — ma go / ma done / ma status / ma cancel / ma watch."""

from __future__ import annotations

import hashlib
import json
import sys
import time

import click

from multi_agent.config import store_db_path, workspace_dir
from multi_agent.workspace import (
    clear_inbox,
    clear_outbox,
    ensure_workspace,
    read_outbox,
    save_task_yaml,
)


def _thread_id(task_id: str) -> str:
    return task_id


def _make_config(task_id: str) -> dict:
    return {"configurable": {"thread_id": _thread_id(task_id)}}


def _generate_task_id(requirement: str) -> str:
    content = f"{requirement}-{time.time()}"
    h = hashlib.sha256(content.encode()).hexdigest()[:8]
    return f"task-{h}"


@click.group()
def main():
    """ma — Multi-Agent orchestration CLI."""
    pass


@main.command()
@click.argument("requirement")
@click.option("--skill", default="code-implement", help="Skill ID to use")
@click.option("--task-id", default=None, help="Override task ID")
@click.option("--builder", default="", help="IDE for builder role (e.g. windsurf, cursor, kiro)")
@click.option("--reviewer", default="", help="IDE for reviewer role (e.g. cursor, codex, kiro)")
@click.option("--retry-budget", default=2, type=int, help="Max retries")
@click.option("--timeout", default=1800, type=int, help="Timeout in seconds")
def go(requirement: str, skill: str, task_id: str | None, builder: str, reviewer: str, retry_budget: int, timeout: int):
    """Start a new task from a natural language requirement.

    Examples:
      ma go "实现 POST /users endpoint"
      ma go "Add auth middleware" --builder windsurf --reviewer cursor
      ma go "Fix login bug" --builder kiro --reviewer codex
    """
    from multi_agent.graph import compile_graph

    ensure_workspace()

    # A2: Check for existing active task — prevent silent collision
    app = compile_graph()
    existing = _detect_active_task(app)
    if existing:
        click.echo(f"⚠️  Task '{existing}' is still active.", err=True)
        click.echo(f"   Run `ma done` to finish it, or `ma cancel` to abort.", err=True)
        if not click.confirm("Start a new task anyway? (will NOT cancel the old one)"):
            sys.exit(1)

    task_id = task_id or _generate_task_id(requirement)

    # A6: Clear stale inbox/outbox from previous tasks
    for role in ("builder", "reviewer"):
        clear_inbox(role)
        clear_outbox(role)

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
        "builder_explicit": builder,
        "reviewer_explicit": reviewer,
        "conversation": [],
    }

    click.echo(f"🚀 Starting task: {task_id}")
    click.echo(f"   Skill: {skill}")
    click.echo(f"   Requirement: {requirement}")
    click.echo()

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
    _show_snapshot(app, config)


@main.command()
@click.option("--task-id", default=None, help="Task ID (auto-detect if only one active)")
@click.option("--file", "file_path", default=None, type=click.Path(exists=True), help="Read output from file")
def done(task_id: str | None, file_path: str | None):
    """Submit agent output and advance the graph.

    Reads from outbox/builder.json or outbox/reviewer.json (role-based),
    or from --file, or from stdin.
    """
    from multi_agent.graph import compile_graph

    app = compile_graph()

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

    # Determine current role and agent from interrupt metadata
    role = "builder"
    agent_id = "?"
    if snapshot.tasks and snapshot.tasks[0].interrupts:
        info = snapshot.tasks[0].interrupts[0].value
        role = info.get("role", "builder")
        agent_id = info.get("agent", "?")

    # Read output: --file > role-based outbox > stdin
    output_data = None

    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            output_data = json.load(f)
    else:
        # Role-based outbox: outbox/builder.json or outbox/reviewer.json
        output_data = read_outbox(role)

    if output_data is None:
        click.echo(f"📝 No output in outbox/{role}.json. Paste JSON (Ctrl-D to end):")
        raw = sys.stdin.read().strip()
        if raw:
            try:
                output_data = json.loads(raw)
            except json.JSONDecodeError as e:
                click.echo(f"❌ Invalid JSON: {e}", err=True)
                sys.exit(1)

    if output_data is None:
        click.echo(f"❌ No output found. Save to .multi-agent/outbox/{role}.json or use --file.", err=True)
        sys.exit(1)

    click.echo(f"📤 Submitting {role} output for task {task_id} (IDE: {agent_id})")

    from langgraph.types import Command
    from langgraph.errors import GraphInterrupt
    try:
        result = app.invoke(Command(resume=output_data), config)
    except GraphInterrupt:
        pass  # Normal — graph paused at next interrupt()

    # Mark task completed if graph finished
    snapshot = app.get_state(config)
    if snapshot and not snapshot.next:
        vals = snapshot.values or {}
        final = vals.get("final_status", "")
        if final:
            save_task_yaml(task_id, {"task_id": task_id, "status": final})

    _show_snapshot(app, config)


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
    current_role = vals.get("current_role", "?")
    click.echo(f"📊 Task: {task_id}")
    click.echo(f"   Current step: {current_role}")
    click.echo(f"   Builder:  {vals.get('builder_id', '?')}")
    click.echo(f"   Reviewer: {vals.get('reviewer_id', '?')}")
    click.echo(f"   Retry: {vals.get('retry_count', 0)}/{vals.get('retry_budget', 2)}")

    if vals.get("error"):
        click.echo(f"   ❌ Error: {vals['error']}")
    if vals.get("final_status"):
        click.echo(f"   🏁 Final: {vals['final_status']}")

    if snapshot.next:
        click.echo(f"   ⏸️  Waiting at: {snapshot.next[0]}")
        click.echo(f"   📄 Inbox: .multi-agent/inbox/{current_role}.md")
    else:
        click.echo("   ✅ Graph complete")

    dp = workspace_dir() / "TASK.md"
    if dp.exists():
        click.echo(f"\n📋 TASK.md: {dp}")


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


@main.command()
@click.option("--task-id", default=None)
@click.option("--interval", default=2.0, type=float, help="Poll interval in seconds")
def watch(task_id: str | None, interval: float):
    """Watch outbox/ for agent output and auto-submit.

    Polls outbox/builder.json or outbox/reviewer.json and runs `ma done`
    automatically when output appears. Useful for hands-free operation.
    """
    from multi_agent.graph import compile_graph
    from multi_agent.watcher import OutboxPoller

    app = compile_graph()

    if not task_id:
        task_id = _detect_active_task(app)
        if not task_id:
            click.echo("❌ No active task to watch.", err=True)
            sys.exit(1)

    config = _make_config(task_id)
    poller = OutboxPoller(poll_interval=interval)

    click.echo(f"👁️  Watching outbox/ for task {task_id} (poll every {interval}s)")
    click.echo("   Press Ctrl-C to stop.\n")

    from langgraph.types import Command
    from langgraph.errors import GraphInterrupt

    try:
        while True:
            snapshot = app.get_state(config)
            if not snapshot or not snapshot.next:
                vals = snapshot.values if snapshot else {}
                final = vals.get("final_status", "")
                if final:
                    save_task_yaml(task_id, {"task_id": task_id, "status": final})
                click.echo(f"🏁 Task finished. Status: {vals.get('final_status', 'done')}")
                break

            # Determine which role we're waiting for
            role = "builder"
            if snapshot.tasks and snapshot.tasks[0].interrupts:
                info = snapshot.tasks[0].interrupts[0].value
                role = info.get("role", "builder")

            for detected_role, data in poller.check_once():
                if detected_role == role:
                    click.echo(f"📥 Detected {role} output, auto-submitting...")
                    try:
                        app.invoke(Command(resume=data), config)
                    except GraphInterrupt:
                        pass
                    _show_snapshot(app, config)
                    break

            import time as _time
            _time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("\n⏹️  Watch stopped.")


def _show_snapshot(app, config):
    """Display current graph state after an invoke."""
    snapshot = app.get_state(config)
    if snapshot and snapshot.next:
        node = snapshot.next[0]
        click.echo(f"⏸️  Graph paused at: {node}")
        if snapshot.tasks and snapshot.tasks[0].interrupts:
            info = snapshot.tasks[0].interrupts[0].value
            role = info.get("role", "?")
            agent = info.get("agent", "?")
            click.echo(f"   Role: {role}")
            click.echo(f"   IDE:  {agent}")
            click.echo(f"   Inbox: .multi-agent/inbox/{role}.md")
        click.echo()
        click.echo("📋 Next steps:")
        click.echo("   1. Open the inbox file in your IDE (or reference via @file)")
        click.echo("   2. Let the AI assistant work on it")
        click.echo("   3. Run: ma done")
    else:
        vals = snapshot.values if snapshot else {}
        status = vals.get("final_status", vals.get("error", "unknown"))
        click.echo(f"🏁 Task finished. Status: {status}")


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
    return None


if __name__ == "__main__":
    main()
