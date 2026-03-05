"""Watch loop & waiting display — extracted from cli.py (A2c refactor).

Contains:
  _normalize_resume_output — payload validation/normalization for resume
  _show_waiting — display current waiting state, auto-spawn CLI agents
  _run_watch_loop — shared outbox poll loop, auto-submit output

These are re-exported from cli.py to preserve existing mock paths.
"""

from __future__ import annotations

import time
from typing import Any

import click

from multi_agent._utils import (
    count_nonempty_entries as _count_nonempty_entries,
)
from multi_agent._utils import (
    positive_int as _positive_int,
)
from multi_agent.workspace import (
    clear_runtime,
    release_lock,
    save_task_yaml,
    validate_outbox_data,
)


def _normalize_resume_output(role: str, data: dict[str, Any], state_values: dict[str, Any]) -> dict[str, Any]:
    """Normalize/validate resume payload for legacy go/watch/done path."""
    if role != "reviewer":
        return data

    out = dict(data)
    decision = str(out.get("decision", "")).lower().strip()
    if decision == "pass":
        out["decision"] = "approve"
        decision = "approve"
    elif decision == "fail":
        out["decision"] = "reject"
        decision = "reject"

    workflow_mode = str(state_values.get("workflow_mode", "")).lower().strip() or "normal"
    review_policy = state_values.get("review_policy")
    if not isinstance(review_policy, dict):
        review_policy = {}
    reviewer_cfg = review_policy.get("reviewer")
    if not isinstance(reviewer_cfg, dict):
        reviewer_cfg = {}

    require_evidence = bool(reviewer_cfg.get("require_evidence_on_approve", workflow_mode == "strict"))
    min_evidence = _positive_int(reviewer_cfg.get("min_evidence_items"), 1) if require_evidence else 0

    if decision == "approve" and require_evidence:
        evidence_items = _count_nonempty_entries(out.get("evidence"))
        evidence_items += _count_nonempty_entries(out.get("evidence_files"))
        if evidence_items < min_evidence:
            raise ValueError(
                "reviewer approve requires evidence: "
                f"need >= {min_evidence}, got {evidence_items}. "
                "Provide result.evidence and/or evidence_files."
            )
    return out


def _show_waiting(app: Any, config: dict[str, Any]) -> None:
    """Show current waiting state — auto-spawn CLI agents or show manual instructions."""
    from multi_agent.orchestrator import get_task_status

    task_id = config["configurable"]["thread_id"]
    status = get_task_status(app, task_id)

    if status.is_terminal:
        final = status.final_status or "done"
        if final in ("approved", "done"):
            click.echo(f"✅ Task finished. Status: {final}")
        else:
            error = status.error or ""
            click.echo(f"❌ Task finished. Status: {final}{' — ' + error if error else ''}")
        return

    role = status.waiting_role or "builder"
    agent = status.waiting_agent or "?"
    step_label = "Build" if role == "builder" else "Review"

    # Check if agent has CLI driver → auto-spawn (with graceful degradation)
    from multi_agent.driver import can_use_cli, get_agent_driver, spawn_cli_agent
    drv = get_agent_driver(agent)
    if drv["driver"] == "cli" and drv["command"]:
        if can_use_cli(drv["command"]):
            timeout = status.values.get("timeout_sec", 600)
            click.echo(f"🤖 [{step_label}] 自动调用 {agent} CLI…")
            spawn_cli_agent(agent, role, drv["command"], timeout_sec=timeout)
        else:
            binary = drv["command"].split()[0]
            click.echo(f"⚠️  {agent} 配置为 CLI 模式但 `{binary}` 未安装，降级为手动模式")
            click.echo(f"📋 [{step_label}] 在 {agent} IDE 里对 AI 说:")
            click.echo('   "帮我完成 @.multi-agent/TASK.md 里的任务"')
    else:
        click.echo(f"📋 [{step_label}] 在 {agent} IDE 里对 AI 说:")
        click.echo('   "帮我完成 @.multi-agent/TASK.md 里的任务"')
    click.echo()


def _handle_terminal(
    status: Any, task_id: str, ts: str, manage_lock: bool,
) -> None:
    """Handle terminal task status in watch loop."""
    final = status.final_status or "done"
    if final:
        save_task_yaml(task_id, {"task_id": task_id, "status": final})
    if manage_lock:
        release_lock()
        clear_runtime()
    if final in ("approved", "done"):
        summary = ""
        bo = status.values.get("builder_output")
        if isinstance(bo, dict):
            summary = bo.get("summary", "")
        retries = status.values.get("retry_count", 0)
        click.echo(f"[{ts}] ✅ Task finished. Status: {final}")
        if summary:
            click.echo(f"             {summary}")
        if retries:
            click.echo(f"             (经过 {retries} 次重试)")
    else:
        error = status.error or ""
        click.echo(f"[{ts}] ❌ Task finished. Status: {final}{' — ' + error if error else ''}")


