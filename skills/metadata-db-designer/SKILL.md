---
name: metadata-db-designer
description: Use this skill when designing relational tables, document models, ORM entities, constraints, or metadata storage for CNS Atlas. This skill ensures the persistence layer stores canonical-schema-guardian semantics directly and prevents DB-specific schema drift from becoming the de facto application model.
---

# Metadata DB Designer

Use this skill for storage design.

This skill is subordinate to `canonical-schema-guardian`.

## Required posture

- The database persists canonical semantics.
- Storage optimizations must not alter business meaning.
- Constraints should enforce the canonical contract where feasible.

## Workflow

1. Start from canonical entities and relationships.
2. Translate them into tables, documents, or ORM models.
3. Add keys, constraints, and audit columns that preserve provenance and ownership.
4. Define derived views separately from write models.

## Rules

- Store `source_type`, `sync_mode`, and `authoritative_source` as first-class fields.
- Do not hide canonical semantics in JSON blobs unless justified and documented.
- Keep index tables and retrieval tables clearly separate from truth tables.

## Deliverables

- schema proposal
- key and constraint plan
- canonical-to-storage mapping
- audit and versioning model
