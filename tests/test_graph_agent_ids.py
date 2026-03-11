from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


def _token_usage() -> dict[str, object]:
    return {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "cost": 0.001,
        "model": "test-model",
    }


def test_build_node_finops_uses_builder_id():
    from multi_agent.graph import build_node

    state = {
        "task_id": "task-build-id-1",
        "skill_id": "code-implement",
        "builder_id": "windsurf",
        "reviewer_id": "antigravity",
        "done_criteria": ["ok"],
        "timeout_sec": 600,
        "retry_budget": 2,
        "retry_count": 0,
        "conversation": [],
        "input_payload": {},
    }

    result_payload = {
        "status": "completed",
        "summary": "done",
        "check_results": {},
        "changed_files": ["/tmp/a.py"],
        "token_usage": _token_usage(),
    }

    with patch("multi_agent.graph.interrupt", return_value=result_payload), \
         patch("multi_agent.graph._is_cancelled", return_value=False), \
         patch("multi_agent.graph.load_contract", return_value=SimpleNamespace(quality_gates=[])), \
         patch("multi_agent.graph.render_reviewer_prompt", return_value="review"), \
         patch("multi_agent.graph.clear_outbox"), \
         patch("multi_agent.graph.write_inbox"), \
         patch("multi_agent.graph._write_task_md"), \
         patch("multi_agent.graph.write_dashboard"), \
         patch("multi_agent.graph.save_state_snapshot"), \
         patch("multi_agent.finops.record_task_usage") as mock_record:
        out = build_node(state)

    assert out["current_role"] == "reviewer"
    mock_record.assert_called_once()
    assert mock_record.call_args.kwargs["agent_id"] == "windsurf"


def test_review_node_finops_and_memory_use_reviewer_id():
    from multi_agent.graph import review_node

    state = {
        "task_id": "task-review-id-1",
        "builder_id": "windsurf",
        "reviewer_id": "antigravity",
        "timeout_sec": 600,
        "conversation": [],
    }

    result_payload = {
        "decision": "approve",
        "summary": "looks good",
        "token_usage": _token_usage(),
    }

    with patch("multi_agent.graph.interrupt", return_value=result_payload), \
         patch("multi_agent.graph._is_cancelled", return_value=False), \
         patch("multi_agent.graph.save_state_snapshot"), \
         patch("multi_agent.finops.record_task_usage") as mock_record, \
         patch("multi_agent.semantic_memory.capture_from_review") as mock_capture:
        out = review_node(state)

    assert out["reviewer_output"]["decision"] == "approve"
    mock_record.assert_called_once()
    assert mock_record.call_args.kwargs["agent_id"] == "antigravity"
    mock_capture.assert_called_once()
    assert mock_capture.call_args.kwargs["agent_id"] == "antigravity"
