-- OVERSEER schema migration 001
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entity_types (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS works (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    medium TEXT NOT NULL CHECK (medium IN ('game','dlc','television','official_web','other')),
    release_year INTEGER
);

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    entity_type_id INTEGER NOT NULL REFERENCES entity_types(id),
    summary TEXT NOT NULL DEFAULT '',
    status TEXT,
    era TEXT,
    canon_status TEXT NOT NULL DEFAULT 'unknown' CHECK (canon_status IN (
        'canonical','noncanonical','promotional','cut_content',
        'developer_commentary','gameplay_mechanic','disputed','unknown'
    )),
    confidence TEXT NOT NULL DEFAULT 'medium' CHECK (confidence IN ('high','medium','low')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias TEXT NOT NULL COLLATE NOCASE,
    UNIQUE(entity_id, alias)
);

CREATE TABLE IF NOT EXISTS appearances (
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    work_id INTEGER NOT NULL REFERENCES works(id),
    appearance_type TEXT NOT NULL DEFAULT 'appears',
    PRIMARY KEY (entity_id, work_id)
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    adapter TEXT NOT NULL,
    source_key TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    license_name TEXT,
    license_url TEXT,
    medium TEXT NOT NULL DEFAULT 'community_reference',
    UNIQUE(adapter, source_key)
);

CREATE TABLE IF NOT EXISTS source_revisions (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    page_id INTEGER,
    revision_id INTEGER,
    revision_timestamp TEXT,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT,
    raw_metadata_json TEXT NOT NULL,
    UNIQUE(source_id, revision_id)
);

CREATE TABLE IF NOT EXISTS entity_sources (
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    source_revision_id INTEGER NOT NULL REFERENCES source_revisions(id),
    role TEXT NOT NULL DEFAULT 'reference',
    PRIMARY KEY(entity_id, source_revision_id, role)
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    predicate TEXT NOT NULL,
    object_text TEXT NOT NULL,
    object_entity_id INTEGER REFERENCES entities(id),
    source_revision_id INTEGER NOT NULL REFERENCES source_revisions(id),
    canon_status TEXT NOT NULL DEFAULT 'unknown',
    confidence TEXT NOT NULL DEFAULT 'medium',
    notes TEXT,
    UNIQUE(entity_id, predicate, object_text, source_revision_id)
);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY,
    subject_entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    predicate TEXT NOT NULL,
    object_entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    source_revision_id INTEGER NOT NULL REFERENCES source_revisions(id),
    canon_status TEXT NOT NULL DEFAULT 'unknown',
    confidence TEXT NOT NULL DEFAULT 'medium',
    notes TEXT,
    CHECK(subject_entity_id <> object_entity_id),
    UNIQUE(subject_entity_id, predicate, object_entity_id, source_revision_id)
);

CREATE TABLE IF NOT EXISTS timeline_events (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    year_start INTEGER,
    year_end INTEGER,
    date_text TEXT,
    sort_key TEXT,
    source_revision_id INTEGER NOT NULL REFERENCES source_revisions(id),
    canon_status TEXT NOT NULL DEFAULT 'unknown',
    confidence TEXT NOT NULL DEFAULT 'medium',
    UNIQUE(entity_id, label, year_start, source_revision_id)
);

CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS entity_tags (
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY(entity_id, tag_id)
);

CREATE TABLE IF NOT EXISTS dossiers (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL UNIQUE REFERENCES entities(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    generator_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dossier_claims (
    dossier_id INTEGER NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    PRIMARY KEY(dossier_id, claim_id)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id INTEGER PRIMARY KEY,
    adapter TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('running','complete','failed','blocked')),
    checkpoint TEXT,
    records_seen INTEGER NOT NULL DEFAULT 0,
    records_written INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS review_flags (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    claim_id INTEGER REFERENCES claims(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    detail TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','wont_fix')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS entity_fts USING fts5(
    name,
    aliases,
    summary,
    tokenize='unicode61 remove_diacritics 2'
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type_id);
CREATE INDEX IF NOT EXISTS idx_alias_lookup ON entity_aliases(alias COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_claims_entity ON claims(entity_id);
CREATE INDEX IF NOT EXISTS idx_claims_source ON claims(source_revision_id);
CREATE INDEX IF NOT EXISTS idx_relationship_subject ON relationships(subject_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationship_object ON relationships(object_entity_id);
CREATE INDEX IF NOT EXISTS idx_timeline_year ON timeline_events(year_start, year_end);
CREATE INDEX IF NOT EXISTS idx_source_revisions_page ON source_revisions(page_id, revision_id);
CREATE INDEX IF NOT EXISTS idx_entity_sources_entity ON entity_sources(entity_id);
