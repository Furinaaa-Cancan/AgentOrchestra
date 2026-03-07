#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY_BIN="python3"
if [ -x ".venv/bin/python" ]; then
  PY_BIN=".venv/bin/python"
fi

SMOKE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/mygo-smoke.XXXXXX")"
cleanup() {
  rm -rf "$SMOKE_ROOT"
}
trap cleanup EXIT

cp -R skills "$SMOKE_ROOT/skills"
cp -R agents "$SMOKE_ROOT/agents"
cp -R config "$SMOKE_ROOT/config"
mkdir -p "$SMOKE_ROOT/runtime" "$SMOKE_ROOT/prompts"
cp tasks/examples/task-code-implement.json "$SMOKE_ROOT/runtime/task-session-smoke.json"

echo "[1/6] Validate skills"
python3 scripts/mvp_ctl.py validate-skill --skill-dir skills/task-decompose
python3 scripts/mvp_ctl.py validate-skill --skill-dir skills/code-implement
python3 scripts/mvp_ctl.py validate-skill --skill-dir skills/test-and-review

echo "[2/6] Validate task"
python3 scripts/mvp_ctl.py validate-task --task tasks/examples/task-code-implement.json

echo "[3/6] Route task"
python3 scripts/mvp_ctl.py route --task tasks/examples/task-code-implement.json --agents agents/profiles.json

echo "[4/6] Verify checks (pass case)"
python3 scripts/mvp_ctl.py verify-checks --task tasks/examples/task-code-implement.json --results tasks/examples/check-results-pass.json

echo "[5/6] Validate lock lifecycle"
python3 scripts/lockctl.py acquire --task-id task-api-user-create --file-path scripts/mvp_ctl.py --ttl-sec 30
python3 scripts/lockctl.py list
python3 scripts/lockctl.py renew --task-id task-api-user-create --file-path scripts/mvp_ctl.py --ttl-sec 30
python3 scripts/lockctl.py release --task-id task-api-user-create --file-path scripts/mvp_ctl.py

echo "[6/6] Session-mode smoke (LangGraph SSOT, isolated MA_ROOT)"
MA_ROOT="$SMOKE_ROOT" PYTHONPATH=src "$PY_BIN" -m multi_agent.cli session start \
  --task "$SMOKE_ROOT/runtime/task-session-smoke.json" \
  --mode strict \
  --config "$SMOKE_ROOT/config/workmode.yaml" \
  --reset >/dev/null

cat > "$SMOKE_ROOT/runtime/session-builder.json" <<'JSON'
{
  "protocol_version": "1.0",
  "task_id": "task-api-user-create",
  "lane_id": "main",
  "agent": "windsurf",
  "role": "builder",
  "state_seen": "RUNNING",
  "result": {
    "status": "completed",
    "summary": "smoke builder",
    "changed_files": ["artifacts/task-api-user-create/app/main.py"],
    "check_results": {
      "lint": "pass",
      "unit_test": "pass",
      "contract_test": "pass",
      "artifact_checksum": "pass"
    }
  },
  "recommended_event": "builder_done",
  "evidence_files": [],
  "created_at": "2026-03-02T00:00:00Z"
}
JSON
MA_ROOT="$SMOKE_ROOT" PYTHONPATH=src "$PY_BIN" -m multi_agent.cli session push \
  --task-id task-api-user-create \
  --agent windsurf \
  --file "$SMOKE_ROOT/runtime/session-builder.json" >/dev/null

cat > "$SMOKE_ROOT/runtime/session-reviewer.json" <<'JSON'
{
  "protocol_version": "1.0",
  "task_id": "task-api-user-create",
  "lane_id": "main",
  "agent": "antigravity",
  "role": "reviewer",
  "state_seen": "VERIFYING",
  "result": {
    "decision": "approve",
    "summary": "Reviewed implementation scope, changed files, and checks; acceptance criteria are satisfied.",
    "reasoning": "Cross-checked builder summary with expected endpoint behavior and required validation paths.",
    "evidence": [
      "Validated builder check_results and endpoint contract expectations."
    ]
  },
  "recommended_event": "review_pass",
  "evidence_files": [],
  "created_at": "2026-03-02T00:00:00Z"
}
JSON
MA_ROOT="$SMOKE_ROOT" PYTHONPATH=src "$PY_BIN" -m multi_agent.cli session push \
  --task-id task-api-user-create \
  --agent antigravity \
  --file "$SMOKE_ROOT/runtime/session-reviewer.json" >/dev/null
MA_ROOT="$SMOKE_ROOT" PYTHONPATH=src "$PY_BIN" -m multi_agent.cli session status \
  --task-id task-api-user-create | rg '"state": "DONE"' >/dev/null

echo "[6/6] Smoke test completed"
