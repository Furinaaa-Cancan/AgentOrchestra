"""File watcher — monitors outbox/ for new agent outputs and auto-resumes the graph."""

from __future__ import annotations

import json
import time
from pathlib import Path

from multi_agent.config import outbox_dir


class OutboxPoller:
    """Simple polling-based watcher for outbox/ directory.

    Uses polling instead of OS-level watchers for maximum FS compatibility.
    Falls back gracefully — user can always use ``ma done`` manually.
    """

    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self._known: dict[str, float] = {}

    def _scan(self) -> dict[str, Path]:
        """Scan outbox/ for .json files, return {agent_id: path}."""
        d = outbox_dir()
        if not d.exists():
            return {}
        return {
            p.stem: p
            for p in d.glob("*.json")
        }

    def check_once(self) -> list[tuple[str, dict]]:
        """Check for new or updated outbox files. Returns [(agent_id, data), ...]."""
        results: list[tuple[str, dict]] = []
        for agent_id, path in self._scan().items():
            mtime = path.stat().st_mtime
            if agent_id not in self._known or self._known[agent_id] < mtime:
                self._known[agent_id] = mtime
                try:
                    with path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    results.append((agent_id, data))
                except (json.JSONDecodeError, OSError):
                    pass
        return results

    def watch(self, callback, *, stop_after: int | None = None):
        """Poll loop. Calls ``callback(agent_id, data)`` for each new outbox file.

        Args:
            callback: function(agent_id: str, data: dict) -> None
            stop_after: stop after N detections (None = run forever)
        """
        count = 0
        while True:
            for agent_id, data in self.check_once():
                callback(agent_id, data)
                count += 1
                if stop_after and count >= stop_after:
                    return
            time.sleep(self.poll_interval)
