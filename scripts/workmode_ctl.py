#!/usr/bin/env python3
"""Workmode controller: deterministic tri-IDE orchestration with strict roles."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter
from typing import Any

import yaml

# Reuse strict validators/state transitions from MVP controller.
from mvp_ctl import apply_transition, load_json, now_utc, save_json, validate_task

DEFAULT_CONFIG = "config/workmode.yaml"
DEFAULT_AUDIT = "runtime/audit.log.ndjson"
DEFAULT_SESSION_DIR = "runtime/sessions"


def load_yaml(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"invalid yaml object: {path}")
    return data


def validate_config(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if cfg.get("version") != 1:
        errors.append("config.version must be 1")

    modes = cfg.get("modes")
    if not isinstance(modes, dict) or not modes:
        errors.append("config.modes must be a non-empty map")
    else:
        for mode_name, mode_cfg in modes.items():
            if not isinstance(mode_cfg, dict):
                errors.append(f"mode '{mode_name}' must be a map")
                continue
            roles = mode_cfg.get("roles")
            if not isinstance(roles, dict):
                errors.append(f"mode '{mode_name}' must contain roles map")
                continue
            for role in ("orchestrator", "builder", "reviewer"):
                if role not in roles or not isinstance(roles[role], str) or len(roles[role].strip()) < 2:
                    errors.append(f"mode '{mode_name}' missing roles.{role}")

            role_priority = mode_cfg.get("role_priority")
            if not isinstance(role_priority, list) or not role_priority:
                errors.append(f"mode '{mode_name}' must contain role_priority list")

    routing = cfg.get("routing")
    if not isinstance(routing, dict):
        errors.append("config.routing must be a map")
    else:
        mapping = routing.get("capability_to_role")
        if not isinstance(mapping, dict) or not mapping:
            errors.append("config.routing.capability_to_role must be a non-empty map")
        default_role = routing.get("default_role")
        if default_role not in {"orchestrator", "builder", "reviewer"}:
            errors.append("config.routing.default_role must be orchestrator|builder|reviewer")

    events = cfg.get("events")
    if not isinstance(events, dict) or not events:
        errors.append("config.events must be a non-empty map")
    else:
        for event_name, event_cfg in events.items():
            if not isinstance(event_cfg, dict):
                errors.append(f"event '{event_name}' must be a map")
                continue
            for field in ("from", "to", "next_role"):
                if field not in event_cfg:
                    errors.append(f"event '{event_name}' missing field '{field}'")

    guardrails = cfg.get("guardrails")
    if not isinstance(guardrails, dict):
        errors.append("config.guardrails must be a map")

    return errors


def mode_config(cfg: dict[str, Any], mode: str) -> dict[str, Any]:
    modes = cfg["modes"]
    if mode not in modes:
        raise ValueError(f"unknown mode '{mode}'. available: {sorted(modes.keys())}")
    return modes[mode]


def choose_role(task: dict[str, Any], cfg: dict[str, Any], mode: str) -> str:
    required_caps = task.get("required_capabilities", [])
    mapping = cfg["routing"]["capability_to_role"]
    role_counter: Counter[str] = Counter()

    for cap in required_caps:
        role = mapping.get(cap)
        if role:
            role_counter[role] += 1

    if not role_counter:
        return cfg["routing"]["default_role"]

    profile = mode_config(cfg, mode)
    priorities = profile["role_priority"]
    best_score = max(role_counter.values())
    best_roles = {role for role, score in role_counter.items() if score == best_score}

    for role in priorities:
        if role in best_roles:
            return role

    return sorted(best_roles)[0]


def session_path(task_id: str, session_dir: pathlib.Path) -> pathlib.Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / f"{task_id}.session.json"


def role_for_state(state: str, default_role: str, events: dict[str, Any]) -> str:
    # Prefer explicit next_role from event definitions where target matches state.
    for event_cfg in events.values():
        if event_cfg.get("to") == state:
            next_role = event_cfg.get("next_role")
            if isinstance(next_role, str):
                return next_role

    # Fallback map for terminal and queue states.
    fallback = {
        "DRAFT": "orchestrator",
        "QUEUED": "orchestrator",
        "ASSIGNED": default_role,
        "RUNNING": default_role,
        "VERIFYING": "reviewer",
        "APPROVED": "orchestrator",
        "MERGED": "orchestrator",
        "DONE": "orchestrator",
        "FAILED": "orchestrator",
        "RETRY": "orchestrator",
        "ESCALATED": "orchestrator",
        "CANCELLED": "orchestrator",
    }
    return fallback.get(state, "orchestrator")


def build_session(task: dict[str, Any], cfg: dict[str, Any], mode: str) -> dict[str, Any]:
    profile = mode_config(cfg, mode)
    roles = profile["roles"]
    default_role = choose_role(task, cfg, mode)
    state_role = role_for_state(task["state"], default_role, cfg["events"])

    owner_agent = roles[state_role]
    return {
        "version": 1,
        "mode": mode,
        "task_id": task["task_id"],
        "trace_id": task["trace_id"],
        "roles": roles,
        "default_execution_role": default_role,
        "current_role": state_role,
        "current_agent": owner_agent,
        "updated_at": now_utc(),
    }


def write_session(task_path: pathlib.Path, task: dict[str, Any], session: dict[str, Any], session_dir: pathlib.Path) -> pathlib.Path:
    s_path = session_path(task["task_id"], session_dir)
    with s_path.open("w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=True, indent=2, sort_keys=True)
        f.write("\n")

    task["consumer"] = session["current_agent"]
    task["owner"] = session["current_role"]
    task["updated_at"] = now_utc()
    save_json(task_path, task)
    return s_path


def next_action(task: dict[str, Any], session: dict[str, Any], agent_id: str) -> dict[str, Any]:
    role_for_agent = None
    for role, aid in session["roles"].items():
        if aid == agent_id:
            role_for_agent = role
            break

    if role_for_agent is None:
        return {
            "task_id": task["task_id"],
            "agent": agent_id,
            "actionable": False,
            "reason": "agent is not registered in this session",
        }

    current_role = session["current_role"]
    if role_for_agent != current_role:
        return {
            "task_id": task["task_id"],
            "agent": agent_id,
            "actionable": False,
            "reason": f"current owner role is '{current_role}'",
            "next_owner_agent": session["current_agent"],
        }

    state = task["state"]
    if state in {"DONE", "CANCELLED"}:
        return {
            "task_id": task["task_id"],
            "agent": agent_id,
            "role": role_for_agent,
            "state": state,
            "actionable": False,
            "reason": f"task is terminal in state '{state}'",
        }

    checklist: list[str]
    event_hint: str

    if state == "ASSIGNED":
        checklist = [
            "Acquire lock(s) for target file(s)",
            "Confirm scope from done_criteria",
            "Start implementation and move to RUNNING",
        ]
        event_hint = "builder_start"
    elif state == "RUNNING":
        checklist = [
            "Implement only scoped changes",
            "Run expected checks",
            "Publish handoff artifact",
            "Release locks",
            "Move to VERIFYING",
        ]
        event_hint = "builder_done"
    elif state == "VERIFYING":
        checklist = [
            "Validate handoff report completeness",
            "Re-run critical checks if needed",
            "Decide APPROVED or RETRY/ESCALATED",
        ]
        event_hint = "review_pass or review_fail"
    elif state == "APPROVED":
        checklist = [
            "Merge approved patch",
            "Capture merge SHA in artifact",
            "Move to MERGED",
        ]
        event_hint = "merge_done"
    elif state == "MERGED":
        checklist = [
            "Archive task artifacts",
            "Mark task DONE",
        ]
        event_hint = "close_done"
    elif state == "RETRY":
        checklist = [
            "Re-dispatch task to builder",
            "Update retry count and reason",
        ]
        event_hint = "retry_dispatch"
    else:
        checklist = ["No action in current state"]
        event_hint = "none"

    return {
        "task_id": task["task_id"],
        "agent": agent_id,
        "role": role_for_agent,
        "state": state,
        "actionable": True,
        "checklist": checklist,
        "event_hint": event_hint,
    }


def transition_by_event(
    task_path: pathlib.Path,
    session: dict[str, Any],
    cfg: dict[str, Any],
    event_name: str,
    actor: str,
    reason: str,
    audit_log: pathlib.Path,
    session_dir: pathlib.Path,
) -> tuple[dict[str, Any], dict[str, Any], pathlib.Path]:
    events = cfg["events"]
    if event_name not in events:
        raise ValueError(f"unknown event '{event_name}'. available: {sorted(events.keys())}")

    event_cfg = events[event_name]
    from_state = event_cfg["from"]
    to_state = event_cfg["to"]
    next_role = event_cfg["next_role"]

    task = load_json(task_path)
    task_errors = validate_task(task)
    if task_errors:
        raise ValueError("task is invalid: " + "; ".join(task_errors))

    if task["state"] != from_state:
        raise ValueError(f"event '{event_name}' requires state {from_state}, current state is {task['state']}")

    updated_task = apply_transition(
        task_path=task_path,
        to_state=to_state,
        actor=actor,
        reason=reason,
        error_code=None,
        error_message=None,
        audit_log=audit_log,
    )

    roles = session["roles"]
    if next_role not in roles:
        raise ValueError(f"event '{event_name}' references unknown role '{next_role}'")

    session["current_role"] = next_role
    session["current_agent"] = roles[next_role]
    session["updated_at"] = now_utc()

    session_file = write_session(task_path, updated_task, session, session_dir)
    return updated_task, session, session_file


def command_validate_config(args: argparse.Namespace) -> int:
    cfg = load_yaml(pathlib.Path(args.config))
    errors = validate_config(cfg)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print("workmode config validation passed")
    return 0


def command_init_session(args: argparse.Namespace) -> int:
    cfg = load_yaml(pathlib.Path(args.config))
    errors = validate_config(cfg)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    task_path = pathlib.Path(args.task)
    task = load_json(task_path)
    task_errors = validate_task(task)
    if task_errors:
        for err in task_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    # UX default: initializing a queued task should immediately dispatch it to execution owner.
    if task["state"] == "QUEUED":
        apply_transition(
            task_path=task_path,
            to_state="ASSIGNED",
            actor="orchestrator",
            reason="init-session auto-dispatch",
            error_code=None,
            error_message=None,
            audit_log=pathlib.Path(DEFAULT_AUDIT),
        )
        task = load_json(task_path)

    session = build_session(task, cfg, args.mode)
    s_path = write_session(task_path, task, session, pathlib.Path(args.session_dir))

    print(
        json.dumps(
            {
                "status": "session_initialized",
                "mode": args.mode,
                "task_id": task["task_id"],
                "current_role": session["current_role"],
                "current_agent": session["current_agent"],
                "session_file": str(s_path),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


def command_next_action(args: argparse.Namespace) -> int:
    task_path = pathlib.Path(args.task)
    task = load_json(task_path)
    task_errors = validate_task(task)
    if task_errors:
        for err in task_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    s_path = session_path(task["task_id"], pathlib.Path(args.session_dir))
    if not s_path.exists():
        print(f"ERROR: session not found: {s_path}", file=sys.stderr)
        return 1
    session = load_json(s_path)

    action = next_action(task, session, args.agent)
    print(json.dumps(action, ensure_ascii=True, indent=2))
    return 0


def command_auto_progress(args: argparse.Namespace) -> int:
    cfg = load_yaml(pathlib.Path(args.config))
    errors = validate_config(cfg)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    task_path = pathlib.Path(args.task)
    task = load_json(task_path)

    s_path = session_path(task["task_id"], pathlib.Path(args.session_dir))
    if not s_path.exists():
        print(f"ERROR: session not found: {s_path}", file=sys.stderr)
        return 1
    session = load_json(s_path)

    try:
        updated_task, updated_session, session_file = transition_by_event(
            task_path=task_path,
            session=session,
            cfg=cfg,
            event_name=args.event,
            actor=args.actor,
            reason=args.reason,
            audit_log=pathlib.Path(args.audit_log),
            session_dir=pathlib.Path(args.session_dir),
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "progressed",
                "task_id": updated_task["task_id"],
                "state": updated_task["state"],
                "current_role": updated_session["current_role"],
                "current_agent": updated_session["current_agent"],
                "session_file": str(session_file),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auto workmode controller for tri-IDE collaboration")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-config", help="Validate workmode config")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="Path to workmode config YAML")
    p.set_defaults(func=command_validate_config)

    p = sub.add_parser("init-session", help="Initialize deterministic role session for a task")
    p.add_argument("--task", required=True, help="Path to task JSON")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="Path to workmode config YAML")
    p.add_argument("--mode", default="strict", help="Mode profile from config")
    p.add_argument("--session-dir", default=DEFAULT_SESSION_DIR, help="Path to session directory")
    p.set_defaults(func=command_init_session)

    p = sub.add_parser("next-action", help="Show actionable next step for one agent")
    p.add_argument("--task", required=True, help="Path to task JSON")
    p.add_argument("--agent", required=True, help="Agent ID (codex|windsurf|antigravity)")
    p.add_argument("--session-dir", default=DEFAULT_SESSION_DIR, help="Path to session directory")
    p.set_defaults(func=command_next_action)

    p = sub.add_parser("auto-progress", help="Progress task by event and auto-reassign owner")
    p.add_argument("--task", required=True, help="Path to task JSON")
    p.add_argument("--event", required=True, help="Event key defined in workmode config")
    p.add_argument("--actor", required=True, help="Actor applying this event")
    p.add_argument("--reason", default="workflow", help="Reason for transition")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="Path to workmode config YAML")
    p.add_argument("--audit-log", default=DEFAULT_AUDIT, help="Path to audit log")
    p.add_argument("--session-dir", default=DEFAULT_SESSION_DIR, help="Path to session directory")
    p.set_defaults(func=command_auto_progress)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
