---
name: figma-sync-designer
description: Use this skill when defining how Figma data syncs with CNS Atlas entities. This skill enforces canonical-schema-guardian ownership rules so Figma integration behaves as a projection and synchronization layer over canonical records rather than an independent source model.
---

# Figma Sync Designer

Use this skill to design Figma sync behavior.

This skill is subordinate to `canonical-schema-guardian`.

## Required posture

- Canonical entities control sync policy.
- Figma is a connected system, not a separate truth model by default.
- Field-level ownership must follow `authoritative_source` and `sync_mode`.

## Workflow

1. Identify which canonical entities are represented in Figma.
2. Define inbound, outbound, or bidirectional sync per entity family.
3. Define conflict handling based on `authoritative_source`.
4. Define event ordering, retries, idempotency, and version checks.

## Rules

- Never sync unnamed ad hoc payloads directly into DB tables.
- Every synced field must map to a canonical field or approved projection.
- Conflicts must be resolved through declared ownership, not arrival order alone.

## Deliverables

- sync matrix by entity and field
- conflict resolution policy
- version and idempotency strategy
- failure and reconciliation flow
