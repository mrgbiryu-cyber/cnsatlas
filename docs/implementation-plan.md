# CNS Atlas Implementation Plan

## Principle

The project operates on one canonical schema.

`canonical-schema-guardian` is the top-level control skill.

All other skills are execution skills that must conform to the canonical contract.

## Skill order

1. `canonical-schema-guardian`
2. `metadata-db-designer`
3. `ppt-figma-parser-architect`
4. `figma-sync-designer`
5. `rag-indexing-planner`
6. `migration-orchestrator`

## Phase 1: Canonical contract

Owner skill: `canonical-schema-guardian`

Outputs:

- canonical entity inventory
- required fields and enums
- `source_type` policy
- `sync_mode` policy
- `authoritative_source` policy
- ID, version, and provenance rules

Exit criteria:

- every planned subsystem can point to one shared entity model
- no unresolved ownership ambiguity remains

## Phase 2: Persistence model

Owner skill: `metadata-db-designer`

Outputs:

- database schema draft
- constraints for provenance and ownership
- audit and versioning design
- canonical-to-storage mapping

Exit criteria:

- DB schema preserves canonical semantics directly
- derived or retrieval tables are separated from truth tables

## Phase 3: Ingestion model

Owner skill: `ppt-figma-parser-architect`

Outputs:

- PPT extraction stages
- Figma extraction stages
- staging-to-canonical mapping
- validation and rejection rules

Exit criteria:

- parser outputs are canonical or canonical-ready
- source-specific naming no longer leaks into shared contracts

## Phase 4: Sync model

Owner skill: `figma-sync-designer`

Outputs:

- entity sync matrix
- field ownership matrix
- conflict resolution rules
- retry and reconciliation policy

Exit criteria:

- sync behavior matches declared `authoritative_source`
- bidirectional flows are version-aware and idempotent

## Phase 5: Retrieval model

Owner skill: `rag-indexing-planner`

Outputs:

- chunking strategy
- retrieval document schema
- metadata filter design
- reindex trigger policy

Exit criteria:

- every indexed artifact maps to canonical IDs and versions
- retrieval structures are explicitly derived, not truth models

## Phase 6: Migration and cutover

Owner skill: `migration-orchestrator`

Outputs:

- legacy-to-canonical mapping
- data validation plan
- cutover checklist
- rollback checklist

Exit criteria:

- migrated data validates against canonical semantics
- rollback path is defined before production cutover

## Working rule

If any phase needs a new field, enum, ownership rule, or entity meaning, update `canonical-schema-guardian` first, then propagate the change downstream.
