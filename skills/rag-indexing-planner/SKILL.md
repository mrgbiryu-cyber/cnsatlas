---
name: rag-indexing-planner
description: Use this skill when planning chunking, embedding, retrieval documents, metadata filters, or reindexing flows for CNS Atlas. This skill ensures every search artifact is derived from canonical-schema-guardian compliant entities and remains traceable to the source of truth.
---

# RAG Indexing Planner

Use this skill for search and retrieval design.

This skill is subordinate to `canonical-schema-guardian`.

## Required posture

- Indexes are derived from canonical records.
- Retrieval metadata must preserve canonical IDs, versions, and provenance.
- Chunking strategy must not invent unsupported business structure.

## Workflow

1. Select canonical source entities for indexing.
2. Define chunk boundaries and denormalized retrieval documents.
3. Attach stable canonical IDs and filter metadata.
4. Define reindex triggers from canonical change events.

## Rules

- Every chunk must map back to canonical entities.
- Embedding payloads may simplify text, but not redefine meaning.
- Reindexing must be driven by canonical version changes, not ad hoc manual guesses.

## Deliverables

- chunking model
- retrieval document schema
- metadata filter schema
- reindex trigger strategy
