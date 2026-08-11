-- Initial schema: incidents, actions, policy verdicts, audit, topology.
--
-- Two properties are structural rather than conventional here:
--   1. Audit and incident transitions are append-only, enforced by triggers that
--      reject UPDATE and DELETE. An audit trail that can be retro-edited is not
--      an audit trail (SECURITY.md, T6).
--   2. Execution rows carry a NOT NULL verdict reference, so a row recording an
--      action that was never authorized cannot be written (Policy Model.md).

-- ---------------------------------------------------------------- topology --

CREATE TABLE topology_node (
    key              TEXT PRIMARY KEY,          -- "service:checkout-api"
    kind             TEXT NOT NULL,
    entity_id        TEXT NOT NULL,
    name             TEXT NOT NULL,
    cluster          TEXT,
    namespace        TEXT,
    owner            TEXT,
    estimated_users  INTEGER NOT NULL DEFAULT 0,
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE topology_edge (
    source_key  TEXT NOT NULL REFERENCES topology_node(key) ON DELETE CASCADE,
    target_key  TEXT NOT NULL REFERENCES topology_node(key) ON DELETE CASCADE,
    kind        TEXT NOT NULL DEFAULT 'depends_on',
    PRIMARY KEY (source_key, target_key, kind),
    CONSTRAINT no_self_dependency CHECK (source_key <> target_key)
);

-- Blast radius walks dependents: given a failed target, who breaks.
CREATE INDEX topology_edge_target_idx ON topology_edge (target_key);

-- ------------------------------------------------------------------ events --

CREATE TABLE event (
    id             TEXT PRIMARY KEY,            -- ULID, sortable by observation
    schema_version TEXT NOT NULL,
    event_class    TEXT NOT NULL,
    source         TEXT NOT NULL,
    source_version TEXT,
    occurred_at    TIMESTAMPTZ NOT NULL,
    observed_at    TIMESTAMPTZ NOT NULL,
    entity_key     TEXT NOT NULL,
    severity       TEXT,
    payload        JSONB NOT NULL,
    provenance     JSONB NOT NULL,              -- mandatory: how to re-retrieve
    labels         JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX event_entity_time_idx ON event (entity_key, occurred_at DESC);
CREATE INDEX event_class_time_idx  ON event (event_class, occurred_at DESC);

-- Entities that could not be resolved into the graph are held and made visible,
-- never silently dropped — they signal stale topology.
CREATE TABLE quarantined_event (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    raw         JSONB NOT NULL,
    source      TEXT NOT NULL,
    reason      TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --------------------------------------------------------------- incidents --

CREATE TABLE incident (
    id                       TEXT PRIMARY KEY,  -- INC-2026-0810
    state                    TEXT NOT NULL,
    severity                 TEXT NOT NULL,
    opened_at                TIMESTAMPTZ NOT NULL,
    closed_at                TIMESTAMPTZ,
    estimated_users_affected INTEGER NOT NULL DEFAULT 0,
    affected_services        TEXT[] NOT NULL DEFAULT '{}',
    blast_radius_entities    INTEGER NOT NULL DEFAULT 0,
    causal_chain             JSONB NOT NULL DEFAULT '[]'::jsonb,
    similar_incident_ids     TEXT[] NOT NULL DEFAULT '{}'
);

CREATE INDEX incident_state_idx ON incident (state, opened_at DESC);

CREATE TABLE incident_event (
    incident_id TEXT NOT NULL REFERENCES incident(id) ON DELETE CASCADE,
    event_id    TEXT NOT NULL,
    PRIMARY KEY (incident_id, event_id)
);

-- State is the fold of its transitions; incidents are never edited in place.
CREATE TABLE incident_transition (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id   TEXT NOT NULL REFERENCES incident(id) ON DELETE CASCADE,
    at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    from_state    TEXT,
    to_state      TEXT NOT NULL,
    actor         TEXT NOT NULL,
    justification TEXT NOT NULL
);

CREATE INDEX incident_transition_incident_idx ON incident_transition (incident_id, at);

CREATE TABLE hypothesis (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id     TEXT NOT NULL REFERENCES incident(id) ON DELETE CASCADE,
    statement       TEXT NOT NULL,
    confidence      DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    evidence        TEXT[] NOT NULL,
    contradicted_by TEXT[] NOT NULL DEFAULT '{}',
    mechanism       TEXT[] NOT NULL DEFAULT '{}',
    -- A hypothesis that cannot cite its telemetry is suppressed, not stored at
    -- low confidence (Grounding ADR). The validator is in core; this is the
    -- backstop for anything that bypasses it.
    CONSTRAINT hypothesis_requires_evidence CHECK (cardinality(evidence) > 0)
);

CREATE INDEX hypothesis_incident_idx ON hypothesis (incident_id, confidence DESC);

-- ------------------------------------------------------------ policy/action --

CREATE TABLE verdict (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    action_id        TEXT NOT NULL,
    incident_id      TEXT REFERENCES incident(id) ON DELETE SET NULL,
    base_risk        INTEGER NOT NULL CHECK (base_risk BETWEEN 0 AND 100),
    effective_risk   INTEGER NOT NULL CHECK (effective_risk BETWEEN 0 AND 100),
    adjustments      JSONB NOT NULL DEFAULT '[]'::jsonb,
    tier             TEXT NOT NULL,
    required_approvers TEXT[] NOT NULL DEFAULT '{}',
    granted_by       TEXT,
    granted_at       TIMESTAMPTZ,
    expires_at       TIMESTAMPTZ,
    constraints      JSONB NOT NULL DEFAULT '{}'::jsonb,
    denial_reason    TEXT,
    evaluated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Adjustments only ever raise risk (Policy Model.md).
    CONSTRAINT effective_risk_not_below_base CHECK (effective_risk >= base_risk)
);

CREATE INDEX verdict_incident_idx ON verdict (incident_id, evaluated_at DESC);
CREATE INDEX verdict_tier_idx ON verdict (tier, evaluated_at DESC);

CREATE TABLE plan_step (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id         TEXT NOT NULL REFERENCES incident(id) ON DELETE CASCADE,
    step_order          INTEGER NOT NULL,
    action_id           TEXT NOT NULL,
    expected_post_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    rollback_action_id  TEXT,
    verdict_id          BIGINT REFERENCES verdict(id),
    UNIQUE (incident_id, step_order)
);

CREATE TABLE execution (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id  TEXT REFERENCES incident(id) ON DELETE SET NULL,
    action_id    TEXT NOT NULL,
    -- NOT NULL: an execution row without an authorizing verdict is unwritable.
    verdict_id   BIGINT NOT NULL REFERENCES verdict(id),
    actor        TEXT NOT NULL,
    dry_run      BOOLEAN NOT NULL,
    started_at   TIMESTAMPTZ NOT NULL,
    finished_at  TIMESTAMPTZ,
    succeeded    BOOLEAN,
    output       TEXT
);

CREATE INDEX execution_incident_idx ON execution (incident_id, started_at DESC);

CREATE TABLE verification (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id     TEXT REFERENCES incident(id) ON DELETE CASCADE,
    execution_id    BIGINT REFERENCES execution(id),
    window_seconds  INTEGER NOT NULL,
    checks          JSONB NOT NULL DEFAULT '[]'::jsonb,
    passed          BOOLEAN,
    completed_at    TIMESTAMPTZ
);

-- ------------------------------------------------------------------- audit --

CREATE TABLE audit_record (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind        TEXT NOT NULL,
    actor       TEXT NOT NULL,
    incident_id TEXT,
    summary     TEXT NOT NULL,
    detail      JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX audit_incident_idx ON audit_record (incident_id, at DESC);
CREATE INDEX audit_kind_idx ON audit_record (kind, at DESC);

-- ------------------------------------------------- append-only enforcement --

CREATE FUNCTION reject_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is append-only: % is not permitted', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_record_append_only
    BEFORE UPDATE OR DELETE ON audit_record
    FOR EACH ROW EXECUTE FUNCTION reject_mutation();

CREATE TRIGGER incident_transition_append_only
    BEFORE UPDATE OR DELETE ON incident_transition
    FOR EACH ROW EXECUTE FUNCTION reject_mutation();

CREATE TRIGGER execution_append_only
    BEFORE DELETE ON execution
    FOR EACH ROW EXECUTE FUNCTION reject_mutation();
