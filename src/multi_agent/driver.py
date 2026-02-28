"""Agent drivers — spawn CLI agents or show file-based instructions."""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

from multi_agent.config import workspace_dir, outbox_dir


def get_agent_driver(agent_id: str) -> dict:
    """Look up driver config for an agent from agents.yaml."""
    from multi_agent.router import load_agents

    for agent in load_agents():
        if agent.id == agent_id:
            return {"driver": agent.driver, "command": agent.command}
    return {"driver": "file", "command": ""}


def spawn_cli_agent(
    agent_id: str,
    role: str,
    command_template: str,
    project_dir: str | None = None,
    timeout_sec: int = 600,
) -> threading.Thread:
    """Spawn a CLI agent in a background thread.

    The CLI agent reads TASK.md and writes its output to outbox/{role}.json.
    The watcher will detect the outbox file and resume the graph.

    Returns the thread (for testing). Caller does NOT need to join it.
    """
    task_file = str(workspace_dir() / "TASK.md")
    outbox_file = str(outbox_dir() / f"{role}.json")

    cmd = command_template.format(
        task_file=task_file,
        outbox_file=outbox_file,
    )

    def _run():
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=project_dir or str(Path.cwd()),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            # If the CLI tool didn't write the outbox file itself,
            # try to extract JSON from stdout and write it
            outbox_path = Path(outbox_file)
            if not outbox_path.exists() and result.stdout.strip():
                _try_extract_json(result.stdout, outbox_path)
        except subprocess.TimeoutExpired:
            # Write a timeout error to outbox so the graph can handle it
            _write_error(outbox_file, f"{agent_id} CLI timed out after {timeout_sec}s")
        except Exception as e:
            _write_error(outbox_file, f"{agent_id} CLI error: {e}")

    t = threading.Thread(target=_run, daemon=True, name=f"cli-{agent_id}-{role}")
    t.start()
    return t


def _try_extract_json(text: str, outbox_path: Path) -> None:
    """Try to find and extract a JSON object from CLI output text."""
    # Look for JSON between ```json ... ``` markers
    import re

    match = re.search(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                outbox_path.parent.mkdir(parents=True, exist_ok=True)
                with outbox_path.open("w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.write("\n")
                return
        except json.JSONDecodeError:
            pass

    # Try parsing the whole output as JSON
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict):
            outbox_path.parent.mkdir(parents=True, exist_ok=True)
            with outbox_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
    except json.JSONDecodeError:
        pass


def _write_error(outbox_file: str, error_msg: str) -> None:
    """Write an error marker to outbox so the graph can detect failure."""
    path = Path(outbox_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"status": "error", "summary": error_msg}, f, indent=2)
        f.write("\n")
