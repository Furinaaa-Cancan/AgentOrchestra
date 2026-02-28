---
name: task-decompose
description: Decompose incoming requirements into dependency-aware tasks with done criteria, capability tags, and strict handoff artifacts. Use when work must be split for multi-agent execution and routing.
---

Parse the user requirement into a directed acyclic graph of executable tasks.

Generate task objects that conform to `/Volumes/Seagate/Multi-Agent/specs/task.schema.json`.

Emit strict outputs for each task:
- `task_id`
- `skill_id`
- `required_capabilities`
- `done_criteria`
- `expected_checks`
- `deps`

Reject vague tasks. Rewrite each task until a different agent can run it without extra clarification.

When dependencies are ambiguous, prefer explicit sequencing over parallelism.
