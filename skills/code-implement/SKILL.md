---
name: code-implement
description: Implement scoped code changes under a strict task contract with file locks, reproducible checks, and auditable artifacts. Use when an assigned task requires deterministic implementation.
---

Acquire file locks before editing shared files.

Implement only the scoped change in the assigned task. Do not expand scope.

Run required quality checks from `expected_checks` and capture results as machine-readable output.

Produce a handoff artifact containing:
- summary
- changed_files
- check_results
- risk

Release file locks after checks complete or task fails.
