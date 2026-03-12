#!/usr/bin/env python3
"""Deterministic local CLI agent for visible multi-agent smoke/integration tests.

This script reads TASK.md (optional) and writes role-specific JSON outputs to outbox.
It is intentionally deterministic and does not call external services.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _decompose_payload() -> dict:
    return {
        "sub_tasks": [
            {
                "id": "user-model",
                "description": "定义用户实体、密码哈希与基本仓储接口",
                "done_criteria": ["User 模型及仓储接口可用", "密码哈希/校验函数可用"],
                "deps": [],
                "skill_id": "code-implement",
                "estimated_minutes": 40,
            },
            {
                "id": "auth-core",
                "description": "实现注册/登录/JWT 刷新核心服务",
                "done_criteria": ["注册登录与刷新令牌接口可用", "异常路径返回一致错误码"],
                "deps": ["user-model"],
                "skill_id": "code-implement",
                "estimated_minutes": 60,
            },
            {
                "id": "rbac-middleware",
                "description": "实现 RBAC 权限中间件和角色校验装饰器",
                "done_criteria": ["RBAC 中间件可复用", "关键接口权限校验生效"],
                "deps": ["auth-core"],
                "skill_id": "code-implement",
                "estimated_minutes": 45,
            },
            {
                "id": "audit-log",
                "description": "实现鉴权相关审计日志记录",
                "done_criteria": ["关键鉴权行为被记录", "日志包含最小必要字段"],
                "deps": ["auth-core"],
                "skill_id": "code-implement",
                "estimated_minutes": 35,
            },
            {
                "id": "openapi-tests",
                "description": "补充 OpenAPI 契约与单元测试",
                "done_criteria": ["OpenAPI 覆盖关键接口", "核心单测通过"],
                "deps": ["rbac-middleware", "audit-log"],
                "skill_id": "code-implement",
                "estimated_minutes": 50,
            },
        ],
        "reasoning": "按依赖关系拆分为 5 个中型子任务，包含可并行阶段（rbac/audit）。",
        "total_estimated_minutes": 230,
        "version": "1.0",
        "metadata": {"agent": "mock-cli", "created_at": _now()},
        "created_at": _now(),
    }


def _builder_payload(task_file: Path) -> dict:
    task_name = task_file.stem
    return {
        "status": "completed",
        "summary": f"mock builder completed {task_name}",
        "changed_files": [
            f"/Volumes/Seagate/Multi-Agent/artifacts/{task_name}/app/main.py",
            f"/Volumes/Seagate/Multi-Agent/artifacts/{task_name}/tests/test_auth.py",
        ],
        "check_results": {
            "lint": "pass",
            "unit_test": "pass",
            "contract_test": "pass",
            "artifact_checksum": "pass",
        },
        "risks": [],
        "handoff_notes": "mock handoff for integration testing",
    }


def _reviewer_payload(task_file: Path) -> dict:
    task_name = task_file.stem
    return {
        "decision": "approve",
        "summary": (
            f"Review accepted for {task_name}: done_criteria alignment, "
            "quality-gate consistency, and artifact scope were independently validated."
        ),
        "reasoning": (
            "Verified builder output fields against reviewer contract, re-checked "
            "quality gate statuses, confirmed changed_files scope is limited to "
            "task artifacts, and validated no contradictory risk signals."
        ),
        "evidence": [
            f"task={task_name}: builder payload includes status/summary/changed_files/check_results.",
            "check_results reports lint/unit_test/contract_test/artifact_checksum = pass.",
            "changed_files point to task-local artifact paths and do not escape workspace.",
            "No missing mandatory reviewer fields (decision/summary/reasoning/evidence).",
        ],
        "feedback": "",
        "issues": [],
        "risks": [],
        "recommended_event": "review_pass",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic local mock CLI agent")
    parser.add_argument("--task-file", required=True, help="TASK.md path")
    parser.add_argument("--outbox-file", required=True, help="output JSON path")
    args = parser.parse_args()

    task_file = Path(args.task_file).expanduser().resolve()
    outbox_file = Path(args.outbox_file).expanduser().resolve()
    role = outbox_file.stem.lower()

    if role == "decompose":
        payload = _decompose_payload()
    elif role == "builder":
        payload = _builder_payload(task_file)
    elif role == "reviewer":
        payload = _reviewer_payload(task_file)
    else:
        payload = {
            "status": "error",
            "summary": f"unsupported outbox role: {role}",
            "created_at": _now(),
        }

    _write_json(outbox_file, payload)
    print(f"mock_cli_agent wrote: {outbox_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
