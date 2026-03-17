PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS atlas_documents (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  document_type TEXT NOT NULL,
  subtype TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL,
  primary_source_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS atlas_pages (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  page_type TEXT NOT NULL,
  subtype TEXT NOT NULL,
  title TEXT NOT NULL,
  order_index INTEGER NOT NULL,
  source_ref_id TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (document_id) REFERENCES atlas_documents(id)
);

CREATE TABLE IF NOT EXISTS atlas_nodes (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  page_id TEXT NOT NULL,
  parent_node_id TEXT,
  node_type TEXT NOT NULL,
  subtype TEXT NOT NULL,
  title TEXT NOT NULL,
  raw_text TEXT,
  normalized_text TEXT,
  semantic_summary TEXT,
  geometry_json TEXT,
  style_json TEXT,
  status TEXT NOT NULL,
  authoritative_source TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (document_id) REFERENCES atlas_documents(id),
  FOREIGN KEY (page_id) REFERENCES atlas_pages(id),
  FOREIGN KEY (parent_node_id) REFERENCES atlas_nodes(id)
);

CREATE TABLE IF NOT EXISTS atlas_assets (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  page_id TEXT NOT NULL,
  node_id TEXT,
  asset_type TEXT NOT NULL,
  storage_url TEXT,
  mime_type TEXT,
  width REAL,
  height REAL,
  checksum TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (document_id) REFERENCES atlas_documents(id),
  FOREIGN KEY (page_id) REFERENCES atlas_pages(id),
  FOREIGN KEY (node_id) REFERENCES atlas_nodes(id)
);

CREATE TABLE IF NOT EXISTS atlas_source_mappings (
  id TEXT PRIMARY KEY,
  internal_entity_type TEXT NOT NULL,
  internal_entity_id TEXT NOT NULL,
  source_type TEXT NOT NULL,
  external_container_id TEXT,
  external_ref_id TEXT,
  source_path TEXT,
  source_hash TEXT,
  source_version TEXT,
  is_primary INTEGER NOT NULL DEFAULT 1,
  raw_payload_json TEXT,
  fetched_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS atlas_knowledge_documents (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  knowledge_type TEXT NOT NULL,
  subtype TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT,
  normalized_text TEXT,
  status TEXT NOT NULL,
  source_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS atlas_annotations (
  id TEXT PRIMARY KEY,
  target_entity_type TEXT NOT NULL,
  target_entity_id TEXT NOT NULL,
  annotation_type TEXT NOT NULL,
  subtype TEXT NOT NULL,
  body TEXT NOT NULL,
  author_type TEXT,
  author_id TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS atlas_ownerships (
  id TEXT PRIMARY KEY,
  target_entity_type TEXT NOT NULL,
  target_entity_id TEXT NOT NULL,
  ownership_type TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  team_id TEXT,
  metadata_json TEXT,
  starts_at TEXT,
  ends_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS atlas_relations (
  id TEXT PRIMARY KEY,
  from_entity_type TEXT NOT NULL,
  from_entity_id TEXT NOT NULL,
  to_entity_type TEXT NOT NULL,
  to_entity_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  subtype TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS atlas_search_index (
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  page_id TEXT,
  searchable_text TEXT NOT NULL,
  metadata_json TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_atlas_pages_document_id ON atlas_pages(document_id);
CREATE INDEX IF NOT EXISTS idx_atlas_nodes_page_id ON atlas_nodes(page_id);
CREATE INDEX IF NOT EXISTS idx_atlas_nodes_parent_node_id ON atlas_nodes(parent_node_id);
CREATE INDEX IF NOT EXISTS idx_atlas_assets_page_id ON atlas_assets(page_id);
CREATE INDEX IF NOT EXISTS idx_atlas_source_mappings_entity ON atlas_source_mappings(internal_entity_type, internal_entity_id);
CREATE INDEX IF NOT EXISTS idx_atlas_search_index_document_page ON atlas_search_index(document_id, page_id);
