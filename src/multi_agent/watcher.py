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
        """Scan outbox/ for .json files, return {role: path}.

        Role-based: detects builder.json and reviewer.json.
        """
        d = outbox_dir()
        if not d.exists():
            return {}
        return {
            p.stem: p
            for p in d.glob("*.json")
        }

    def check_once(self) -> list[tuple[str, dict]]:
        """Check for new or updated outbox files. Returns [(role, data), ...]."""
        results: list[tuple[str, dict]] = []
        for role, path in self._scan().items():
            mtime = path.stat().st_mtime
            if role not in self._known or self._known[role] < mtime:
                self._known[role] = mtime
                try:
                    with path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    results.append((role, data))
                except (json.JSONDecodeError, OSError):
                    pass
        return results

    def watch(self, callback, *, stop_after: int | None = None):
        """Poll loop. Calls ``callback(role, data)`` for each new outbox file.

        Args:
            callback: function(role: str, data: dict) -> None
            stop_after: stop after N detections (None = run forever)
        """
        count = 0
        while True:
            for role, data in self.check_once():
                callback(role, data)
                count += 1
                if stop_after and count >= stop_after:
                    return
            time.sleep(self.poll_interval)
