-- R118/R107: the two fields added to `Incident` on 4-5 October 2026.
--
-- The Postgres store shreds an incident into columns while DynamoDB keeps it
-- as one JSON document, so a field added to the model round-trips on the
-- deployed store and is silently dropped on the on-prem path. These are the
-- columns for `simulation_of` and `sources`; `testdb.py` now round-trips a
-- fully populated incident through every store so the next one fails loudly
-- instead of vanishing.

ALTER TABLE incident ADD COLUMN IF NOT EXISTS simulation_of TEXT;
ALTER TABLE incident ADD COLUMN IF NOT EXISTS sources JSONB NOT NULL DEFAULT '[]'::jsonb;
