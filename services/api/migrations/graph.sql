-- Blast radius as a recursive CTE.
--
-- The Graph ADR defers the store decision to Phase 1 measurements, with Postgres
-- as the working default. This function is that default made testable: it must
-- reproduce, exactly, the semantics of `TopologyGraph.blast_radius` in
-- packages/core — which is the reference implementation, not merely a mock.
--
-- Traversal follows dependents: given a failed target, who breaks because of it.

CREATE FUNCTION blast_radius(origin TEXT, max_depth INTEGER DEFAULT 10)
RETURNS TABLE (affected_key TEXT, depth INTEGER)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE walk(key, depth) AS (
        SELECT origin, 0
      UNION
        SELECT e.source_key, w.depth + 1
        FROM walk w
        JOIN topology_edge e ON e.target_key = w.key
        WHERE w.depth < max_depth
    )
    -- The origin itself is excluded: blast radius is what *else* is affected.
    -- A cycle re-reaching the origin must not add it either, which UNION's
    -- deduplication combined with this filter guarantees.
    SELECT key, MIN(depth)::INTEGER
    FROM walk
    WHERE key <> origin
    GROUP BY key
    ORDER BY key;
$$;

-- Estimated users behind a failure, summed over affected nodes only.
CREATE FUNCTION blast_radius_users(origin TEXT, max_depth INTEGER DEFAULT 10)
RETURNS BIGINT
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(SUM(n.estimated_users), 0)::BIGINT
    FROM blast_radius(origin, max_depth) b
    JOIN topology_node n ON n.key = b.affected_key;
$$;
