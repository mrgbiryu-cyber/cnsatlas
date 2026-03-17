---
name: ppt-figma-parser-architect
description: Use this skill when designing ingestion or parsing workflows from PowerPoint or Figma into CNS Atlas. This skill normalizes raw source structures into canonical-schema-guardian compliant entities and blocks source-specific models from leaking into the shared system contract.
---

# PPT Figma Parser Architect

Use this skill for PPT or Figma ingestion design.

This skill is subordinate to `canonical-schema-guardian`.

## Required posture

- Treat PPT and Figma as volatile source formats.
- Convert source-specific constructs into canonical entities as early as possible.
- Keep raw extraction, normalization, and canonical mapping as separate stages.

## Workflow

1. Extract raw source payloads without assigning long-term business semantics.
2. Normalize source quirks into a staging shape.
3. Map staging records into canonical entities.
4. Emit validation failures when canonical required fields cannot be resolved.

## Rules

- Parser output must include `source_type`, `source_ref`, `sync_mode`, and `authoritative_source`.
- Do not let slide-local, node-local, or tool-local naming become system field names unless promoted by the guardian.
- If PPT and Figma disagree, preserve both observations but resolve truth using canonical ownership rules.

## Deliverables

- source-to-canonical mapping table
- extraction stages
- validation rules
- lossiness report for unsupported source constructs
