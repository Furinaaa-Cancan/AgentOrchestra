"""LangGraph 4-node graph: plan → build → review → decide."""

from __future__ import annotations

import time
from operator import add
from typing import Annotated, Any

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite import SqliteSaver

from multi_agent.config import store_db_path
from multi_agent.contract import load_contract
from multi_agent.dashboard import write_dashboard
from multi_agent.prompt import render_builder_prompt, render_reviewer_prompt
from multi_agent.router import load_agents, resolve_builder, resolve_reviewer
from multi_agent.schema import (
    BuilderOutput,
    ReviewerOutput,
    Task,
)
from multi_agent.workspace import (
    archive_conversation,
    clear_outbox,
    write_inbox,
)


# ── State ─────────────────────────────────────────────────

class WorkflowState(TypedDict, total=False):
    # Input (set once at start)
    task_id: str
    requirement: str
    skill_id: str
    done_criteria: list[str]
    timeout_sec: int
    input_payload: dict[str, Any]

    # Flow control
    current_role: str          # "builder" or "reviewer"
    builder_id: str            # IDE name filling builder role (e.g. "windsurf")
    reviewer_id: str           # IDE name filling reviewer role (e.g. "cursor")
    builder_explicit: str      # user-specified builder (from --builder flag)
    reviewer_explicit: str     # user-specified reviewer (from --reviewer flag)
    builder_output: dict | None
    reviewer_output: dict | None
    retry_count: int
    retry_budget: int
    started_at: float

    # Accumulate
    conversation: Annotated[list[dict], add]

    # Terminal
    error: str | None
    final_status: str | None


# ── TASK.md — Universal Entry Point ──────────────────────

def _write_task_md(state: dict, builder_id: str, reviewer_id: str, current_role: str):
    """Write TASK.md — THE single self-contained file for the IDE AI.

    TASK.md embeds the full prompt content inline so the IDE AI gets
    everything it needs from ONE file reference. No jumping to inbox files.
    """
    from multi_agent.config import workspace_dir, inbox_dir

    outbox_path = f".multi-agent/outbox/{current_role}.json"

    # Read the inbox prompt that was just written
    inbox_file = inbox_dir() / f"{current_role}.md"
    prompt_content = ""
    if inbox_file.exists():
        prompt_content = inbox_file.read_text(encoding="utf-8")

    lines = [
        prompt_content,
        "",
        "---",
        "",
        "> **完成后，把上面要求的 JSON 结果保存到以下路径，终端会自动推进流程:**",
        f"> `{outbox_path}`",
        "",
    ]

    p = workspace_dir() / "TASK.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")


# ── Node 1: Plan ──────────────────────────────────────────

def plan_node(state: WorkflowState) -> dict:
    """Load skill contract → resolve builder → generate prompt → write inbox."""
    skill_id = state["skill_id"]
    contract = load_contract(skill_id)
    agents = load_agents()

    # On retry, reuse existing role assignments to keep consistency
    existing_builder = state.get("builder_id")
    existing_reviewer = state.get("reviewer_id")

    if existing_builder and existing_reviewer:
        builder_id = existing_builder
        reviewer_id = existing_reviewer
    else:
        # First run: resolve roles
        builder_id = resolve_builder(
            agents, contract,
            explicit=state.get("builder_explicit") or None,
        )
        reviewer_id = resolve_reviewer(
            agents, contract, builder_id,
            explicit=state.get("reviewer_explicit") or None,
        )

    # Build a lightweight Task for prompt rendering
    task = Task(
        task_id=state["task_id"],
        trace_id="0" * 16,
        skill_id=skill_id,
        done_criteria=state.get("done_criteria", []),
        timeout_sec=state.get("timeout_sec", contract.timeouts.run_sec),
        retry_budget=state.get("retry_budget", contract.retry.max_attempts),
        input_payload=state.get("input_payload"),
    )

    retry_count = state.get("retry_count", 0)
    retry_feedback = ""
    if retry_count > 0 and state.get("reviewer_output"):
        retry_feedback = state["reviewer_output"].get("feedback", "")

    prompt = render_builder_prompt(
        task=task,
        contract=contract,
        agent_id=builder_id,
        retry_count=retry_count,
        retry_feedback=retry_feedback,
        retry_budget=task.retry_budget,
    )

    # Write to ROLE-based inbox (builder.md, not windsurf.md)
    clear_outbox("builder")
    write_inbox("builder", prompt)

    # Write TASK.md — single entry point for any IDE
    _write_task_md(state, builder_id, reviewer_id, "builder")

    # Update dashboard
    write_dashboard(
        task_id=state["task_id"],
        done_criteria=state.get("done_criteria", []),
        current_agent=builder_id,
        current_role="builder",
        conversation=state.get("conversation", []),
        status_msg=f"🔵 等待 **{builder_id}** 执行 builder 任务",
    )

    return {
        "current_role": "builder",
        "builder_id": builder_id,
        "reviewer_id": reviewer_id,
        "started_at": time.time(),
        "conversation": [
            {"role": "orchestrator", "action": "assigned", "agent": builder_id}
        ],
    }


