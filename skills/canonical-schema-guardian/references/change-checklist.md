# Canonical Change Checklist

Use this checklist whenever a new field, entity, sync rule, or retrieval shape is proposed.

## Schema checks

- Is this a new canonical concept or only a source-specific parsing detail?
- If it is canonical, has it been added to the guardian before downstream design?
- Does the field name preserve the same meaning across DB, API, sync, and indexing?

## Provenance checks

- Is `source_type` explicit?
- Is `authoritative_source` explicit?
- Is `source_ref` sufficient to trace the original record?

## Sync checks

- Is `sync_mode` explicitly declared?
- Is ownership resolution defined for conflicts?
- Is version-based replay or idempotency required?

## Retrieval checks

- Can the retrieval artifact be traced to canonical IDs and versions?
- Is any business meaning stored only in the index?

## Migration checks

- Can legacy values map into the canonical enum set?
- Are unknown states flagged instead of silently coerced?

## Approval rule

If any answer is unclear, update the canonical contract before implementing downstream changes.
