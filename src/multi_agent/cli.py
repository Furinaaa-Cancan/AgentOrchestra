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
@click.option("--decompose", is_flag=True, default=False, help="Decompose complex requirement into sub-tasks first")
def go(requirement: str, skill: str, task_id: str | None, builder: str, reviewer: str, retry_budget: int, timeout: int, no_watch: bool, decompose: bool):
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
      ma go "实现完整用户认证模块" --decompose
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

    if decompose:
        _run_decomposed(app, task_id, requirement, skill, builder, reviewer,
                        retry_budget, timeout, no_watch)
        return

    _run_single_task(app, task_id, requirement, skill, builder, reviewer,
                     retry_budget, timeout, no_watch)


def _run_single_task(app, task_id, requirement, skill, builder, reviewer,
                     retry_budget, timeout, no_watch):
    """Run a single monolithic build-review cycle (original behavior)."""
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


def _run_decomposed(app, parent_task_id, requirement, skill, builder, reviewer,
                    retry_budget, timeout, no_watch):
    """Decompose → sequential sub-task build-review cycles → aggregate."""
    from multi_agent.decompose import write_decompose_prompt, read_decompose_result, topo_sort
    from multi_agent.meta_graph import build_sub_task_state, aggregate_results
    from langgraph.errors import GraphInterrupt

    click.echo(f"🧩 Task Decomposition: {parent_task_id}")
    click.echo(f"   {requirement}")
    click.echo()

    save_task_yaml(parent_task_id, {
        "task_id": parent_task_id, "status": "active", "mode": "decompose",
    })

    # Phase 1: Write decompose prompt → wait for agent to decompose
    write_decompose_prompt(requirement)
    click.echo(f"📋 分解任务中… 在 IDE 里对 AI 说:")
    click.echo(f'   "帮我完成 @.multi-agent/TASK.md 里的任务"')

    # Check if builder has CLI driver → auto-spawn for decomposition
    from multi_agent.driver import get_agent_driver, spawn_cli_agent, can_use_cli
    from multi_agent.router import load_agents
    agents = load_agents()
    decompose_agent = builder if builder else (agents[0].id if agents else "?")
    drv = get_agent_driver(decompose_agent)
    if drv["driver"] == "cli" and drv["command"] and can_use_cli(drv["command"]):
        click.echo(f"🤖 自动调用 {decompose_agent} CLI 进行任务分解…")
        spawn_cli_agent(decompose_agent, "decompose", drv["command"], timeout_sec=timeout)

    click.echo(f"👁️  等待任务分解结果… (Ctrl-C 停止)")

    # Poll for decompose.json (with timeout)
    decompose_result = None
    deadline = time.time() + timeout
    try:
        while decompose_result is None:
            decompose_result = read_decompose_result()
            if decompose_result:
                break
            if time.time() > deadline:
                click.echo(f"❌ 任务分解超时 ({timeout}s)。", err=True)
                release_lock()
                clear_runtime()
                sys.exit(1)
            time.sleep(2)
    except KeyboardInterrupt:
        click.echo(f"\n⏹️  Decomposition stopped.")
        release_lock()
        clear_runtime()
        return

    # Phase 2: Sort sub-tasks by dependencies
    try:
        sorted_tasks = topo_sort(decompose_result.sub_tasks)
    except ValueError as e:
        click.echo(f"❌ 分解结果无效: {e}", err=True)
        release_lock()
        clear_runtime()
        sys.exit(1)

    if not sorted_tasks:
        click.echo(f"⚠️  分解结果为空，降级为单任务模式")
        _run_single_task(app, parent_task_id, requirement, skill, builder, reviewer,
                         retry_budget, timeout, no_watch)
        return

    click.echo(f"\n✅ 分解完成: {len(sorted_tasks)} 个子任务")
    if decompose_result.reasoning:
        click.echo(f"   理由: {decompose_result.reasoning}")
    for i, st in enumerate(sorted_tasks, 1):
        deps_str = f" (依赖: {', '.join(st.deps)})" if st.deps else ""
        click.echo(f"   {i}. {st.id}: {st.description}{deps_str}")
    click.echo()

    # Phase 3: Execute each sub-task sequentially
    prior_results: list[dict] = []
    failed_ids: set[str] = set()  # track failed sub-task IDs for dep skipping

    for i, st in enumerate(sorted_tasks, 1):
        # Skip sub-tasks whose dependencies failed
        skipped_deps = [d for d in st.deps if d in failed_ids]
        if skipped_deps:
            click.echo(f"\n⏭️  跳过 {st.id}: 依赖 {', '.join(skipped_deps)} 已失败")
            prior_results.append({
                "sub_id": st.id, "status": "skipped",
                "summary": f"Skipped: dependency {', '.join(skipped_deps)} failed",
                "changed_files": [], "retry_count": 0,
            })
            failed_ids.add(st.id)
            continue

        click.echo(f"\n{'='*60}")
        click.echo(f"  📦 Sub-task {i}/{len(sorted_tasks)}: {st.id}")
        click.echo(f"  {st.description}")
        click.echo(f"{'='*60}")

        # Clear runtime for this sub-task
        clear_runtime()

        sub_state = build_sub_task_state(
            sub_task=st,
            parent_task_id=parent_task_id,
            builder=builder,
            reviewer=reviewer,
            timeout=timeout,
            retry_budget=retry_budget,
            prior_results=prior_results,
        )
        sub_task_id = sub_state["task_id"]
        sub_config = _make_config(sub_task_id)

        # Run sub-task graph
        try:
            app.invoke(sub_state, sub_config)
        except GraphInterrupt:
            pass
        except Exception as e:
            click.echo(f"❌ Sub-task {st.id} failed to start: {e}", err=True)
            prior_results.append({
                "sub_id": st.id, "status": "failed",
                "summary": str(e), "changed_files": [], "retry_count": 0,
            })
            failed_ids.add(st.id)
            continue

        # Show waiting + watch loop for this sub-task
        _show_waiting(app, sub_config)

        if no_watch:
            click.echo(f"📌 Sub-task {st.id}: 等待手动 ma done")
            click.echo(f"⚠️  --no-watch 模式下 --decompose 只执行第一步分解。")
            click.echo(f"   后续请逐个手动执行各子任务。")
            save_task_yaml(parent_task_id, {
                "task_id": parent_task_id, "status": "decomposed",
                "sub_tasks": [s.model_dump() for s in sorted_tasks],
            })
            return

        # manage_lock=False: don't release parent lock between sub-tasks
        _run_watch_loop(app, sub_config, sub_task_id, manage_lock=False)

        # Collect result
        snapshot = app.get_state(sub_config)
        vals = snapshot.values if snapshot else {}
        builder_out = vals.get("builder_output", {})
        if not isinstance(builder_out, dict):
            builder_out = {}

        sub_status = vals.get("final_status", "unknown")
        prior_results.append({
            "sub_id": st.id,
            "status": sub_status,
            "summary": builder_out.get("summary", ""),
            "changed_files": builder_out.get("changed_files", []),
            "retry_count": vals.get("retry_count", 0),
        })
        if sub_status not in ("approved", "completed"):
            failed_ids.add(st.id)

    # Phase 4: Aggregate
    click.echo(f"\n{'='*60}")
    click.echo(f"  📊 汇总结果")
    click.echo(f"{'='*60}")

    agg = aggregate_results(parent_task_id, prior_results)

    click.echo(f"  总子任务: {agg['total_sub_tasks']}")
    click.echo(f"  完成: {agg['completed']}")
    click.echo(f"  总重试: {agg['total_retries']}")
    if agg["failed"]:
        click.echo(f"  ❌ 失败: {', '.join(agg['failed'])}")
    else:
        click.echo(f"  ✅ 全部通过")
    click.echo(f"  修改文件: {', '.join(agg['all_changed_files']) or '无'}")
    click.echo()

    save_task_yaml(parent_task_id, {
        "task_id": parent_task_id, "status": agg["final_status"],
        "sub_results": prior_results,
    })
    release_lock()
    clear_runtime()


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

    # Check if agent has CLI driver → auto-spawn (with graceful degradation)
    from multi_agent.driver import get_agent_driver, spawn_cli_agent, can_use_cli
    drv = get_agent_driver(agent)
    if drv["driver"] == "cli" and drv["command"]:
        if can_use_cli(drv["command"]):
            vals = snapshot.values or {}
            timeout = vals.get("timeout_sec", 600)
            click.echo(f"🤖 [{step_label}] 自动调用 {agent} CLI…")
            spawn_cli_agent(agent, role, drv["command"], timeout_sec=timeout)
        else:
            binary = drv["command"].split()[0]
            click.echo(f"⚠️  {agent} 配置为 CLI 模式但 `{binary}` 未安装，降级为手动模式")
            click.echo(f"📋 [{step_label}] 在 {agent} IDE 里对 AI 说:")
            click.echo(f'   "帮我完成 @.multi-agent/TASK.md 里的任务"')
    else:
        click.echo(f"📋 [{step_label}] 在 {agent} IDE 里对 AI 说:")
        click.echo(f'   "帮我完成 @.multi-agent/TASK.md 里的任务"')
    click.echo()


def _run_watch_loop(app, config, task_id: str, interval: float = 2.0, manage_lock: bool = True):
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
                if manage_lock:
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
                        if manage_lock:
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
                        from multi_agent.driver import get_agent_driver, spawn_cli_agent, can_use_cli
                        drv = get_agent_driver(next_agent)
                        if drv["driver"] == "cli" and drv["command"] and can_use_cli(drv["command"]):
                            t_sec = next_vals.get("timeout_sec", 600)
                            click.echo(f"[{mins:02d}:{secs:02d}] 🤖 自动调用 {next_agent} CLI…")
                            spawn_cli_agent(next_agent, next_role, drv["command"], timeout_sec=t_sec)
                        else:
                            if drv["driver"] == "cli" and drv["command"] and not can_use_cli(drv["command"]):
                                binary = drv["command"].split()[0]
                                click.echo(f"[{mins:02d}:{secs:02d}] ⚠️  `{binary}` 未安装，降级手动模式")
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
