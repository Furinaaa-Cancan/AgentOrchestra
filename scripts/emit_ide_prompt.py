#!/usr/bin/env python3
"""Emit role-specific prompt text for IDE agents from task/session state."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

TERMINAL_STATES = {"DONE", "CANCELLED"}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"invalid JSON object: {path}")
    return data


def resolve_session_path(task: dict[str, Any], session: str | None, session_dir: str) -> pathlib.Path:
    if session:
        return pathlib.Path(session)
    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("task.task_id missing; pass --session explicitly")
    return pathlib.Path(session_dir) / f"{task_id}.session.json"


def role_for_agent(session: dict[str, Any], agent: str) -> str | None:
    roles = session.get("roles", {})
    if not isinstance(roles, dict):
        return None
    for role, role_agent in roles.items():
        if role_agent == agent:
            return role
    return None


def expected_event(role: str, state: str) -> str:
    if role == "builder" and state == "ASSIGNED":
        return "builder_start"
    if role == "builder" and state == "RUNNING":
        return "builder_done"
    if role == "reviewer" and state == "VERIFYING":
        return "review_pass | review_fail"
    if role == "orchestrator" and state == "APPROVED":
        return "merge_done"
    if role == "orchestrator" and state == "MERGED":
        return "close_done"
    if role == "orchestrator" and state == "RETRY":
        return "retry_dispatch"
    return "none"


def check_template(expected_checks: list[str]) -> dict[str, str]:
    return {chk: "pass|fail|not_run" for chk in expected_checks}


def build_active_prompt(task: dict[str, Any], session: dict[str, Any], agent: str, role: str, task_path: str) -> str:
    state = str(task.get("state", ""))
    task_id = str(task.get("task_id", ""))
    done_criteria = task.get("done_criteria", [])
    expected_checks = task.get("expected_checks", [])
    event = expected_event(role, state)

    lock_cmd = (
        "python3 /Volumes/Seagate/Multi-Agent/scripts/lockctl.py "
        "--db /Volumes/Seagate/Multi-Agent/runtime/locks.db "
        "acquire --task-id " + task_id + " --file-path <ABS_FILE_PATH> --ttl-sec 120"
    )

    release_cmd = (
        "python3 /Volumes/Seagate/Multi-Agent/scripts/lockctl.py "
        "--db /Volumes/Seagate/Multi-Agent/runtime/locks.db "
        "release --task-id " + task_id + " --file-path <ABS_FILE_PATH>"
    )

    submit_cmd = (
        "python3 /Volumes/Seagate/Multi-Agent/scripts/ide_hub.py submit "
        f"--task {task_path} "
        "--agent <AGENT>"
    )

    base = [
        "你是严格多 Agent 协作流程中的已分配执行者。",
        "",
        "任务上下文：",
        f"- task_id: {task_id}",
        f"- current_state: {state}",
        f"- your_agent_id: {agent}",
        f"- your_role: {role}",
        f"- expected_event_after_your_step: {event}",
        f"- done_criteria: {json.dumps(done_criteria, ensure_ascii=False)}",
        f"- expected_checks: {json.dumps(expected_checks, ensure_ascii=False)}",
        "",
        "硬性规则：",
        "- 只做你当前角色的职责。",
        "- 不要扩大任务范围。",
        "- 输出中的文件路径必须使用绝对路径。",
        "- 编辑共享文件时，先加锁，完成检查后释放锁。",
        "",
        "锁命令（按需使用）：",
        f"- acquire: {lock_cmd}",
        f"- release: {release_cmd}",
        "",
    ]

    if role == "builder":
        role_lines = [
            "Builder 目标：",
            "- 只实现当前任务范围内的改动。",
            "- 运行要求的检查项。",
            "- 输出交接信息给 Reviewer。",
            "",
            "请严格只返回一个 JSON 对象：",
            json.dumps(
                {
                    "agent": agent,
                    "role": "builder",
                    "task_id": task_id,
                    "status": "completed|blocked",
                    "summary": "本次实现内容摘要",
                    "changed_files": ["/abs/path/file1", "/abs/path/file2"],
                    "check_results": check_template(expected_checks if isinstance(expected_checks, list) else []),
                    "risks": ["风险1", "风险2"],
                    "handoff_notes": "给 reviewer 的说明",
                    "recommended_event": "builder_done|none",
                },
                ensure_ascii=False,
                indent=2,
            ),
            "",
            "返回 JSON 后，在终端执行（将你的原始输出粘贴进去，Ctrl-D 结束）：",
            submit_cmd.replace("<AGENT>", agent),
        ]
    elif role == "reviewer":
        role_lines = [
            "Reviewer 目标：",
            "- 对照 done_criteria 验证 builder 输出。",
            "- 校验 required checks 是否满足。",
            "- 给出 pass/fail 结论并附证据。",
            "",
            "请严格只返回一个 JSON 对象：",
            json.dumps(
                {
                    "agent": agent,
                    "role": "reviewer",
                    "task_id": task_id,
                    "decision": "pass|fail",
                    "summary": "评审摘要",
                    "failed_checks": ["contract_test"],
                    "evidence": ["关键证据"],
                    "risks": ["风险1"],
                    "recommended_event": "review_pass|review_fail",
                },
                ensure_ascii=False,
                indent=2,
            ),
            "",
            "返回 JSON 后，在终端执行（将你的原始输出粘贴进去，Ctrl-D 结束）：",
            submit_cmd.replace("<AGENT>", agent),
        ]
    else:
        role_lines = [
            "Orchestrator 目标：",
            "- 负责状态流转与角色分派。",
            "- 流转前校验角色输出是否完整。",
            "- 保持审计链完整可追踪。",
            "",
            "请严格只返回一个 JSON 对象：",
            json.dumps(
                {
                    "agent": agent,
                    "role": "orchestrator",
                    "task_id": task_id,
                    "decision": "dispatch|retry|escalate|merge|close",
                    "reason": "简短原因",
                    "next_event": "builder_start|builder_done|review_pass|review_fail|retry_dispatch|merge_done|close_done|none",
                    "notes": "执行备注",
                },
                ensure_ascii=False,
                indent=2,
            ),
        ]

    return "\n".join(base + role_lines)


def build_waiting_prompt(task: dict[str, Any], session: dict[str, Any], agent: str, role: str) -> str:
    owner = session.get("current_agent", "unknown")
    owner_role = session.get("current_role", "unknown")
    return "\n".join(
        [
            "你当前处于待命状态。",
            f"- task_id: {task.get('task_id', '')}",
            f"- your_agent_id: {agent}",
            f"- your_role: {role}",
            f"- current_owner_agent: {owner}",
            f"- current_owner_role: {owner_role}",
            "",
            "现在不要执行任何改动。",
            "请严格返回下面这个 JSON：",
            json.dumps(
                {
                    "agent": agent,
                    "task_id": task.get("task_id", ""),
                    "status": "standby",
                    "reason": f"当前 owner 是 {owner_role}/{owner}",
                },
                ensure_ascii=False,
                indent=2,
            ),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="为 IDE agent 生成可复制提示词")
    parser.add_argument("--task", required=True, help="任务 JSON 路径")
    parser.add_argument("--agent", required=True, help="Agent id (codex|windsurf|antigravity)")
    parser.add_argument("--session", help="会话 JSON 路径；默认根据 task_id 推导")
    parser.add_argument("--session-dir", default="/Volumes/Seagate/Multi-Agent/runtime/sessions", help="会话目录")
    parser.add_argument("--out", help="可选：输出到文件")
    args = parser.parse_args()

    task = load_json(pathlib.Path(args.task))
    session_file = resolve_session_path(task, args.session, args.session_dir)
    if not session_file.exists():
        print(f"ERROR: session file not found: {session_file}", file=sys.stderr)
        return 1

    session = load_json(session_file)
    role = role_for_agent(session, args.agent)
    if role is None:
        print(f"ERROR: agent '{args.agent}' is not mapped in session roles", file=sys.stderr)
        return 1

    state = str(task.get("state", ""))
    task_path = str(pathlib.Path(args.task).resolve())
    actionable = args.agent == session.get("current_agent") and role == session.get("current_role") and state not in TERMINAL_STATES
    if actionable:
        prompt = build_active_prompt(task, session, args.agent, role, task_path)
    else:
        prompt = build_waiting_prompt(task, session, args.agent, role)

    if args.out:
        out_path = pathlib.Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(prompt + "\n", encoding="utf-8")
    else:
        print(prompt)

    return 0


if __name__ == "__main__":
    sys.exit(main())
