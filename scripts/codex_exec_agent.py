#!/usr/bin/env python3
"""Codex CLI adapter agent.

Runs `codex exec` with a role-specific prompt and writes normalized JSON
to the requested outbox file.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read_requirement(task_file: Path) -> str:
    if not task_file.exists():
        return "N/A"
    text = task_file.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"需求[:：]\s*(.+)", text)
    if m:
        return m.group(1).strip()[:800]
    return text[:1200].strip() or "N/A"


def _prompt_for_role(role: str, task_file: Path, outbox_file: Path) -> str:
    requirement = _read_requirement(task_file)
    common = (
        "你是 Multi-Agent 系统里的自动化执行器。"
        "你必须只输出一个 JSON 对象，不要输出 markdown，不要解释。"
        f"task_file={task_file} outbox_file={outbox_file}."
    )
    if role == "decompose":
        return (
            common
            + f" requirement={requirement}"
            + ' 输出字段严格为: {"sub_tasks":[{"id":"...","description":"...","done_criteria":["..."],"deps":[],"skill_id":"code-implement","estimated_minutes":30}],"reasoning":"...","total_estimated_minutes":120,"version":"1.0","created_at":"'
            + _now()
            + '"}.'
            " 要求生成 4~6 个中型子任务，存在合理依赖。"
        )
    if role == "builder":
        return (
            common
            + " 先读取 task_file，并在 project_root 中实际完成实现与必要校验；不要只做总结。"
            + " 若无法完成，status 必须写 blocked 并给出阻塞原因。"
            + ' 输出字段严格为: {"status":"completed","summary":"...","changed_files":["/abs/path"],"check_results":{"lint":"pass","unit_test":"pass","contract_test":"pass","artifact_checksum":"pass"},"risks":[],"handoff_notes":"..."}.'
            " status 只能是 completed/blocked/error。"
        )
    if role == "reviewer":
        return (
            common
            + " 先读取 task_file，并独立审查 builder 的实现与检查结果；不要只做总结。"
            + ' 输出字段严格为: {"decision":"approve","summary":"...","reasoning":"...","evidence":["..."],"issues":[],"feedback":"","risks":[],"recommended_event":"review_pass"}.'
            " decision 只能是 approve/reject/request_changes。"
        )
    return common + ' 输出: {"status":"error","summary":"unsupported role"}'


def _extract_json_candidates(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in re.finditer(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL):
        try:
            d = json.loads(m.group(1))
            if isinstance(d, dict):
                out.append(d)
        except json.JSONDecodeError:
            pass
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{") or not line.endswith("}"):
            continue
        try:
            d = json.loads(line)
            if isinstance(d, dict):
                out.append(d)
        except json.JSONDecodeError:
            pass
    for m in re.finditer(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", text):
        raw = m.group(1)
        try:
            d = json.loads(raw)
            if isinstance(d, dict) and len(d) >= 2:
                out.append(d)
        except json.JSONDecodeError:
            pass
    return out


def _normalize_decompose(data: dict[str, Any]) -> dict[str, Any]:
    sub_tasks = data.get("sub_tasks")
    if not isinstance(sub_tasks, list) or not sub_tasks:
        sub_tasks = [
            {
                "id": "task-core",
                "description": "实现核心功能",
                "done_criteria": ["核心功能可运行"],
                "deps": [],
                "skill_id": "code-implement",
                "estimated_minutes": 40,
            },
            {
                "id": "task-tests",
                "description": "补充测试与验证",
                "done_criteria": ["测试通过"],
                "deps": ["task-core"],
                "skill_id": "code-implement",
                "estimated_minutes": 30,
            },
        ]
    return {
        "sub_tasks": sub_tasks,
        "reasoning": str(data.get("reasoning", "基于依赖关系拆分")),
        "total_estimated_minutes": int(data.get("total_estimated_minutes", 120)),
        "version": str(data.get("version", "1.0")),
        "created_at": str(data.get("created_at", _now())),
    }


def _normalize_builder(data: dict[str, Any], task_file: Path) -> dict[str, Any]:
    status = str(data.get("status", "blocked")).strip().lower()
    if status not in {"completed", "blocked", "error"}:
        status = "blocked"
    changed_files = data.get("changed_files")
    if not isinstance(changed_files, list):
        changed_files = []
    check_results = data.get("check_results")
    if not isinstance(check_results, dict):
        check_results = {
            "lint": "skip",
            "unit_test": "skip",
            "contract_test": "skip",
            "artifact_checksum": "skip",
        }
    return {
        "status": status,
        "summary": str(data.get("summary", "codex builder output incomplete")),
        "changed_files": [str(x) for x in changed_files if str(x).strip()],
        "check_results": check_results,
        "risks": data.get("risks", []),
        "handoff_notes": str(data.get("handoff_notes", "generated by codex_cli adapter")),
    }


def _normalize_reviewer(data: dict[str, Any]) -> dict[str, Any]:
    decision = str(data.get("decision", "request_changes")).strip().lower()
    if decision not in {"approve", "reject", "request_changes"}:
        decision = "request_changes"
    evidence = data.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        evidence = []
    return {
        "decision": decision,
        "summary": str(data.get("summary", "codex reviewer decision generated")),
        "reasoning": str(data.get("reasoning", "Need stronger reviewer evidence and verification.")),
        "evidence": [str(x) for x in evidence if str(x).strip()],
        "issues": data.get("issues", []),
        "feedback": str(data.get("feedback", "Need additional verification evidence.")),
        "risks": data.get("risks", []),
        "recommended_event": str(data.get("recommended_event", "review_fail")),
    }


def _normalize(role: str, data: dict[str, Any], task_file: Path) -> dict[str, Any]:
    if role == "decompose":
        return _normalize_decompose(data)
    if role == "builder":
        return _normalize_builder(data, task_file)
    if role == "reviewer":
        return _normalize_reviewer(data)
    return {"status": "error", "summary": f"unsupported role: {role}", "created_at": _now()}


def _run_codex(prompt: str, project_root: Path, timeout_sec: int) -> tuple[int, str]:
    cmd = [
        "codex",
        "exec",
        prompt,
        "--full-auto",
        "-s",
        "workspace-write",
        "--skip-git-repo-check",
        "-C",
        str(project_root),
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return proc.returncode, proc.stdout or ""
    except subprocess.TimeoutExpired as exc:
        partial = ""
        if isinstance(exc.stdout, str):
            partial = exc.stdout
        return 124, partial


def _fallback_payload(role: str, task_file: Path, rc: int) -> dict[str, Any]:
    if role == "decompose":
        return _normalize_decompose({})
    if role == "builder":
        return {
            "status": "blocked",
            "summary": f"adapter fallback blocked (codex rc={rc})",
            "changed_files": [],
            "check_results": {
                "lint": "skip",
                "unit_test": "skip",
                "contract_test": "skip",
                "artifact_checksum": "skip",
            },
            "risks": [f"codex exec fallback used rc={rc}"],
            "handoff_notes": "generated by codex_cli adapter fallback",
            "_adapter_fallback": True,
        }
    if role == "reviewer":
        return {
            "decision": "request_changes",
            "summary": f"adapter fallback request_changes (codex rc={rc})",
            "reasoning": "Fallback path used due codex execution issue.",
            "evidence": [],
            "issues": ["adapter fallback active"],
            "feedback": "codex reviewer execution unstable; rerun review with concrete evidence",
            "risks": [f"codex exec fallback used rc={rc}"],
            "recommended_event": "review_fail",
            "_adapter_fallback": True,
        }
    return {"status": "error", "summary": f"unsupported role: {role}"}


def _select_payload(
    role: str,
    task_file: Path,
    rc: int,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Choose normalized payload with conservative fallback semantics.

    Policy:
    - If no parseable JSON candidate exists, use strict fallback payload.
    - If candidate exists, keep parsed payload even when rc != 0, but mark
      transport instability via adapter metadata for observability.
    """
    if not candidates:
        return _fallback_payload(role, task_file, rc)

    payload = _normalize(role, candidates[-1], task_file)
    if rc != 0:
        payload = dict(payload)
        payload["_adapter_nonzero_rc"] = True
        payload["_adapter_exit_code"] = rc
        if role in {"builder", "reviewer"}:
            risks = payload.get("risks")
            if not isinstance(risks, list):
                risks = []
            note = f"codex exec exited with rc={rc}; using parsed JSON output"
            if note not in risks:
                risks.append(note)
            payload["risks"] = risks
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex CLI adapter agent")
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--outbox-file", required=True)
    parser.add_argument("--timeout-sec", type=int, default=90)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    task_file = Path(args.task_file).expanduser().resolve()
    outbox_file = Path(args.outbox_file).expanduser().resolve()
    project_root = Path(args.project_root).expanduser().resolve()
    role = outbox_file.stem.lower()

    prompt = _prompt_for_role(role, task_file, outbox_file)
    rc, output = _run_codex(prompt, project_root, timeout_sec=max(30, args.timeout_sec))
    cands = _extract_json_candidates(output)
    payload = _select_payload(role, task_file, rc, cands)

    outbox_file.parent.mkdir(parents=True, exist_ok=True)
    outbox_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"codex_exec_agent wrote: {outbox_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
