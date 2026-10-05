-- Counters for /impact (R107). Aggregates, never the audit ledger: R93's rule
-- is that reading a page must not append to an append-only record of
-- decisions, and neither of these has an actor, a verdict or anything to
-- approve. They are counts, and they are kept where counts belong.

CREATE TABLE IF NOT EXISTS page_view (
    day   DATE   NOT NULL,
    route TEXT   NOT NULL,
    views BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (day, route)
);

CREATE TABLE IF NOT EXISTS heartbeat (
    day   DATE   PRIMARY KEY,
    beats BIGINT NOT NULL DEFAULT 0
);