# ── Node 2: Build ─────────────────────────────────────────

def build_node(state: WorkflowState) -> dict:
    """Interrupt for builder → validate output → prepare reviewer."""
    builder_id = state.get("builder_id", "?")
    reviewer_id = state.get("reviewer_id", "?")

    # Interrupt: wait for builder to submit via `ma done`
    # Role-based: inbox is always builder.md regardless of which IDE
    result = interrupt({
        "role": "builder",
        "agent": builder_id,
    })

    # A3: Timeout enforcement — check elapsed time
    started = state.get("started_at", 0)
    timeout = state.get("timeout_sec", 1800)
    if started and timeout:
        elapsed = time.time() - started
        if elapsed > timeout:
            return {
                "error": f"TIMEOUT: builder took {int(elapsed)}s (limit: {timeout}s)",
                "final_status": "failed",
                "conversation": [{"role": "orchestrator", "action": "timeout", "elapsed": int(elapsed)}],
            }

    # Validate builder output (light-weight)
    errors: list[str] = []
    if not isinstance(result, dict):
        errors.append("output must be a JSON object")
    else:
        if "status" not in result:
            errors.append("missing 'status' field")
        if "summary" not in result:
            errors.append("missing 'summary' field")

    if errors:
        return {
            "error": f"Builder output invalid: {'; '.join(errors)}",
            "final_status": "failed",
            "conversation": [{"role": "builder", "output": "INVALID"}],
        }

    # Validate via Pydantic (non-fatal — we log warnings but proceed)
    try:
        BuilderOutput(**result)
    except Exception:
        pass  # Lenient: proceed even if extra fields exist

    # A4: Quality gate enforcement — check that required gates passed
    skill_id = state["skill_id"]
    contract = load_contract(skill_id)
    check_results = result.get("check_results", {})
    gate_warnings: list[str] = []
    for gate in contract.quality_gates:
        gate_result = check_results.get(gate)
        if gate_result is None:
            gate_warnings.append(f"quality gate '{gate}' not reported")
        elif str(gate_result).lower() not in ("pass", "passed", "ok", "success", "true"):
            gate_warnings.append(f"quality gate '{gate}' failed: {gate_result}")
    # Gate failures go to reviewer as extra context (not hard-fail)
    if gate_warnings:
        result.setdefault("gate_warnings", gate_warnings)

    task = Task(
        task_id=state["task_id"],
        trace_id="0" * 16,
        skill_id=skill_id,
        done_criteria=state.get("done_criteria", []),
        input_payload=state.get("input_payload"),
    )

    reviewer_prompt = render_reviewer_prompt(
        task=task,
        contract=contract,
        agent_id=reviewer_id,
        builder_output=result,
        builder_id=builder_id,
    )

    clear_outbox("reviewer")
    write_inbox("reviewer", reviewer_prompt)

    # Update TASK.md
    _write_task_md(state, builder_id, reviewer_id, "reviewer")

    write_dashboard(
        task_id=state["task_id"],
        done_criteria=state.get("done_criteria", []),
        current_agent=reviewer_id,
        current_role="reviewer",
        conversation=state.get("conversation", []),
        status_msg=f"🟡 等待 **{reviewer_id}** 审查",
    )

    return {
        "builder_output": result,
        "current_role": "reviewer",
        "conversation": [
            {"role": "builder", "output": result.get("summary", "")}
        ],
    }


# ── Node 3: Review ────────────────────────────────────────

