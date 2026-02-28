#!/usr/bin/env python3
"""LangGraph-backed orchestration entrypoint for tri-IDE workflow.

This module mirrors ide_hub.py semantics but expresses the workflow as a StateGraph.
If LangGraph is unavailable, it exits with a clear fallback instruction.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, TypedDict

# Ensure workspace scripts are importable regardless of current working directory.
ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Reuse proven helper functions from the current hub.
from ide_hub import (
    ALLOWED_AGENTS,
    DEFAULT_AUDIT,
    DEFAULT_CONFIG,
    DEFAULT_HANDOFF_DIR,
    DEFAULT_PROMPT_DIR,
    DEFAULT_SESSION_DIR,
    apply_event_chain,
    ensure_owner_agent,
    generate_all_prompts,
    infer_event,
    initialize_session,
    parse_result_json,
    read_text,
    save_handoff,
)
from mvp_ctl import load_json as load_task_json, validate_task
from workmode_ctl import load_yaml, next_action, session_path, validate_config


class WorkflowState(TypedDict, total=False):
    operation: str
    task_path: str
    config_path: str
    mode: str
    session_dir: str
    prompt_dir: str
    audit_log: str
    handoff_dir: str
    requeue: bool
    agent: str
    reason: str
    raw_result: str

    # outputs
    task_id: str
    state: str
    current_agent: str
    current_role: str
    session_file: str
    prompt_map: dict[str, str]
    active_prompt: str
    next_action: dict[str, Any]
    handoff_file: str
    applied_events: list[str]
    copied_active_prompt: bool


def require_langgraph():
    try:
        from langgraph.graph import END, START, StateGraph  # noqa: F401
    except Exception as exc:  # pragma: no cover - env dependent
        raise RuntimeError(
            "LangGraph is not installed in this environment. "
            "Use /Volumes/Seagate/Multi-Agent/scripts/ide_hub.py for now, "
            "or install langgraph into your project environment first."
        ) from exc


# ---------- Nodes ----------

def node_start(state: WorkflowState) -> WorkflowState:
    task_path = pathlib.Path(state["task_path"])
    config_path = pathlib.Path(state["config_path"])
    session_dir = pathlib.Path(state["session_dir"])
    prompt_dir = pathlib.Path(state["prompt_dir"])
    audit_log = pathlib.Path(state["audit_log"])

    _, task, session, session_file = initialize_session(
        task_path=task_path,
        config_path=config_path,
        mode=state["mode"],
        session_dir=session_dir,
        audit_log=audit_log,
        requeue=bool(state.get("requeue", False)),
    )
    prompt_map = generate_all_prompts(task_path, task, session, prompt_dir)
    active_agent = session["current_agent"]

    return {
        "task_id": task["task_id"],
        "state": task["state"],
        "current_agent": active_agent,
        "current_role": session["current_role"],
        "session_file": str(session_file),
        "prompt_map": prompt_map,
        "active_prompt": prompt_map[active_agent],
        "copied_active_prompt": False,
    }


def node_status(state: WorkflowState) -> WorkflowState:
    task_path = pathlib.Path(state["task_path"])
    task = load_task_json(task_path)
    task_errors = validate_task(task)
    if task_errors:
        raise ValueError("; ".join(task_errors))

    s_path = session_path(task["task_id"], pathlib.Path(state["session_dir"]))
    if not s_path.exists():
        raise ValueError(f"session not found: {s_path}")
    session = load_task_json(s_path)

    action = next_action(task, session, session["current_agent"])
    prompt_map = {
        a: str(pathlib.Path(state["prompt_dir"]) / f"current-{a}.txt") for a in sorted(ALLOWED_AGENTS)
    }

    return {
        "task_id": task["task_id"],
        "state": task["state"],
        "current_agent": session.get("current_agent", ""),
        "current_role": session.get("current_role", ""),
        "next_action": action,
        "prompt_map": prompt_map,
    }


def node_parse_submit(state: WorkflowState) -> WorkflowState:
    task_path = pathlib.Path(state["task_path"])
    task = load_task_json(task_path)
    task_errors = validate_task(task)
    if task_errors:
        raise ValueError("; ".join(task_errors))

    s_path = session_path(task["task_id"], pathlib.Path(state["session_dir"]))
    if not s_path.exists():
        raise ValueError(f"session not found: {s_path}")
    session = load_task_json(s_path)

    agent = state["agent"]
    ensure_owner_agent(task, session, agent)

    payload = parse_result_json(state["raw_result"])

    # strict identity validation
    if payload.get("task_id") != task["task_id"]:
        raise ValueError(f"payload.task_id mismatch: {payload.get('task_id')} != {task['task_id']}")
    if payload.get("agent") != agent:
        raise ValueError(f"payload.agent mismatch: {payload.get('agent')} != {agent}")

    role = session["current_role"]
    payload_role = payload.get("role")
    if payload_role and payload_role != role:
        raise ValueError(f"payload.role mismatch: {payload_role} != {role}")

    event = infer_event(role, payload)
    if not event:
        raise ValueError("cannot infer event from payload")

    handoff_file = save_handoff(task["task_id"], agent, payload, pathlib.Path(state["handoff_dir"]))

    return {
        "task_id": task["task_id"],
        "state": task["state"],
        "event": event,
        "handoff_file": str(handoff_file),
    }


def node_progress_submit(state: WorkflowState) -> WorkflowState:
    task_path = pathlib.Path(state["task_path"])
    config_path = pathlib.Path(state["config_path"])
    session_dir = pathlib.Path(state["session_dir"])
    prompt_dir = pathlib.Path(state["prompt_dir"])

    cfg = load_yaml(config_path)
    cfg_errors = validate_config(cfg)
    if cfg_errors:
        raise ValueError("; ".join(cfg_errors))

    task = load_task_json(task_path)
    s_path = session_path(task["task_id"], session_dir)
    session = load_task_json(s_path)

    task, session, applied = apply_event_chain(
        task_path=task_path,
        task=task,
        session=session,
        cfg=cfg,
        event=state["event"],
        actor=state["agent"],
        reason=state.get("reason", "agent submitted result"),
        audit_log=pathlib.Path(state["audit_log"]),
        session_dir=session_dir,
    )

    prompt_map = generate_all_prompts(task_path, task, session, prompt_dir)
    active_agent = session["current_agent"]

    return {
        "task_id": task["task_id"],
        "state": task["state"],
        "current_agent": active_agent,
        "current_role": session["current_role"],
        "active_prompt": prompt_map[active_agent],
        "prompt_map": prompt_map,
        "applied_events": applied,
    }


def route_operation(state: WorkflowState) -> str:
    op = state.get("operation", "")
    if op == "start":
        return "start"
    if op == "status":
        return "status"
    if op == "submit":
        return "submit_parse"
    raise ValueError(f"unsupported operation: {op}")


def build_graph():
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(WorkflowState)
    g.add_node("start", node_start)
    g.add_node("status", node_status)
    g.add_node("submit_parse", node_parse_submit)
    g.add_node("submit_progress", node_progress_submit)

    g.add_conditional_edges(START, route_operation, {
        "start": "start",
        "status": "status",
        "submit_parse": "submit_parse",
    })

    g.add_edge("start", END)
    g.add_edge("status", END)
    g.add_edge("submit_parse", "submit_progress")
    g.add_edge("submit_progress", END)
    return g.compile()


def invoke_graph(initial: WorkflowState) -> WorkflowState:
    require_langgraph()
    app = build_graph()
    out = app.invoke(initial)
    if not isinstance(out, dict):
        raise RuntimeError("unexpected graph output")
    return out


def read_submit_input(result: str | None, result_file: str | None) -> str:
    if result_file:
        return read_text(pathlib.Path(result_file))
    if result:
        return result
    if sys.stdin.isatty():
        print("请粘贴 IDE 输出（含 JSON），结束后按 Ctrl-D：", file=sys.stderr)
    return sys.stdin.read()


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_start(args: argparse.Namespace) -> int:
    try:
        out = invoke_graph(
            {
                "operation": "start",
                "task_path": args.task,
                "config_path": args.config,
                "mode": args.mode,
                "session_dir": args.session_dir,
                "prompt_dir": args.prompt_dir,
                "audit_log": args.audit_log,
                "handoff_dir": args.handoff_dir,
                "requeue": args.requeue,
            }
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print_json(
        {
            "status": "started",
            "task_id": out.get("task_id"),
            "state": out.get("state"),
            "current_agent": out.get("current_agent"),
            "current_role": out.get("current_role"),
            "session_file": out.get("session_file"),
            "active_prompt": out.get("active_prompt"),
            "prompts": out.get("prompt_map", {}),
            "copied_active_prompt": False,
        }
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    try:
        out = invoke_graph(
            {
                "operation": "status",
                "task_path": args.task,
                "config_path": args.config,
                "mode": args.mode,
                "session_dir": args.session_dir,
                "prompt_dir": args.prompt_dir,
                "audit_log": args.audit_log,
                "handoff_dir": args.handoff_dir,
                "requeue": False,
            }
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print_json(
        {
            "task_id": out.get("task_id"),
            "state": out.get("state"),
            "current_agent": out.get("current_agent"),
            "current_role": out.get("current_role"),
            "next_action": out.get("next_action"),
            "prompt_paths": out.get("prompt_map", {}),
        }
    )
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    raw = read_submit_input(args.result, args.result_file)

    try:
        out = invoke_graph(
            {
                "operation": "submit",
                "task_path": args.task,
                "config_path": args.config,
                "mode": args.mode,
                "session_dir": args.session_dir,
                "prompt_dir": args.prompt_dir,
                "audit_log": args.audit_log,
                "handoff_dir": args.handoff_dir,
                "requeue": False,
                "agent": args.agent,
                "reason": args.reason,
                "raw_result": raw,
            }
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print_json(
        {
            "status": "submitted",
            "task_id": out.get("task_id"),
            "applied_events": out.get("applied_events", []),
            "state": out.get("state"),
            "current_agent": out.get("current_agent"),
            "current_role": out.get("current_role"),
            "active_prompt": out.get("active_prompt"),
            "prompts": out.get("prompt_map", {}),
            "handoff_file": out.get("handoff_file"),
            "copied_active_prompt": False,
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="LangGraph Hub（start / status / submit）")
    sub = p.add_subparsers(dest="command", required=True)

    for cmd in ("start", "status", "submit"):
        sp = sub.add_parser(cmd)
        sp.add_argument("--task", required=True)
        sp.add_argument("--config", default=DEFAULT_CONFIG)
        sp.add_argument("--mode", default="strict")
        sp.add_argument("--session-dir", default=DEFAULT_SESSION_DIR)
        sp.add_argument("--prompt-dir", default=DEFAULT_PROMPT_DIR)
        sp.add_argument("--audit-log", default=DEFAULT_AUDIT)
        sp.add_argument("--handoff-dir", default=DEFAULT_HANDOFF_DIR)

    s = sub.choices["start"]
    s.add_argument("--requeue", action="store_true")
    s.set_defaults(func=cmd_start)

    st = sub.choices["status"]
    st.set_defaults(func=cmd_status)

    sb = sub.choices["submit"]
    sb.add_argument("--agent", required=True, choices=sorted(ALLOWED_AGENTS))
    sb.add_argument("--result")
    sb.add_argument("--result-file")
    sb.add_argument("--reason", default="agent submitted result")
    sb.set_defaults(func=cmd_submit)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
