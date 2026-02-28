"""Meta-graph — orchestrate sequential execution of decomposed sub-tasks.

Each sub-task runs through its own independent build-review cycle using
the existing 4-node LangGraph workflow. The meta-graph coordinates:
1. Topological ordering of sub-tasks by dependencies
2. Sequential execution of each sub-task
3. Context passing: previous sub-task results feed into next
4. Aggregation of all results into a final report
"""

from __future__ import annotations

import hashlib
from typing import Any

from multi_agent.schema import SubTask


def generate_sub_task_id(parent_task_id: str, sub_id: str) -> str:
    """Generate a unique task ID for a sub-task."""
    h = hashlib.sha256(f"{parent_task_id}-{sub_id}".encode()).hexdigest()[:6]
    return f"task-{h}"


def build_sub_task_state(
    sub_task: SubTask,
    parent_task_id: str,
    builder: str = "",
    reviewer: str = "",
    timeout: int = 1800,
    retry_budget: int = 2,
    prior_results: list[dict] | None = None,
) -> dict[str, Any]:
    """Build the initial state dict for a sub-task's build-review cycle.

    prior_results: list of completed sub-task summaries for context.
    """
    task_id = generate_sub_task_id(parent_task_id, sub_task.id)

    # Build context from prior completed sub-tasks
    context_lines = []
    if prior_results:
        context_lines.append("已完成的相关子任务:")
        for pr in prior_results:
            context_lines.append(f"  - {pr.get('sub_id', '?')}: {pr.get('summary', '?')}")
            changed = pr.get("changed_files", [])
            if changed:
                context_lines.append(f"    修改文件: {', '.join(changed)}")

    requirement = sub_task.description
    if context_lines:
        requirement = requirement + "\n\n" + "\n".join(context_lines)

    return {
        "task_id": task_id,
        "requirement": requirement,
        "skill_id": sub_task.skill_id,
        "done_criteria": sub_task.done_criteria or [sub_task.description],
        "timeout_sec": timeout,
        "retry_budget": retry_budget,
        "retry_count": 0,
        "input_payload": {"requirement": sub_task.description},
        "builder_explicit": builder,
        "reviewer_explicit": reviewer,
        "conversation": [],
    }


def aggregate_results(
    parent_task_id: str,
    sub_results: list[dict],
) -> dict[str, Any]:
    """Aggregate results from all completed sub-tasks into a summary."""
    all_files = []
    all_summaries = []
    total_retries = 0
    failed = []

    for sr in sub_results:
        sub_id = sr.get("sub_id", "?")
        status = sr.get("status", "unknown")
        summary = sr.get("summary", "")
        changed = sr.get("changed_files", [])
        retries = sr.get("retry_count", 0)

        all_summaries.append(f"- {sub_id}: {summary}")
        all_files.extend(changed)
        total_retries += retries

        if status not in ("approved", "completed"):
            failed.append(sub_id)

    return {
        "task_id": parent_task_id,
        "total_sub_tasks": len(sub_results),
        "completed": len(sub_results) - len(failed),
        "failed": failed,
        "total_retries": total_retries,
        "all_changed_files": sorted(set(all_files)),
        "summary": "\n".join(all_summaries),
        "final_status": "failed" if failed else "approved",
    }
