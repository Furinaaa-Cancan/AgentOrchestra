#!/usr/bin/env python3
"""Interactive hub for tri-IDE prompt workflow.

Use this script as the only terminal entrypoint:
1) start a task session and generate prompts for all IDE agents
2) submit one agent result and auto-progress state/event
3) regenerate next-round prompts automatically
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

from emit_ide_prompt import build_active_prompt, build_waiting_prompt, role_for_agent
from mvp_ctl import apply_transition, load_json as load_task_json, now_utc, validate_task
from workmode_ctl import (
    build_session,
    load_yaml,
    next_action,
    session_path,
    transition_by_event,
    validate_config,
    write_session,
)

DEFAULT_CONFIG = "/Volumes/Seagate/Multi-Agent/config/workmode.yaml"
DEFAULT_SESSION_DIR = "/Volumes/Seagate/Multi-Agent/runtime/sessions"
DEFAULT_PROMPT_DIR = "/Volumes/Seagate/Multi-Agent/prompts"
DEFAULT_AUDIT = "/Volumes/Seagate/Multi-Agent/runtime/audit.log.ndjson"
DEFAULT_HANDOFF_DIR = "/Volumes/Seagate/Multi-Agent/runtime/handoffs"

ALLOWED_AGENTS = {"codex", "windsurf", "antigravity"}


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def parse_result_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        raise ValueError("empty result text")

    # 1) direct JSON
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2) fenced code blocks (prefer the last valid JSON block)
    fences = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw, flags=re.IGNORECASE)
    last_valid: dict[str, Any] | None = None
    for block in fences:
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                last_valid = obj
        except json.JSONDecodeError:
            continue
    if last_valid is not None:
        return last_valid

    # 3) scan decodable JSON objects and prefer the last one
    decoder = json.JSONDecoder()
    scanned_valid: dict[str, Any] | None = None
    for idx, ch in enumerate(raw):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(raw[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            scanned_valid = obj
    if scanned_valid is not None:
        return scanned_valid

    raise ValueError("failed to parse JSON object from agent output")


def infer_event(role: str, payload: dict[str, Any]) -> str | None:
    recommended = payload.get("recommended_event")
    if isinstance(recommended, str) and recommended.strip() and recommended.strip() != "none":
        return recommended.strip()

    if role == "builder":
        status = str(payload.get("status", "")).lower()
        if status == "completed":
            return "builder_done"
        return None

    if role == "reviewer":
        decision = str(payload.get("decision", "")).lower()
        if decision == "pass":
            return "review_pass"
        if decision == "fail":
            return "review_fail"
        return None

    if role == "orchestrator":
        nxt = payload.get("next_event")
        if isinstance(nxt, str) and nxt.strip() and nxt.strip() != "none":
            return nxt.strip()
        decision = str(payload.get("decision", "")).lower()
        decision_map = {
            "merge": "merge_done",
            "close": "close_done",
            "retry": "retry_dispatch",
        }
        return decision_map.get(decision)

    return None


def initialize_session(
    task_path: pathlib.Path,
    config_path: pathlib.Path,
    mode: str,
    session_dir: pathlib.Path,
    audit_log: pathlib.Path,
    requeue: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], pathlib.Path]:
    cfg = load_yaml(config_path)
    cfg_errors = validate_config(cfg)
    if cfg_errors:
        raise ValueError("; ".join(cfg_errors))

    task = load_task_json(task_path)
    task_errors = validate_task(task)
    if task_errors:
        raise ValueError("; ".join(task_errors))

    if requeue:
        task["state"] = "QUEUED"
        task["owner"] = "planner"
        task["consumer"] = "pending"
        task["updated_at"] = now_utc()
        task.pop("error", None)
        with task_path.open("w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=True, indent=2, sort_keys=True)
            f.write("\n")

    if task["state"] == "QUEUED":
        apply_transition(
            task_path=task_path,
            to_state="ASSIGNED",
            actor="orchestrator",
            reason="ide-hub auto-dispatch",
            error_code=None,
            error_message=None,
            audit_log=audit_log,
        )
        task = load_task_json(task_path)

    session = build_session(task, cfg, mode)
    s_path = write_session(task_path, task, session, session_dir)
    return cfg, task, session, s_path


def render_prompt(task: dict[str, Any], session: dict[str, Any], agent: str, task_path: pathlib.Path) -> str:
    role = role_for_agent(session, agent)
    if role is None:
        raise ValueError(f"agent '{agent}' not mapped in session")
    state = str(task.get("state", ""))
    actionable = agent == session.get("current_agent") and role == session.get("current_role") and state not in {
        "DONE",
        "CANCELLED",
    }
    if actionable:
        return build_active_prompt(task, session, agent, role, str(task_path.resolve()))
    return build_waiting_prompt(task, session, agent, role)


def generate_all_prompts(task_path: pathlib.Path, task: dict[str, Any], session: dict[str, Any], prompt_dir: pathlib.Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for agent in sorted(ALLOWED_AGENTS):
        prompt = render_prompt(task, session, agent, task_path)
        out = prompt_dir / f"current-{agent}.txt"
        write_text(out, prompt + "\n")
        mapping[agent] = str(out)
    return mapping


def save_handoff(task_id: str, agent: str, payload: dict[str, Any], handoff_dir: pathlib.Path) -> pathlib.Path:
    out_dir = handoff_dir / task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"{now_compact()}-{agent}"
    out = out_dir / f"{base}.json"
    suffix = 1
    while out.exists():
        out = out_dir / f"{base}-{suffix}.json"
        suffix += 1
    with out.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "recorded_at": now_utc(),
                "agent": agent,
                "payload": payload,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
        f.write("\n")
    return out


def maybe_copy_to_clipboard(text: str) -> bool:
    if not shutil.which("pbcopy"):
        return False
    try:
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
    except subprocess.SubprocessError:
        return False
    return True


def ensure_owner_agent(task: dict[str, Any], session: dict[str, Any], agent: str) -> None:
    owner = session.get("current_agent")
    if owner != agent:
        raise ValueError(f"current owner is '{owner}', not '{agent}'")


def apply_event_chain(
    task_path: pathlib.Path,
    task: dict[str, Any],
    session: dict[str, Any],
    cfg: dict[str, Any],
    event: str,
    actor: str,
    reason: str,
    audit_log: pathlib.Path,
    session_dir: pathlib.Path,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    applied: list[str] = []

    # UX bridge: if builder forgets builder_start and directly submits builder_done from ASSIGNED,
    # auto-apply builder_start first.
    if event == "builder_done" and task["state"] == "ASSIGNED":
        task, session, _ = transition_by_event(
            task_path=task_path,
            session=session,
            cfg=cfg,
            event_name="builder_start",
            actor=actor,
            reason="auto-bridge before builder_done",
            audit_log=audit_log,
            session_dir=session_dir,
        )
        applied.append("builder_start")

    task, session, _ = transition_by_event(
        task_path=task_path,
        session=session,
        cfg=cfg,
        event_name=event,
        actor=actor,
        reason=reason,
        audit_log=audit_log,
        session_dir=session_dir,
    )
    applied.append(event)

    return task, session, applied


def command_start(args: argparse.Namespace) -> int:
    task_path = pathlib.Path(args.task)
    config_path = pathlib.Path(args.config)
    session_dir = pathlib.Path(args.session_dir)
    prompt_dir = pathlib.Path(args.prompt_dir)

    try:
        _, task, session, session_file = initialize_session(
            task_path=task_path,
            config_path=config_path,
            mode=args.mode,
            session_dir=session_dir,
            audit_log=pathlib.Path(args.audit_log),
            requeue=args.requeue,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    prompt_map = generate_all_prompts(task_path, task, session, prompt_dir)
    active_agent = session["current_agent"]
    active_prompt_path = prompt_map[active_agent]

    copied = False
    if args.copy_active:
        copied = maybe_copy_to_clipboard(read_text(pathlib.Path(active_prompt_path)))

    print(
        json.dumps(
            {
                "status": "started",
                "task_id": task["task_id"],
                "state": task["state"],
                "current_agent": active_agent,
                "current_role": session["current_role"],
                "session_file": str(session_file),
                "active_prompt": active_prompt_path,
                "prompts": prompt_map,
                "copied_active_prompt": copied,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_status(args: argparse.Namespace) -> int:
    task_path = pathlib.Path(args.task)
    task = load_task_json(task_path)
    task_errors = validate_task(task)
    if task_errors:
        for err in task_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    s_path = session_path(task["task_id"], pathlib.Path(args.session_dir))
    if not s_path.exists():
        print(f"ERROR: session not found: {s_path}", file=sys.stderr)
        return 1

    session = load_task_json(s_path)
    action = next_action(task, session, session["current_agent"])

    payload = {
        "task_id": task["task_id"],
        "state": task["state"],
        "current_agent": session.get("current_agent"),
        "current_role": session.get("current_role"),
        "next_action": action,
        "prompt_paths": {
            a: str(pathlib.Path(args.prompt_dir) / f"current-{a}.txt") for a in sorted(ALLOWED_AGENTS)
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_submit(args: argparse.Namespace) -> int:
    if args.agent not in ALLOWED_AGENTS:
        print(f"ERROR: unsupported agent '{args.agent}'", file=sys.stderr)
        return 1

    task_path = pathlib.Path(args.task)
    config_path = pathlib.Path(args.config)
    session_dir = pathlib.Path(args.session_dir)
    prompt_dir = pathlib.Path(args.prompt_dir)
    handoff_dir = pathlib.Path(args.handoff_dir)

    task = load_task_json(task_path)
    task_errors = validate_task(task)
    if task_errors:
        for err in task_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    s_path = session_path(task["task_id"], session_dir)
    if not s_path.exists():
        print(f"ERROR: session not found: {s_path}", file=sys.stderr)
        return 1
    session = load_task_json(s_path)

    try:
        ensure_owner_agent(task, session, args.agent)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    raw: str
    if args.result_file:
        raw = read_text(pathlib.Path(args.result_file))
    elif args.result:
        raw = args.result
    else:
        if sys.stdin.isatty():
            print("请粘贴 IDE 输出（含 JSON），结束后按 Ctrl-D：", file=sys.stderr)
        raw = sys.stdin.read()

    try:
        payload = parse_result_json(raw)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    role = role_for_agent(session, args.agent)
    if role is None:
        print(f"ERROR: agent '{args.agent}' not mapped in session", file=sys.stderr)
        return 1

    # Strict payload identity checks to prevent cross-task/cross-agent misuse.
    payload_task_id = payload.get("task_id")
    if payload_task_id != task["task_id"]:
        print(
            f"ERROR: payload.task_id mismatch ({payload_task_id} != {task['task_id']})",
            file=sys.stderr,
        )
        return 1

    payload_agent = payload.get("agent")
    if payload_agent != args.agent:
        print(
            f"ERROR: payload.agent mismatch ({payload_agent} != {args.agent})",
            file=sys.stderr,
        )
        return 1

    payload_role = payload.get("role")
    if payload_role and payload_role != role:
        print(
            f"ERROR: payload.role mismatch ({payload_role} != {role})",
            file=sys.stderr,
        )
        return 1

    event = infer_event(role, payload)
    if not event:
        print("ERROR: cannot infer event from payload; provide recommended_event or role-specific decision", file=sys.stderr)
        return 1

    cfg = load_yaml(config_path)
    cfg_errors = validate_config(cfg)
    if cfg_errors:
        for err in cfg_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    handoff_file = save_handoff(task["task_id"], args.agent, payload, handoff_dir)

    try:
        task, session, applied = apply_event_chain(
            task_path=task_path,
            task=task,
            session=session,
            cfg=cfg,
            event=event,
            actor=args.agent,
            reason=args.reason,
            audit_log=pathlib.Path(args.audit_log),
            session_dir=session_dir,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    prompt_map = generate_all_prompts(task_path, task, session, prompt_dir)
    active_agent = session["current_agent"]
    active_prompt_path = prompt_map[active_agent]

    copied = False
    if args.copy_active:
        copied = maybe_copy_to_clipboard(read_text(pathlib.Path(active_prompt_path)))

    print(
        json.dumps(
            {
                "status": "submitted",
                "task_id": task["task_id"],
                "applied_events": applied,
                "state": task["state"],
                "current_agent": active_agent,
                "current_role": session["current_role"],
                "active_prompt": active_prompt_path,
                "prompts": prompt_map,
                "handoff_file": str(handoff_file),
                "copied_active_prompt": copied,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tri-IDE 交互 Hub（start / submit / status）")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="初始化会话并生成三端提示词")
    p.add_argument("--task", required=True, help="任务 JSON 路径")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="workmode 配置路径")
    p.add_argument("--mode", default="strict", help="模式名")
    p.add_argument("--session-dir", default=DEFAULT_SESSION_DIR, help="session 目录")
    p.add_argument("--prompt-dir", default=DEFAULT_PROMPT_DIR, help="提示词输出目录")
    p.add_argument("--audit-log", default=DEFAULT_AUDIT, help="审计日志路径")
    p.add_argument("--requeue", action="store_true", help="先将任务重置为 QUEUED 再启动（用于重复实验）")
    p.add_argument("--copy-active", action="store_true", help="将当前 owner 提示词复制到剪贴板（macOS pbcopy）")
    p.set_defaults(func=command_start)

    p = sub.add_parser("status", help="查看当前 owner 和下一步动作")
    p.add_argument("--task", required=True, help="任务 JSON 路径")
    p.add_argument("--session-dir", default=DEFAULT_SESSION_DIR, help="session 目录")
    p.add_argument("--prompt-dir", default=DEFAULT_PROMPT_DIR, help="提示词输出目录")
    p.set_defaults(func=command_status)

    p = sub.add_parser("submit", help="提交某 IDE 的 JSON 输出并自动推进")
    p.add_argument("--task", required=True, help="任务 JSON 路径")
    p.add_argument("--agent", required=True, help="提交结果的 agent（codex|windsurf|antigravity）")
    p.add_argument("--result", help="结果文本（可含 markdown 代码块）")
    p.add_argument("--result-file", help="结果文件路径")
    p.add_argument("--reason", default="agent submitted result", help="状态流转理由")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="workmode 配置路径")
    p.add_argument("--session-dir", default=DEFAULT_SESSION_DIR, help="session 目录")
    p.add_argument("--prompt-dir", default=DEFAULT_PROMPT_DIR, help="提示词输出目录")
    p.add_argument("--audit-log", default=DEFAULT_AUDIT, help="审计日志路径")
    p.add_argument("--handoff-dir", default=DEFAULT_HANDOFF_DIR, help="handoff 存档目录")
    p.add_argument("--copy-active", action="store_true", help="将下一位 owner 提示词复制到剪贴板")
    p.set_defaults(func=command_submit)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
