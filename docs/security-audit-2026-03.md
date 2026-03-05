# Security & Performance Audit — 2026-03-05

## Summary

| Category | Status | Details |
|----------|--------|---------|
| Path traversal | **Fixed** | task_id, agent_id, skill_id all validated |
| Command injection | **Fixed** | shell=False with shlex.split() |
| SQL injection | **N/A** | No raw SQL; LangGraph uses parameterized queries |
| Concurrency | **OK** | Lock-based, connection-pooled, thread-safe |
| Resource leaks | **Low risk** | SQLite connections atexit-cleaned |
| State machine | **Fixed** | Terminal states block outgoing transitions |

## Findings & Actions

### 1. Path Traversal — agent_id (FIXED)

**Risk**: HIGH → **Resolved**

`agent_id` was used unsanitized in file paths (`inbox/{agent_id}.md`,
`outbox/{agent_id}.json`). A crafted `--builder ../../../etc` flag
could write files outside the workspace.

**Fix**: Added `validate_agent_id()` in `_utils.py` with regex
`^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$`. Applied to all 6 workspace
functions: `write_inbox`, `read_outbox`, `write_outbox`, `clear_outbox`,
`clear_inbox`, plus defense-in-depth in `trace.py` and `memory.py`.

### 2. Path Traversal — task_id (Already Protected)

**Risk**: LOW (was already mitigated)

`task_id` validated at CLI entry (`cli.py:_validate_task_id`), session
entry (`session.py:_validate_task_id`), and now also in `trace.py` and
`memory.py` (defense-in-depth). Graph snapshot saving uses regex
sanitization (`graph.py:save_state_snapshot`).

### 3. Command Injection — shell=False (FIXED)

**Risk**: MEDIUM → **Resolved**

`driver.py:spawn_cli_agent` now uses `shell=False` with `shlex.split()`,
completely eliminating shell injection risk. Previously used `shell=True`
with defense-in-depth mitigations.

**Fix**: Replaced `subprocess.Popen(cmd, shell=True, ...)` with
`subprocess.Popen(shlex.split(cmd_str), shell=False, ...)`. Paths are
passed as list elements, not shell-interpreted strings.

Remaining safeguard:
- `agents.yaml` file permissions should be `0o644` or stricter.

### 4. SQLite Resource Leaks (Low Risk)

**Risk**: LOW

Test warnings show `ResourceWarning: unclosed database`. This is because
`compile_graph()` creates pooled connections that are cleaned up via
`atexit.register(conn.close)` but not during test teardown.

`reset_graph()` properly closes all pooled connections and is called
in test fixtures. The warnings come from tests that don't call
`reset_graph()` in their teardown.

**No production impact** — connections are properly closed on process exit.

### 5. State Machine Terminal State Enforcement (FIXED)

**Risk**: LOW → **Resolved**

`validate_transition("DONE", "RUNNING")` previously returned `True`
because terminal states were not explicitly checked before the graceful
degradation fallback.

**Fix**: Added explicit terminal state check in `validate_transition()`
before the graceful degradation path. Terminal states (DONE, FAILED,
ESCALATED, CANCELLED) now block outgoing transitions. Self-transitions
(e.g., DONE→DONE) remain allowed for idempotency. Strict mode raises
`InvalidTransitionError` for terminal→X transitions.

### 6. Atomic File Writes (OK)

All JSON writes to outbox/inbox use atomic temp-file + `Path.replace()`
pattern with cleanup on failure. This prevents TOCTOU race conditions
with the file watcher.

### 7. Concurrency Safety (OK)

- Lock file mechanism prevents concurrent task execution
- `_cli_lock` mutex prevents duplicate CLI agent spawning
- `_conn_lock` protects SQLite connection pool
- Connection pool uses `check_same_thread=False` for multi-threaded access

### 8. Input Validation Coverage

| Input | Validated | Pattern |
|-------|-----------|---------|
| task_id | ✅ | `[a-z0-9][a-z0-9-]{2,63}` |
| agent_id | ✅ | `[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}` |
| skill_id | ✅ | `[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}` |
| file_path (CLI) | ✅ | `click.Path(exists=True)` |
| JSON payloads | ✅ | Pydantic + schema validation |
| command_template | ✅ | shell=False eliminates injection risk |

## Test Coverage

22 dedicated security tests in `tests/test_security.py` covering:
- task_id validation (traversal, special chars, boundary lengths)
- agent_id validation (traversal, shell metachars, boundaries)
- Workspace function rejection of malicious agent_ids

## Overall Project Quality (as of 2026-03-05)

| Metric | Value |
|--------|-------|
| Tests | **1040** |
| Coverage | **97%** (13 modules at 100%) |
| Ruff errors | **0** |
| Mypy strict errors | **0** |

### Performance Optimizations

- **SQLite WAL mode**: `PRAGMA journal_mode=WAL` enables concurrent readers during writes
- **Reduced fsync**: `PRAGMA synchronous=NORMAL` balances durability vs speed
- **Page cache**: `PRAGMA cache_size=-8000` (8 MB) for faster repeated queries
- **Graph compile cache**: Double-checked locking with fast-path (no lock on cache hit)
- **Connection pool**: Singleton per db_path with health verification (`SELECT 1`)
