"""LangGraph 4-node graph: plan → build → review → decide."""

from __future__ import annotations

import time
from operator import add
from typing import Annotated, Any

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.sqlite import SqliteSaver

from multi_agent.config import store_db_path
from multi_agent.contract import load_contract
from multi_agent.dashboard import write_dashboard
from multi_agent.prompt import render_builder_prompt, render_reviewer_prompt
from multi_agent.router import load_agents, pick_agent, pick_reviewer
from multi_agent.schema import (
    BuilderOutput,
    ReviewerOutput,
    SkillContract,
    Task,
)
from multi_agent.workspace import (
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
    expected_checks: list[str]
    timeout_sec: int
    input_payload: dict[str, Any]

    # Flow control
    current_role: str
    current_agent: str
    builder_agent: str
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


# ── Node 1: Plan ──────────────────────────────────────────

def plan_node(state: WorkflowState) -> dict:
    """Load skill contract → select agent → generate prompt → write inbox."""
    skill_id = state["skill_id"]
    contract = load_contract(skill_id)
    agents = load_agents()

    # Determine required capabilities from contract triggers or default
    required_caps = ["implementation"]
    for trigger in contract.triggers:
        if "plan" in trigger.lower() or "decompose" in trigger.lower():
            required_caps = ["planning"]
            break

    # Pick builder agent
    builder = pick_agent(agents, contract, required_caps, role="builder")

    # Build a lightweight Task for prompt rendering
    task = Task(
        task_id=state["task_id"],
        trace_id="0" * 16,
        skill_id=skill_id,
        done_criteria=state.get("done_criteria", []),
        expected_checks=state.get("expected_checks", []),
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
        agent_id=builder.id,
        retry_count=retry_count,
        retry_feedback=retry_feedback,
        retry_budget=task.retry_budget,
    )

    # Clear previous outbox and write new inbox
    clear_outbox(builder.id)
    write_inbox(builder.id, prompt)

    # Update dashboard
    write_dashboard(
        task_id=state["task_id"],
        done_criteria=state.get("done_criteria", []),
        current_agent=builder.id,
        current_role="builder",
        conversation=state.get("conversation", []),
        status_msg=f"🔵 等待 **{builder.id}** 执行 builder 任务",
    )

    return {
        "current_role": "builder",
        "current_agent": builder.id,
        "builder_agent": builder.id,
        "started_at": time.time(),
        "conversation": [
            {"role": "orchestrator", "action": "assigned", "agent": builder.id}
        ],
    }


# ── Node 2: Build ─────────────────────────────────────────

def build_node(state: WorkflowState) -> dict:
    """Interrupt for builder → validate output → prepare reviewer."""
    agent = state["current_agent"]

    # Interrupt: wait for builder to submit via `ma done`
    result = interrupt({
        "role": "builder",
        "agent": agent,
        "inbox": f".multi-agent/inbox/{agent}.md",
    })

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

    # Pick reviewer (cross-model adversarial review)
    skill_id = state["skill_id"]
    contract = load_contract(skill_id)
    agents = load_agents()
    reviewer = pick_reviewer(agents, contract, builder_id=agent)

    # Generate reviewer prompt
    task = Task(
        task_id=state["task_id"],
        trace_id="0" * 16,
        skill_id=skill_id,
        done_criteria=state.get("done_criteria", []),
        expected_checks=state.get("expected_checks", []),
        input_payload=state.get("input_payload"),
    )

    reviewer_prompt = render_reviewer_prompt(
        task=task,
        contract=contract,
        agent_id=reviewer.id,
        builder_output=result,
        builder_agent=agent,
    )

    clear_outbox(reviewer.id)
    write_inbox(reviewer.id, reviewer_prompt)

    write_dashboard(
        task_id=state["task_id"],
        done_criteria=state.get("done_criteria", []),
        current_agent=reviewer.id,
        current_role="reviewer",
        conversation=state.get("conversation", []),
        status_msg=f"🟡 等待 **{reviewer.id}** 审查",
    )

    return {
        "builder_output": result,
        "current_role": "reviewer",
        "current_agent": reviewer.id,
        "conversation": [
            {"role": "builder", "output": result.get("summary", "")}
        ],
    }


# ── Node 3: Review ────────────────────────────────────────

def review_node(state: WorkflowState) -> dict:
    """Interrupt for reviewer → record decision."""
    agent = state["current_agent"]

    result = interrupt({
        "role": "reviewer",
        "agent": agent,
        "inbox": f".multi-agent/inbox/{agent}.md",
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
        write_dashboard(
            task_id=state["task_id"],
            done_criteria=state.get("done_criteria", []),
            current_agent=state.get("current_agent", ""),
            current_role="done",
            conversation=state.get("conversation", []),
            status_msg="✅ 审查通过，任务完成",
        )
        return {
            "final_status": "approved",
            "conversation": [{"role": "orchestrator", "action": "approved"}],
        }

    # Reject → check retry budget
    retry_count = state.get("retry_count", 0) + 1
    budget = state.get("retry_budget", 2)

    if retry_count > budget:
        write_dashboard(
            task_id=state["task_id"],
            done_criteria=state.get("done_criteria", []),
            current_agent=state.get("current_agent", ""),
            current_role="escalated",
            conversation=state.get("conversation", []),
            error=f"重试预算耗尽 ({retry_count - 1}/{budget})",
        )
        return {
            "error": "BUDGET_EXHAUSTED",
            "retry_count": retry_count,
            "final_status": "escalated",
            "conversation": [
                {"role": "orchestrator", "action": "escalated", "reason": "budget exhausted"}
            ],
        }

    # Has budget → retry with feedback
    feedback = reviewer_output.get("feedback", "")
    write_dashboard(
        task_id=state["task_id"],
        done_criteria=state.get("done_criteria", []),
        current_agent=state.get("builder_agent", ""),
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
    import sqlite3
    from pathlib import Path as _Path

    g = build_graph()
    path = db_path or str(store_db_path())

    # Ensure parent directory exists
    _Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return g.compile(checkpointer=checkpointer)
