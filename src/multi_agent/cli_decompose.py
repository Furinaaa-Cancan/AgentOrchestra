"""Decomposed task execution — extracted from cli.py (A2b refactor).

Contains _run_decomposed(): the sequential sub-task build-review pipeline
invoked by `ma go --decompose`.  All CLI helpers (_make_config, _show_waiting,
_run_watch_loop, _run_single_task) are imported lazily from cli.py to break
the circular-import chain.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import click


def _run_decomposed(
    app,
    parent_task_id,
    requirement,
    skill,
    builder,
    reviewer,
    retry_budget,
    timeout,
    no_watch,
    workflow_mode,
    review_policy,
    *,
    auto_confirm: bool = False,
    decompose_file: str | None = None,
    no_cache: bool = False,
):
    """Decompose → sequential sub-task build-review cycles → aggregate."""
    # Lazy imports to avoid circular dependency with cli.py
    from multi_agent.cli import _make_config, _run_single_task, _run_watch_loop, _show_waiting
    from multi_agent.decompose import read_decompose_result, topo_sort, topo_sort_grouped, write_decompose_prompt
    from multi_agent.meta_graph import aggregate_results, build_sub_task_state
    from multi_agent.orchestrator import TaskStartError, start_task
    from multi_agent.workspace import clear_runtime, release_lock, save_task_yaml

    click.echo(f"🧩 Task Decomposition: {parent_task_id}")
    click.echo(f"   {requirement}")
    click.echo()

    save_task_yaml(parent_task_id, {
        "task_id": parent_task_id, "status": "active", "mode": "decompose",
    })

    # Task 23: Check decompose cache first
    decompose_result = None
    if not decompose_file and not no_cache:
        from multi_agent.decompose import get_cached_decompose
        decompose_result = get_cached_decompose(requirement, skill_id=skill)
        if decompose_result:
            click.echo("💾 使用缓存的分解结果 (原始需求相同)")

    # Task 29: Read decompose result from file if provided (JSON or YAML)
    if decompose_result is None and decompose_file:
        import json as _json

        from multi_agent.schema import DecomposeResult
        try:
            raw = Path(decompose_file).read_text(encoding="utf-8")
            if decompose_file.endswith((".yaml", ".yml")):
                import yaml as _yaml
                data = _yaml.safe_load(raw)
            else:
                data = _json.loads(raw)
            decompose_result = DecomposeResult(**data)
            click.echo(f"📂 从文件加载分解结果: {decompose_file}")
        except Exception as e:
            click.echo(f"❌ 无法读取分解文件: {e}", err=True)
            release_lock()
            sys.exit(1)

    if decompose_result is None:
        # Phase 1: Write decompose prompt → wait for agent to decompose
        write_decompose_prompt(requirement)
        click.echo("📋 分解任务中… 在 IDE 里对 AI 说:")
        click.echo('   "帮我完成 @.multi-agent/TASK.md 里的任务"')

        # Check if builder has CLI driver → auto-spawn for decomposition
        from multi_agent.driver import can_use_cli, get_agent_driver, spawn_cli_agent
        from multi_agent.router import load_agents
        agents = load_agents()
        decompose_agent = builder if builder else (agents[0].id if agents else "?")
        drv = get_agent_driver(decompose_agent)
        if drv["driver"] == "cli" and drv["command"] and can_use_cli(drv["command"]):
            click.echo(f"🤖 自动调用 {decompose_agent} CLI 进行任务分解…")
            spawn_cli_agent(decompose_agent, "decompose", drv["command"], timeout_sec=timeout)

        click.echo("👁️  等待任务分解结果… (Ctrl-C 停止)")

        # Poll for decompose.json (with timeout)
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
            click.echo("\n⏹️  Decomposition stopped.")
            release_lock()
            clear_runtime()
            return

    # Task 23: Cache the decompose result for future re-use
    if not decompose_file and not no_cache:
        from multi_agent.decompose import cache_decompose
        try:
            cache_decompose(requirement, decompose_result, skill_id=skill)
        except Exception:
            pass

    # Task 20: Validate decompose result structure
    from multi_agent.decompose import validate_decompose_result
    validation_errors = validate_decompose_result(decompose_result)
    if validation_errors:
        click.echo("⚠️  分解结果存在问题:", err=True)
        for ve in validation_errors:
            click.echo(f"   - {ve}", err=True)

    # Phase 2: Sort sub-tasks by dependencies
    try:
        sorted_tasks = topo_sort(decompose_result.sub_tasks)
    except ValueError as e:
        click.echo(f"❌ 分解结果无效: {e}", err=True)
        release_lock()
        clear_runtime()
        sys.exit(1)

    if not sorted_tasks:
        click.echo("⚠️  分解结果为空，降级为单任务模式")
        _run_single_task(app, parent_task_id, requirement, skill, builder, reviewer,
                         retry_budget, timeout, no_watch, workflow_mode, review_policy)
        return

    click.echo(f"\n✅ 分解完成: {len(sorted_tasks)} 个子任务")
    if decompose_result.reasoning:
        click.echo(f"   理由: {decompose_result.reasoning}")

    # Task 19: Show parallel group info
    try:
        groups = topo_sort_grouped(decompose_result.sub_tasks)
        for gi, group in enumerate(groups, 1):
            ids = ", ".join(st.id for st in group)
            if len(group) > 1:
                click.echo(f"   组 {gi} (可并行): {ids}")
            else:
                click.echo(f"   组 {gi}: {ids}")
    except ValueError:
        for i, st in enumerate(sorted_tasks, 1):
            deps_str = f" (依赖: {', '.join(st.deps)})" if st.deps else ""
            click.echo(f"   {i}. {st.id}: {st.description}{deps_str}")
    click.echo()

    # Task 28: Confirmation step before execution
    if not auto_confirm:
        if not click.confirm("确认执行这些子任务？", default=True):
            click.echo("⏹️  已取消。可修改 .multi-agent/outbox/decompose.json 后重新运行。")
            release_lock()
            return

    # Phase 3: Execute each sub-task sequentially
    # C2: Load checkpoint for crash recovery (MAS-FIRE 2026 fault tolerance)
    from multi_agent.meta_graph import clear_checkpoint, load_checkpoint, save_checkpoint
    ckpt = load_checkpoint(parent_task_id)
    prior_results: list[dict[str, Any]] = ckpt["prior_results"] if ckpt else []
    completed_ids: set[str] = set(ckpt["completed_ids"]) if ckpt else set()
    failed_ids: set[str] = set()  # track failed sub-task IDs for dep skipping
    if ckpt:
        click.echo(f"💾 恢复 checkpoint: {len(completed_ids)} 个子任务已完成")
        # Rebuild failed_ids from prior_results
        for pr in prior_results:
            if pr.get("status") not in ("approved", "completed", "skipped"):
                failed_ids.add(pr["sub_id"])

    total = len(sorted_tasks)
    decompose_start = time.time()

    for i, st in enumerate(sorted_tasks, 1):
        # Skip already-completed sub-tasks (from checkpoint)
        if st.id in completed_ids:
            click.echo(f"\n[{i}/{total}] ⏩ {st.id} 已完成 (checkpoint)")
            continue
        done_count = len([r for r in prior_results if r["status"] in ("approved", "completed", "skipped")])
        pct = int(done_count / total * 100)

        # Skip sub-tasks whose dependencies failed
        skipped_deps = [d for d in st.deps if d in failed_ids]
        if skipped_deps:
            click.echo(f"\n[{i}/{total}] ⏭️ {st.id} 跳过 ({pct}%)")
            prior_results.append({
                "sub_id": st.id, "status": "skipped",
                "summary": f"Skipped: dependency {', '.join(skipped_deps)} failed",
                "changed_files": [], "retry_count": 0, "duration_sec": 0,
                "estimated_minutes": getattr(st, 'estimated_minutes', 0),
            })
            failed_ids.add(st.id)
            continue

        click.echo(f"\n{'='*60}")
        click.echo(f"  [{i}/{total}] 📦 {st.id} ({pct}% 完成)")
        click.echo(f"  {st.description}")
        click.echo(f"{'='*60}")
        sub_start = time.time()

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
            workflow_mode=workflow_mode,
            review_policy=review_policy,
        )
        sub_task_id = sub_state["task_id"]
        sub_config = _make_config(sub_task_id)

        # Run sub-task graph via orchestrator
        try:
            start_task(app, sub_task_id, sub_state)
        except TaskStartError as e:
            click.echo(f"❌ Sub-task {st.id} failed to start: {e.cause}", err=True)
            prior_results.append({
                "sub_id": st.id, "status": "failed",
                "summary": str(e), "changed_files": [], "retry_count": 0,
                "duration_sec": round(time.time() - sub_start, 1),
                "estimated_minutes": getattr(st, 'estimated_minutes', 0),
            })
            failed_ids.add(st.id)
            continue

        # Show waiting + watch loop for this sub-task
        _show_waiting(app, sub_config)

        if no_watch:
            click.echo(f"📌 Sub-task {st.id}: 等待手动 ma done")
            click.echo("⚠️  --no-watch 模式下 --decompose 只执行第一步分解。")
            click.echo("   后续请逐个手动执行各子任务。")
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
        sub_dur = round(time.time() - sub_start, 1)
        reviewer_out = vals.get("reviewer_output", {})
        if not isinstance(reviewer_out, dict):
            reviewer_out = {}
        prior_results.append({
            "sub_id": st.id,
            "status": sub_status,
            "summary": builder_out.get("summary", ""),
            "changed_files": builder_out.get("changed_files", []),
            "retry_count": vals.get("retry_count", 0),
            "duration_sec": sub_dur,
            "estimated_minutes": getattr(st, 'estimated_minutes', 0),
            "reviewer_feedback": reviewer_out.get("feedback", ""),
        })
        completed_ids.add(st.id)
        save_checkpoint(parent_task_id, prior_results, list(completed_ids))
        done_count2 = len([r for r in prior_results if r["status"] in ("approved", "completed", "skipped")])
        pct2 = int(done_count2 / total * 100)
        if sub_status in ("approved", "completed"):
            click.echo(f"[{i}/{total}] ✅ {st.id} 完成 ({pct2}%)")
        if sub_status not in ("approved", "completed"):
            # Task 21: User choice on failure (skip for auto CLI mode)
            if not auto_confirm:
                click.echo(f"\n❌ Sub-task {st.id} 失败 (状态: {sub_status})")
                choice = click.prompt(
                    "选择操作", type=click.Choice(["skip", "retry", "abort"]),
                    default="skip",
                )
                if choice == "retry":
                    click.echo(f"🔄 重试 Sub-task {st.id}…")
                    clear_runtime()
                    prior_results.pop()  # remove the failed result
                    sub_state2 = build_sub_task_state(
                        sub_task=st,
                        parent_task_id=parent_task_id,
                        builder=builder, reviewer=reviewer,
                        timeout=timeout, retry_budget=retry_budget,
                        prior_results=prior_results,
                        workflow_mode=workflow_mode,
                        review_policy=review_policy,
                    )
                    sub_config2 = _make_config(sub_state2["task_id"])
                    try:
                        start_task(app, sub_state2["task_id"], sub_state2)
                    except TaskStartError:
                        pass  # Will be detected in watch loop
                    _show_waiting(app, sub_config2)
                    _run_watch_loop(app, sub_config2, sub_state2["task_id"], manage_lock=False)
                    snap2 = app.get_state(sub_config2)
                    v2 = snap2.values if snap2 else {}
                    bo2 = v2.get("builder_output", {})
                    if not isinstance(bo2, dict):
                        bo2 = {}
                    s2 = v2.get("final_status", "unknown")
                    ro2 = v2.get("reviewer_output", {})
                    if not isinstance(ro2, dict):
                        ro2 = {}
                    prior_results.append({
                        "sub_id": st.id, "status": s2,
                        "summary": bo2.get("summary", ""),
                        "changed_files": bo2.get("changed_files", []),
                        "retry_count": v2.get("retry_count", 0),
                        "duration_sec": round(time.time() - sub_start, 1),
                        "estimated_minutes": getattr(st, 'estimated_minutes', 0),
                        "reviewer_feedback": ro2.get("feedback", ""),
                    })
                    if s2 not in ("approved", "completed"):
                        failed_ids.add(st.id)
                    else:
                        completed_ids.add(st.id)
                        save_checkpoint(parent_task_id, prior_results, list(completed_ids))
                    continue
                elif choice == "abort":
                    click.echo("⏹️  终止 decompose 流程，保存已完成结果。")
                    failed_ids.add(st.id)
                    break
            failed_ids.add(st.id)

    # Phase 4: Aggregate
    click.echo(f"\n{'='*60}")
    click.echo("  📊 汇总结果")
    click.echo(f"{'='*60}")

    agg = aggregate_results(parent_task_id, prior_results)

    click.echo(f"  总子任务: {agg['total_sub_tasks']}")
    click.echo(f"  完成: {agg['completed']}")
    click.echo(f"  总重试: {agg['total_retries']}")
    if agg["failed"]:
        click.echo(f"  ❌ 失败: {', '.join(agg['failed'])}")
    else:
        click.echo("  ✅ 全部通过")
    click.echo(f"  修改文件: {', '.join(agg['all_changed_files']) or '无'}")

    # Task 26: Write Markdown report
    from multi_agent.meta_graph import generate_aggregate_report
    report_text = generate_aggregate_report(agg)
    from multi_agent.config import workspace_dir
    report_path = workspace_dir() / f"report-{parent_task_id}.md"
    report_path.write_text(report_text, encoding="utf-8")
    click.echo(f"  📄 报告: {report_path}")
    total_elapsed = round(time.time() - decompose_start)
    if total_elapsed >= 60:
        mins, secs = divmod(total_elapsed, 60)
        click.echo(f"  ⏱️ 总耗时: {mins} 分 {secs} 秒")
    else:
        click.echo(f"  ⏱️ 总耗时: {total_elapsed} 秒")
    click.echo()

    save_task_yaml(parent_task_id, {
        "task_id": parent_task_id, "status": agg["final_status"],
        "sub_results": prior_results,
    })
    # C2: Clear checkpoint on completion (MAS-FIRE 2026)
    clear_checkpoint(parent_task_id)
    release_lock()
    clear_runtime()