def review_node(state: WorkflowState) -> dict:
    """Interrupt for reviewer → record decision."""
    reviewer_id = state.get("reviewer_id", "?")

    result = interrupt({
        "role": "reviewer",
        "agent": reviewer_id,
    })

    # Basic validation
    if not isinstance(result, dict):
        return {
            "reviewer_output": {"decision": "reject", "feedback": "Invalid reviewer output"},
            "conversation": [{"role": "reviewer", "decision": "reject"}],
        }

    try:
        parsed = ReviewerOutput(**result)
        decision = parsed.decision.value
    except Exception:
        decision = result.get("decision", "reject")

    return {
        "reviewer_output": result,
        "conversation": [{"role": "reviewer", "decision": decision}],
    }


# ── Node 4: Decide ────────────────────────────────────────

def decide_node(state: WorkflowState) -> dict:
    """Route based on reviewer decision: approve → end, reject → retry or escalate."""
    reviewer_output = state.get("reviewer_output", {})
    decision = reviewer_output.get("decision", "reject")

    if decision == "approve":
        final_entry = {"role": "orchestrator", "action": "approved"}
        full_convo = state.get("conversation", []) + [final_entry]
        write_dashboard(
            task_id=state["task_id"],
            done_criteria=state.get("done_criteria", []),
            current_agent=state.get("reviewer_id", ""),
            current_role="done",
            conversation=full_convo,
            status_msg="✅ 审查通过，任务完成",
        )
        archive_conversation(state["task_id"], full_convo)
        return {
            "final_status": "approved",
            "conversation": [final_entry],
        }

    # Reject → check retry budget
    retry_count = state.get("retry_count", 0) + 1
    budget = state.get("retry_budget", 2)

    if retry_count > budget:
        final_entry = {"role": "orchestrator", "action": "escalated", "reason": "budget exhausted"}
        full_convo = state.get("conversation", []) + [final_entry]
        write_dashboard(
            task_id=state["task_id"],
            done_criteria=state.get("done_criteria", []),
            current_agent=state.get("reviewer_id", ""),
            current_role="escalated",
            conversation=full_convo,
            error=f"重试预算耗尽 ({retry_count - 1}/{budget})",
        )
        archive_conversation(state["task_id"], full_convo)
        return {
            "error": "BUDGET_EXHAUSTED",
            "retry_count": retry_count,
            "final_status": "escalated",
            "conversation": [final_entry],
        }

    # Has budget → retry with feedback
    feedback = reviewer_output.get("feedback", "")
    write_dashboard(
        task_id=state["task_id"],
        done_criteria=state.get("done_criteria", []),
        current_agent=state.get("builder_id", ""),
        current_role="builder",
        conversation=state.get("conversation", []),
        status_msg=f"🔄 重试 ({retry_count}/{budget})",
    )

    return {
        "retry_count": retry_count,
        "conversation": [
            {"role": "orchestrator", "action": "retry", "feedback": feedback}
        ],
    }


# ── Routing ───────────────────────────────────────────

def _route_after_build(state: WorkflowState) -> str:
    """Skip review if build_node returned an error."""
    if state.get("error") or state.get("final_status") in ("failed", "cancelled"):
        return "end"
    return "review"


def route_decision(state: WorkflowState) -> str:
    if state.get("error"):
        return "end"
    if state.get("final_status") == "approved":
        return "end"
    return "retry"


# ── Graph Assembly ────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build the 4-node LangGraph workflow (uncompiled)."""
    g = StateGraph(WorkflowState)

    g.add_node("plan", plan_node)
    g.add_node("build", build_node)
    g.add_node("review", review_node)
    g.add_node("decide", decide_node)

    g.add_edge(START, "plan")
    g.add_edge("plan", "build")
    g.add_conditional_edges("build", _route_after_build, {
        "review": "review",
        "end": END,
    })
    g.add_edge("review", "decide")
    g.add_conditional_edges("decide", route_decision, {
        "end": END,
        "retry": "plan",
    })

    return g


def compile_graph(*, db_path: str | None = None):
    """Compile graph with SQLite checkpointer."""
    import atexit
    import sqlite3
    from pathlib import Path as _Path

    g = build_graph()
    path = db_path or str(store_db_path())

    # Ensure parent directory exists
    _Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, check_same_thread=False)
    atexit.register(conn.close)
    checkpointer = SqliteSaver(conn)
    return g.compile(checkpointer=checkpointer)
