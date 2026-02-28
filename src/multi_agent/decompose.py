"""Task decomposition — break complex requirements into sub-tasks.

Uses the first available builder agent (via IDE or CLI) to decompose
a complex requirement into independent sub-tasks, each with its own
build-review cycle.

The decomposition result is a DecomposeResult containing SubTask objects
with dependency ordering.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from multi_agent.config import workspace_dir, outbox_dir, inbox_dir
from multi_agent.schema import DecomposeResult, SubTask


DECOMPOSE_PROMPT = """\
# 🧩 任务分解

## 你的身份
- **角色**: Task Decomposer (任务分解器)
- **目标**: 把一个复杂需求拆分成多个独立的、可逐个实现的子任务

## 原始需求
{requirement}

## 规则
1. 每个子任务必须是**独立可实现**的（一次 build-review 能完成）
2. 子任务之间可以有依赖关系（用 deps 字段表示）
3. 每个子任务需要明确的 done_criteria（完成标准）
4. 子任务数量控制在 2-6 个（太少没意义，太多增加开销）
5. 如果需求本身就很简单（单个功能），输出 1 个子任务即可
6. 子任务 ID 使用小写字母和连字符，如 "auth-login"

## 产出要求
输出以下 JSON:

```json
{{
  "sub_tasks": [
    {{
      "id": "subtask-id",
      "description": "要实现什么",
      "done_criteria": ["标准1", "标准2"],
      "deps": [],
      "skill_id": "code-implement"
    }}
  ],
  "reasoning": "为什么这样拆分"
}}
```
"""


def write_decompose_prompt(requirement: str) -> Path:
    """Write decomposition prompt to TASK.md for IDE/CLI agent."""
    prompt = DECOMPOSE_PROMPT.format(requirement=requirement)

    outbox_rel = ".multi-agent/outbox/decompose.json"
    outbox_abs = str(outbox_dir() / "decompose.json")

    lines = [
        prompt,
        "",
        "---",
        "",
        "> **完成后，把上面要求的 JSON 结果保存到以下路径:**",
        f"> `{outbox_rel}`",
        f"> 绝对路径: `{outbox_abs}`",
        "",
    ]

    p = workspace_dir() / "TASK.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")

    # Also write to inbox for consistency
    inbox_p = inbox_dir() / "decompose.md"
    inbox_p.parent.mkdir(parents=True, exist_ok=True)
    inbox_p.write_text(prompt, encoding="utf-8")

    return p


def read_decompose_result() -> DecomposeResult | None:
    """Read decomposition result from outbox/decompose.json."""
    outbox_file = outbox_dir() / "decompose.json"
    if not outbox_file.exists():
        return None

    try:
        data = json.loads(outbox_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "sub_tasks" not in data:
            return None
        return DecomposeResult(**data)
    except (json.JSONDecodeError, Exception):
        return None


def parse_decompose_json(text: str) -> DecomposeResult | None:
    """Parse decomposition result from raw text (handles markdown fences)."""
    # Try extracting from ```json ... ```
    match = re.search(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and "sub_tasks" in data:
                return DecomposeResult(**data)
        except (json.JSONDecodeError, Exception):
            pass

    # Try parsing whole text as JSON
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and "sub_tasks" in data:
            return DecomposeResult(**data)
    except (json.JSONDecodeError, Exception):
        pass

    return None


def topo_sort(sub_tasks: list[SubTask]) -> list[SubTask]:
    """Topologically sort sub-tasks by dependencies.

    Returns sub-tasks in execution order: tasks with no deps first,
    then tasks whose deps are satisfied, etc.
    Raises ValueError if circular dependency detected.
    """
    by_id = {st.id: st for st in sub_tasks}
    visited: set[str] = set()
    result: list[SubTask] = []
    visiting: set[str] = set()

    def visit(task_id: str):
        if task_id in visited:
            return
        if task_id in visiting:
            raise ValueError(f"Circular dependency detected involving '{task_id}'")
        visiting.add(task_id)

        task = by_id.get(task_id)
        if task is None:
            raise ValueError(f"Unknown dependency '{task_id}'")

        for dep in task.deps:
            visit(dep)

        visiting.discard(task_id)
        visited.add(task_id)
        result.append(task)

    for st in sub_tasks:
        visit(st.id)

    return result
