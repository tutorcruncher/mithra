DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

CREATE TABLE calls (
  id SERIAL PRIMARY KEY,
  number VARCHAR(63) NOT NULL,
  country VARCHAR(31) NOT NULL,
  ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- replaced by direct notify as more data can be included
-- CREATE OR REPLACE FUNCTION notify_on_call() RETURNS trigger AS $$
--   DECLARE
--     payload_ JSON = json_build_object(
--       'number', NEW.number,
--       'country', NEW.country,
--       'ts', NEW.ts
--     );
--   BEGIN
--     -- notify no channel "call"
--     PERFORM pg_notify('call', payload_::text);
--     RETURN NULL;
--   END;
-- $$ LANGUAGE plpgsql;
-- CREATE TRIGGER calls_insert AFTER INSERT ON calls FOR EACH ROW EXECUTE PROCEDURE notify_on_call();
