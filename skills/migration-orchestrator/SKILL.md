---
name: migration-orchestrator
description: Use this skill when migrating legacy data, intermediate files, existing schemas, or historical records into CNS Atlas. This skill sequences migration through canonical-schema-guardian compliant mappings so cutover, validation, and rollback are aligned with the shared system contract.
---

# Migration Orchestrator

Use this skill for migration and cutover planning.

This skill is subordinate to `canonical-schema-guardian`.

## Required posture

- Migrations land in canonical schema first.
- Legacy structures are temporary translation inputs, not long-term system models.
- Validation must prove semantic equivalence, not just row counts.

## Workflow

1. Inventory source schemas and data quality issues.
2. Build source-to-canonical mappings.
3. Define backfill, verification, and rollback procedures.
4. Cut over only after canonical validation passes.

## Rules

- Every migrated record must receive canonical provenance fields.
- Unknown legacy semantics must be flagged, not silently dropped.
- Migration success requires entity-level validation, not only transport success.

## Deliverables

- migration mapping matrix
- validation plan
- cutover checklist
- rollback and reconciliation plan
