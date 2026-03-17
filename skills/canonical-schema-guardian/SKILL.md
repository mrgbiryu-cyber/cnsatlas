---
name: canonical-schema-guardian
description: Use this skill when defining or changing any schema, data contract, parser output, sync payload, database model, API model, search document, or migration mapping for CNS Atlas. This skill is the canonical source of truth for entity structure, source provenance, sync policy, and authoritative ownership rules across DB, API, indexing, and sync workflows.
---

# Canonical Schema Guardian

This skill is the top-level contract for the project.

Apply it before changing:

- entity definitions
- parser outputs from PPT or Figma
- database tables or ORM models
- API request or response models
- RAG indexing documents
- sync payloads
- migration mappings

Read these references when drafting or updating the canonical contract:

- `references/entity-catalog.md` for the draft entity inventory and enum values
- `references/change-checklist.md` for schema review and downstream propagation checks

## Core mandate

All business objects must resolve to one canonical schema.

The following fields are mandatory in the canonical layer for every entity or record family:

- `id`
- `entity_type`
- `source_type`
- `sync_mode`
- `authoritative_source`
- `source_ref`
- `version`
- `created_at`
- `updated_at`

If a downstream system needs a different shape, it must be a projection of the canonical model, not a competing truth model.

## Required invariants

### 1. Single truth model

- DB, API, indexing, sync, and ingestion must reference the same entity semantics.
- New fields must be introduced in the canonical schema first.
- No subsystem may invent a field that changes meaning from the canonical definition.

### 2. Provenance is explicit

Every entity must carry source provenance:

- `source_type`: where the data came from
- `source_ref`: stable pointer to the external or internal origin
- `authoritative_source`: which system currently owns the truth

Never infer ownership from storage location alone.

### 3. Sync policy is explicit

Every sync-capable entity must declare:

- `sync_mode=one_way_inbound`
- `sync_mode=one_way_outbound`
- `sync_mode=bidirectional`
- `sync_mode=manual`
- `sync_mode=none`

Do not leave sync direction implicit in code or job configuration.

### 4. Authoritative ownership is explicit

Every canonical entity must declare exactly one current `authoritative_source`.

Recommended allowed values:

- `ppt`
- `figma`
- `db`
- `curation`
- `migration`
- `system`

If ownership changes over time, record the change through versioning or audit history. Do not overwrite ownership semantics silently.

### 5. Indexes are derived artifacts

- Search chunks, embeddings, denormalized documents, and retrieval payloads are derived outputs.
- They must trace back to canonical entity IDs and versions.
- They must never become the only place where business meaning exists.

## Canonical field guidance

Use this baseline structure unless the project establishes a stricter typed schema:

```yaml
id: string
entity_type: string
title: string|null
description: string|null
source_type: enum
source_ref:
  external_id: string|null
  external_uri: string|null
  revision_id: string|null
sync_mode: enum
authoritative_source: enum
status: string|null
tags: string[]
version: integer
created_at: datetime
updated_at: datetime
metadata: object
```

Downstream systems may drop fields for read optimization, but they may not rename or reinterpret canonical fields without an explicit mapping layer.

The current draft entity set and enum recommendations live in `references/entity-catalog.md`.

## Change control workflow

When a request touches schema or contracts:

1. Identify the canonical entity affected.
2. Check whether the requested field already exists semantically.
3. If not, add or revise the canonical definition first.
4. Validate implications for DB, API, indexing, sync, and migration.
5. Only then update downstream projections.

Reject changes that:

- add parser-only fields without canonical meaning
- let DB columns and API fields drift semantically
- encode sync ownership in job names or comments only
- let RAG chunks carry information not recoverable from canonical entities

## Review checklist

Before approving a design or implementation, verify:

- Is there exactly one canonical definition for this concept?
- Are `source_type`, `sync_mode`, and `authoritative_source` present and valid?
- Can every derived document map back to canonical IDs and versions?
- Does the DB schema preserve canonical semantics?
- Does the API expose canonical meaning rather than transport-specific shortcuts?
- Does sync behavior match the declared ownership model?

## Interaction with other skills

- `ppt-figma-parser-architect` must output canonical entities or canonical-ready staging records.
- `figma-sync-designer` must treat canonical records as the control plane.
- `metadata-db-designer` must store canonical semantics without reinterpretation.
- `rag-indexing-planner` must derive retrievable documents from canonical records.
- `migration-orchestrator` must migrate old formats into canonical entities before cutover.

If another skill appears to require a conflicting schema, stop and revise the canonical contract first.
