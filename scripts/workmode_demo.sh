#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TASK="tasks/examples/task-code-implement.json"
SESSION_DIR="runtime/sessions"
CONFIG="config/workmode.yaml"

echo "[1/8] Validate config"
python3 scripts/workmode_ctl.py validate-config --config "$CONFIG"

echo "[2/8] Reset runtime demo task"
mkdir -p runtime
cp "$TASK" runtime/task-workmode.json

echo "[3/8] Init strict session"
python3 scripts/workmode_ctl.py init-session --task runtime/task-workmode.json --config "$CONFIG" --mode strict --session-dir "$SESSION_DIR"

echo "[4/8] Next action for Windsurf (builder)"
python3 scripts/workmode_ctl.py next-action --task runtime/task-workmode.json --agent windsurf --session-dir "$SESSION_DIR"

echo "[5/8] Builder starts and finishes"
python3 scripts/workmode_ctl.py auto-progress --task runtime/task-workmode.json --event builder_start --actor windsurf --reason "builder started" --config "$CONFIG" --session-dir "$SESSION_DIR"
python3 scripts/workmode_ctl.py auto-progress --task runtime/task-workmode.json --event builder_done --actor windsurf --reason "builder finished" --config "$CONFIG" --session-dir "$SESSION_DIR"

echo "[6/8] Next action for Antigravity (reviewer)"
python3 scripts/workmode_ctl.py next-action --task runtime/task-workmode.json --agent antigravity --session-dir "$SESSION_DIR"

echo "[7/8] Review pass and close"
python3 scripts/workmode_ctl.py auto-progress --task runtime/task-workmode.json --event review_pass --actor antigravity --reason "checks passed" --config "$CONFIG" --session-dir "$SESSION_DIR"
python3 scripts/workmode_ctl.py auto-progress --task runtime/task-workmode.json --event merge_done --actor codex --reason "merged" --config "$CONFIG" --session-dir "$SESSION_DIR"
python3 scripts/workmode_ctl.py auto-progress --task runtime/task-workmode.json --event close_done --actor codex --reason "closed" --config "$CONFIG" --session-dir "$SESSION_DIR"

echo "[8/8] Final next action snapshots"
python3 scripts/workmode_ctl.py next-action --task runtime/task-workmode.json --agent codex --session-dir "$SESSION_DIR"
python3 scripts/workmode_ctl.py next-action --task runtime/task-workmode.json --agent windsurf --session-dir "$SESSION_DIR"
python3 scripts/workmode_ctl.py next-action --task runtime/task-workmode.json --agent antigravity --session-dir "$SESSION_DIR"
