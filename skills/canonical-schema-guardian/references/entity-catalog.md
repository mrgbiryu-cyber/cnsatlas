# Draft Entity Catalog

This file is a working draft derived from the current project scope:

- all inputs must converge to one canonical schema
- `source_type`, `sync_mode`, and `authoritative_source` must be explicit
- DB, API, indexing, and sync must operate on the same shared model

The entities below are the minimum viable canonical set for that scope.

## 1. `source_asset`

Represents an imported source container such as a PowerPoint file or Figma file.

Purpose:

- track where data entered the system
- preserve provenance and revision history
- anchor parser runs and migration lineage

Required fields:

```yaml
id: string
entity_type: source_asset
source_type: enum
authoritative_source: enum
sync_mode: enum
source_ref:
  external_id: string|null
  external_uri: string|null
  revision_id: string|null
name: string
status: enum
version: integer
created_at: datetime
updated_at: datetime
metadata: object
```

Recommended status values:

- `discovered`
- `ingested`
- `parsed`
- `failed`
- `archived`

## 2. `source_fragment`

Represents a source-local component extracted from a source asset.

Examples:

- a PPT slide
- a PPT shape or note block
- a Figma page
- a Figma frame or component

Purpose:

- preserve source-native structure without turning it into the truth model
- make parser staging and traceability explicit

Required fields:

```yaml
id: string
entity_type: source_fragment
source_asset_id: string
fragment_type: string
source_type: enum
authoritative_source: enum
sync_mode: enum
source_ref: object
parent_fragment_id: string|null
title: string|null
content_text: string|null
status: enum
version: integer
created_at: datetime
updated_at: datetime
metadata: object
```

## 3. `atlas_entity`

Represents the main canonical business object produced by normalization.

This is the shared entity family consumed by DB, API, sync, and indexing.

Purpose:

- provide one project-wide semantic record
- abstract away PPT and Figma implementation details
- serve as the basis for downstream projections

Required fields:

```yaml
id: string
entity_type: atlas_entity
canonical_type: enum
title: string|null
description: string|null
source_type: enum
authoritative_source: enum
sync_mode: enum
source_ref: object
status: enum
version: integer
created_at: datetime
updated_at: datetime
metadata: object
```

Recommended `canonical_type` starter values:

- `document`
- `section`
- `node`
- `component`
- `annotation`
- `asset`

These are placeholders and should be replaced by domain-specific types once the product model is clearer.

## 4. `entity_relation`

Represents typed links between canonical entities.

Purpose:

- allow hierarchy and graph structure without embedding all relationships in ad hoc JSON
- support indexing and sync traversal from the same model

Required fields:

```yaml
id: string
entity_type: entity_relation
from_entity_id: string
to_entity_id: string
relation_type: enum
source_type: enum
authoritative_source: enum
sync_mode: enum
source_ref: object
version: integer
created_at: datetime
updated_at: datetime
metadata: object
```

Recommended `relation_type` starter values:

- `contains`
- `references`
- `derived_from`
- `mirrors`
- `annotates`

## 5. `sync_binding`

Represents mapping state between a canonical entity and an external system object.

Purpose:

- separate sync mechanics from canonical business meaning
- support idempotency, retries, and conflict checks

Required fields:

```yaml
id: string
entity_type: sync_binding
canonical_entity_id: string
target_system: enum
target_object_id: string
source_type: enum
authoritative_source: enum
sync_mode: enum
binding_status: enum
last_synced_version: integer|null
created_at: datetime
updated_at: datetime
metadata: object
```

Recommended `binding_status` values:

- `pending`
- `active`
- `conflict`
- `stale`
- `disabled`

## 6. `index_document`

Represents a derived retrieval document for search and embedding.

This is a derived entity, not a truth entity.

Purpose:

- support retrieval and filtering
- preserve traceability to canonical entities and versions

Required fields:

```yaml
id: string
entity_type: index_document
canonical_entity_id: string
chunk_key: string
source_type: enum
authoritative_source: enum
sync_mode: enum
source_ref: object
text: string
filter_metadata: object
canonical_version: integer
created_at: datetime
updated_at: datetime
metadata: object
```

## Recommended shared enums

### `source_type`

- `ppt`
- `figma`
- `db`
- `api`
- `migration`
- `manual`
- `system`

### `sync_mode`

- `one_way_inbound`
- `one_way_outbound`
- `bidirectional`
- `manual`
- `none`

### `authoritative_source`

- `ppt`
- `figma`
- `db`
- `curation`
- `migration`
- `system`

## ID and provenance rules

- Every canonical record ID must be system-generated and stable.
- External IDs belong in `source_ref`, not as the canonical primary key.
- Every derived artifact must reference the canonical entity ID and canonical version it came from.
- Source-local hierarchy may exist in `source_fragment`, but cross-system truth belongs in `atlas_entity` and `entity_relation`.

## Draft interpretation notes

Because the detailed product domain has not been specified yet, this catalog intentionally defines platform-level entities first.

Once the product domain is clearer, replace or refine:

- `atlas_entity.canonical_type`
- `source_fragment.fragment_type`
- `entity_relation.relation_type`

Do not remove provenance, ownership, or version fields when doing that refinement.