def _show_next_agent(next_status: Any, ts: str) -> None:
    """Show next waiting state: retry feedback + auto-spawn or manual instructions."""
    next_role = next_status.waiting_role
    next_agent = next_status.waiting_agent or "?"
    retry_n = next_status.values.get("retry_count", 0)
    if retry_n > 0 and next_role == "builder":
        reviewer_out = next_status.values.get("reviewer_output") or {}
        feedback = reviewer_out.get("feedback", "") if isinstance(reviewer_out, dict) else ""
        budget = next_status.values.get("retry_budget", 2)
        click.echo(f"[{ts}] � Reviewer 要求修改 ({retry_n}/{budget}):")
        if feedback:
            click.echo(f"             {feedback}")
    from multi_agent.driver import can_use_cli, get_agent_driver, spawn_cli_agent
    drv = get_agent_driver(next_agent)
    if drv["driver"] == "cli" and drv["command"] and can_use_cli(drv["command"]):
        t_sec = next_status.values.get("timeout_sec", 600)
        click.echo(f"[{ts}] 🤖 自动调用 {next_agent} CLI…")
        spawn_cli_agent(next_agent, next_role, drv["command"], timeout_sec=t_sec)
    else:
        if drv["driver"] == "cli" and drv["command"] and not can_use_cli(drv["command"]):
            binary = drv["command"].split()[0]
            click.echo(f"[{ts}] ⚠️  `{binary}` 未安装，降级手动模式")
        click.echo(f"[{ts}] 📋 在 {next_agent} IDE 里对 AI 说:")
        click.echo('             "帮我完成 @.multi-agent/TASK.md 里的任务"')


def _process_outbox(poller: Any, role: str, agent: str, status: Any, app: Any, task_id: str, ts: str, manage_lock: bool) -> str:
    """Check outbox for matching role output, validate, and resume. Returns 'return' to stop loop."""
    from multi_agent.orchestrator import resume_task

    for detected_role, data in poller.check_once():
        if detected_role == role:
            step_label = "Build" if role == "builder" else "Review"
            click.echo(f"[{ts}] 📥 {step_label} 完成 ({agent})")
            try:
                data = _normalize_resume_output(role, data, status.values)
            except ValueError as e:
                click.echo(f"[{ts}] ❌ {e}", err=True)
                click.echo(f"[{ts}] 🔁 请修复 outbox/{role}.json 后重试", err=True)
                continue
            v_errors = validate_outbox_data(role, data)
            if v_errors:
                click.echo(f"[{ts}] ⚠️  Output warnings:", err=True)
                for ve in v_errors:
                    click.echo(f"             - {ve}", err=True)
            try:
                next_status = resume_task(app, task_id, data)
            except Exception as e:
                if manage_lock:
                    release_lock()
                    clear_runtime()
                click.echo(f"[{ts}] ❌ Error: {e}", err=True)
                save_task_yaml(task_id, {"task_id": task_id, "status": "failed", "error": str(e)})
                return "return"

            if not next_status.is_terminal and next_status.waiting_role:
                _show_next_agent(next_status, ts)
            break
    return "continue"


def _run_watch_loop(app: Any, config: dict[str, Any], task_id: str, interval: float = 2.0, manage_lock: bool = True) -> None:
    """Shared watch loop — polls outbox/ and auto-submits output."""
    from multi_agent.orchestrator import get_task_status
    from multi_agent.watcher import OutboxPoller

    poller = OutboxPoller(poll_interval=interval)
    start_time = time.time()

    click.echo("👁️  等待 IDE 完成任务… (Ctrl-C 停止)")
    click.echo()

    try:
        while True:
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)
            ts = f"{mins:02d}:{secs:02d}"

            status = get_task_status(app, task_id)

            if status.is_terminal:
                _handle_terminal(status, task_id, ts, manage_lock)
                return

            role = status.waiting_role or "builder"
            agent = status.waiting_agent or "?"

            result = _process_outbox(poller, role, agent, status, app, task_id, ts, manage_lock)
            if result == "return":
                return

            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("\n⏹️  Watch stopped. Task still active — resume with: ma watch")
