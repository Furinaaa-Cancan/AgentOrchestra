---
name: test-and-review
description: Verify implementation artifacts with mandatory gates, regression checks, and decision output (approve/retry/escalate). Use when a task enters VERIFYING or needs independent review.
---

Validate that implementation output satisfies task done criteria and expected checks.

Re-run critical checks when artifacts are stale or inconsistent.

Emit a strict review decision:
- APPROVED
- RETRY
- ESCALATED

Always include rationale and failing evidence for non-approved decisions.
