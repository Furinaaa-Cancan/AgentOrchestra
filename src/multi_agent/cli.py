"""CLI entry point — ma go / ma done / ma status / ma cancel / ma watch."""

from __future__ import annotations

import hashlib
import json
import sys
import time

import click

from multi_agent.workspace import (
    acquire_lock,
    clear_runtime,
    ensure_workspace,
    read_lock,
    read_outbox,
    release_lock,
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
    """ma — Multi-Agent 协作 CLI. 一条命令协调多个 IDE AI."""
    pass


@main.command()
@click.argument("requirement")
@click.option("--skill", default="code-implement", help="Skill ID to use")
@click.option("--task-id", default=None, help="Override task ID")
@click.option("--builder", default="", help="IDE for builder role (e.g. windsurf, cursor, kiro)")
@click.option("--reviewer", default="", help="IDE for reviewer role (e.g. cursor, codex, kiro)")
@click.option("--retry-budget", default=2, type=int, help="Max retries")
@click.option("--timeout", default=1800, type=int, help="Timeout in seconds")
@click.option("--no-watch", is_flag=True, default=False, help="Don't auto-watch (exit after start)")
def go(requirement: str, skill: str, task_id: str | None, builder: str, reviewer: str, retry_budget: int, timeout: int, no_watch: bool):
    """Start a new task and watch for IDE output.

    Starts the task, then auto-watches outbox/ for agent output.
    When the IDE AI saves its result, the orchestrator auto-advances.

    Usage:
      1. Run: ma go "your requirement"
      2. Open .multi-agent/TASK.md in your IDE
      3. Watch the terminal — it handles the rest

    Examples:
      ma go "实现 POST /users endpoint"
      ma go "Add auth middleware" --builder windsurf --reviewer cursor
      ma go "Fix login bug" --no-watch
    """
    from multi_agent.graph import compile_graph

    ensure_workspace()

    # Enforce single active task — prevent data conflicts
    app = compile_graph()
    locked = read_lock()
    if locked:
        click.echo(f"❌ 任务 '{locked}' 正在进行中。", err=True)
        click.echo(f"   先完成或取消当前任务:", err=True)
        click.echo(f"   • ma cancel   — 取消当前任务", err=True)
        click.echo(f"   • ma done     — 手动提交结果", err=True)
        click.echo(f"   • ma status   — 查看任务状态", err=True)
        sys.exit(1)

    task_id = task_id or _generate_task_id(requirement)

    # Clear ALL shared runtime files to prevent stale data leaking
    clear_runtime()

    # Acquire lock — marks this task as the sole active task
    acquire_lock(task_id)

    initial_state = {
        "task_id": task_id,
        "requirement": requirement,
        "skill_id": skill,
        "done_criteria": [requirement],
        "timeout_sec": timeout,
        "retry_budget": retry_budget,
        "retry_count": 0,
        "input_payload": {"requirement": requirement},
        "builder_explicit": builder,
        "reviewer_explicit": reviewer,
        "conversation": [],
    }

    click.echo(f"🚀 Task: {task_id}")
    click.echo(f"   {requirement}")
    click.echo()

    config = _make_config(task_id)

    # Run until first interrupt (plan → build interrupt)
    from langgraph.errors import GraphInterrupt
    try:
        app.invoke(initial_state, config)
    except GraphInterrupt:
        pass
    except FileNotFoundError as e:
        release_lock()
        click.echo(f"❌ {e}", err=True)
        click.echo(f"   确认你在 AgentOrchestra 项目根目录运行, 且 skills/ 和 agents/ 存在。", err=True)
        click.echo(f"   或设置 MA_ROOT 环境变量指向项目根目录。", err=True)
        save_task_yaml(task_id, {"task_id": task_id, "status": "failed", "error": str(e)})
        sys.exit(1)
    except ValueError as e:
        release_lock()
        click.echo(f"❌ {e}", err=True)
        click.echo(f"   检查 agents/agents.yaml 配置是否正确。", err=True)
        save_task_yaml(task_id, {"task_id": task_id, "status": "failed", "error": str(e)})
        sys.exit(1)
    except Exception as e:
        release_lock()
        click.echo(f"❌ Task failed to start: {e}", err=True)
        save_task_yaml(task_id, {"task_id": task_id, "status": "failed", "error": str(e)})
        sys.exit(1)

    save_task_yaml(task_id, {"task_id": task_id, "skill": skill, "status": "active"})

    # Show what to do
    _show_waiting(app, config)

    if no_watch:
        click.echo("\n📌 Run `ma done` after the IDE finishes, or `ma watch` to auto-detect.")
        return

    # Auto-watch mode (default) — poll outbox and auto-submit
    _run_watch_loop(app, config, task_id)


@main.command()
@click.option("--task-id", default=None, help="Task ID (auto-detect if only one active)")
@click.option("--file", "file_path", default=None, type=click.Path(exists=True), help="Read output from file")
def done(task_id: str | None, file_path: str | None):
    """手动提交 IDE 输出并推进任务.

    自动从 .multi-agent/outbox/ 读取当前角色的 JSON 输出,
    也可用 --file 指定文件, 或从 stdin 粘贴.
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
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                output_data = json.load(f)
        except json.JSONDecodeError as e:
            click.echo(f"❌ Invalid JSON in {file_path}: {e}", err=True)
            sys.exit(1)
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
    except Exception as e:
        release_lock()
        clear_runtime()
        click.echo(f"❌ Graph error during resume: {e}", err=True)
        save_task_yaml(task_id, {"task_id": task_id, "status": "failed", "error": str(e)})
        sys.exit(1)

    # Mark task completed if graph finished
    snapshot = app.get_state(config)
    if snapshot and not snapshot.next:
        vals = snapshot.values or {}
        final = vals.get("final_status", "")
        if final:
            save_task_yaml(task_id, {"task_id": task_id, "status": final})
        release_lock()
        clear_runtime()

    _show_waiting(app, config)


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
    locked = read_lock()

    click.echo(f"📊 Task: {task_id}")
    click.echo(f"   Step:     {current_role}")
    click.echo(f"   Builder:  {vals.get('builder_id', '?')}")
    click.echo(f"   Reviewer: {vals.get('reviewer_id', '?')}")
    click.echo(f"   Retry:    {vals.get('retry_count', 0)}/{vals.get('retry_budget', 2)}")
    click.echo(f"   Lock:     {'🔒 ' + locked if locked else '🔓 none'}")

    if vals.get("error"):
        click.echo(f"   ❌ Error: {vals['error']}")
    if vals.get("final_status"):
        click.echo(f"   🏁 Final: {vals['final_status']}")

    if snapshot.next:
        agent = vals.get("builder_id" if current_role == "builder" else "reviewer_id", "?")
        from multi_agent.driver import get_agent_driver
        drv = get_agent_driver(agent)
        mode = "🤖 auto" if drv["driver"] == "cli" else "📋 manual"
        click.echo(f"   ⏸️  Waiting: {current_role} ({agent}) [{mode}]")
        if drv["driver"] != "cli":
            click.echo(f'   📋 在 {agent} IDE 里说: "帮我完成 @.multi-agent/TASK.md 里的任务"')
    else:
        click.echo("   ✅ Graph complete")


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
            # Fallback: check for orphaned lock (e.g. after kill -9)
            task_id = read_lock()
            if not task_id:
                click.echo("No active task to cancel.")
                return
            click.echo(f"⚠️  发现孤立锁 (task: {task_id}), 正在清理…")

    # Mark task YAML as cancelled so auto-detect skips it
    save_task_yaml(task_id, {"task_id": task_id, "status": "cancelled", "reason": reason})

    # Release lock + clean shared files
    release_lock()
    clear_runtime()

    click.echo(f"🛑 Task {task_id} cancelled: {reason}")


@main.command()
@click.option("--task-id", default=None)
@click.option("--interval", default=2.0, type=float, help="Poll interval in seconds")
def watch(task_id: str | None, interval: float):
    """自动检测 IDE 输出并推进任务.

    恢复之前中断的自动检测.
    适用于 `ma go --no-watch` 启动的任务.
    """
    from multi_agent.graph import compile_graph

    app = compile_graph()

    if not task_id:
        task_id = _detect_active_task(app)
        if not task_id:
            click.echo("❌ No active task to watch.", err=True)
            sys.exit(1)

    # Validate lock consistency — prevent watching wrong task
    locked = read_lock()
    if locked and locked != task_id:
        click.echo(f"❌ 锁文件指向 '{locked}', 但你要 watch '{task_id}'。", err=True)
        click.echo(f"   同时只能有一个活跃任务。", err=True)
        sys.exit(1)
    if not locked:
        acquire_lock(task_id)

    config = _make_config(task_id)
    snapshot = app.get_state(config)
    if not snapshot or not snapshot.next:
        vals = snapshot.values if snapshot else {}
        final = vals.get("final_status", "done")
        release_lock()
        clear_runtime()
        click.echo(f"✅ Task {task_id} already finished — {final}")
        return
    _show_waiting(app, config)
    _run_watch_loop(app, config, task_id, interval=interval)


def _show_waiting(app, config):
    """Show current waiting state — auto-spawn CLI agents or show manual instructions."""
    snapshot = app.get_state(config)
    if not snapshot or not snapshot.next:
        vals = snapshot.values if snapshot else {}
        final = vals.get("final_status", "")
        error = vals.get("error", "")
        if final in ("approved", ""):
            click.echo(f"✅ Task finished. Status: {final or 'done'}")
        else:
            click.echo(f"❌ Task finished. Status: {final}{' — ' + error if error else ''}")
        return

    role = "builder"
    agent = "?"
    if snapshot.tasks and snapshot.tasks[0].interrupts:
        info = snapshot.tasks[0].interrupts[0].value
        role = info.get("role", "builder")
        agent = info.get("agent", "?")

    step_label = "Build" if role == "builder" else "Review"

    # Check if agent has CLI driver → auto-spawn
    from multi_agent.driver import get_agent_driver, spawn_cli_agent
    drv = get_agent_driver(agent)
    if drv["driver"] == "cli" and drv["command"]:
        vals = snapshot.values or {}
        timeout = vals.get("timeout_sec", 600)
        click.echo(f"🤖 [{step_label}] 自动调用 {agent} CLI…")
        spawn_cli_agent(agent, role, drv["command"], timeout_sec=timeout)
    else:
        click.echo(f"📋 [{step_label}] 在 {agent} IDE 里对 AI 说:")
        click.echo(f'   "帮我完成 @.multi-agent/TASK.md 里的任务"')
    click.echo()


def _run_watch_loop(app, config, task_id: str, interval: float = 2.0):
    """Shared watch loop — polls outbox/ and auto-submits output."""
    from multi_agent.watcher import OutboxPoller
    from langgraph.types import Command
    from langgraph.errors import GraphInterrupt

    poller = OutboxPoller(poll_interval=interval)
    start_time = time.time()

    click.echo(f"👁️  等待 IDE 完成任务… (Ctrl-C 停止)")
    click.echo()

    try:
        while True:
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)

            snapshot = app.get_state(config)
            if not snapshot or not snapshot.next:
                vals = snapshot.values if snapshot else {}
                final = vals.get("final_status", "")
                if final:
                    save_task_yaml(task_id, {"task_id": task_id, "status": final})
                release_lock()
                clear_runtime()
                if final in ("approved", ""):
                    summary = vals.get("builder_output", {}).get("summary", "") if isinstance(vals.get("builder_output"), dict) else ""
                    retries = vals.get("retry_count", 0)
                    click.echo(f"[{mins:02d}:{secs:02d}] ✅ Task finished — {final or 'done'}")
                    if summary:
                        click.echo(f"             {summary}")
                    if retries:
                        click.echo(f"             (经过 {retries} 次重试)")
                else:
                    error = vals.get("error", "")
                    click.echo(f"[{mins:02d}:{secs:02d}] ❌ Task finished — {final}{' — ' + error if error else ''}")
                return

            # Determine which role we're waiting for
            role = "builder"
            agent = "?"
            if snapshot.tasks and snapshot.tasks[0].interrupts:
                info = snapshot.tasks[0].interrupts[0].value
                role = info.get("role", "builder")
                agent = info.get("agent", "?")

            for detected_role, data in poller.check_once():
                if detected_role == role:
                    step_label = "Build" if role == "builder" else "Review"
                    click.echo(f"[{mins:02d}:{secs:02d}] 📥 {step_label} 完成 ({agent})")
                    try:
                        app.invoke(Command(resume=data), config)
                    except GraphInterrupt:
                        pass
                    except Exception as e:
                        release_lock()
                        clear_runtime()
                        click.echo(f"[{mins:02d}:{secs:02d}] ❌ Error: {e}", err=True)
                        save_task_yaml(task_id, {"task_id": task_id, "status": "failed", "error": str(e)})
                        return

                    # Show next waiting state or completion
                    next_snap = app.get_state(config)
                    if next_snap and next_snap.next and next_snap.tasks and next_snap.tasks[0].interrupts:
                        next_info = next_snap.tasks[0].interrupts[0].value
                        next_role = next_info.get("role", "?")
                        next_agent = next_info.get("agent", "?")
                        next_label = "Build" if next_role == "builder" else "Review"
                        # Show retry feedback if this is a retry
                        next_vals = next_snap.values or {}
                        retry_n = next_vals.get("retry_count", 0)
                        if retry_n > 0 and next_role == "builder":
                            reviewer_out = next_vals.get("reviewer_output", {})
                            feedback = reviewer_out.get("feedback", "")
                            budget = next_vals.get("retry_budget", 2)
                            click.echo(f"[{mins:02d}:{secs:02d}] 🔄 Reviewer 要求修改 ({retry_n}/{budget}):")
                            if feedback:
                                click.echo(f"             {feedback}")
                        # Auto-spawn CLI agent or show manual instructions
                        from multi_agent.driver import get_agent_driver, spawn_cli_agent
                        drv = get_agent_driver(next_agent)
                        if drv["driver"] == "cli" and drv["command"]:
                            t_sec = next_vals.get("timeout_sec", 600)
                            click.echo(f"[{mins:02d}:{secs:02d}] 🤖 自动调用 {next_agent} CLI…")
                            spawn_cli_agent(next_agent, next_role, drv["command"], timeout_sec=t_sec)
                        else:
                            click.echo(f"[{mins:02d}:{secs:02d}] 📋 在 {next_agent} IDE 里对 AI 说:")
                            click.echo(f'             "帮我完成 @.multi-agent/TASK.md 里的任务"')
                    break

            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo(f"\n⏹️  Watch stopped. Task still active — resume with: ma watch")


def _detect_active_task(app=None) -> str | None:
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
