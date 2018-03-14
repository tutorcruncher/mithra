CREATE OR REPLACE FUNCTION on_call() RETURNS trigger AS $$
  DECLARE
    payload JSON;
    person_id INT;
    person_name VARCHAR(255);
    company VARCHAR(255);
  BEGIN
   SELECT p.id, p.name, c.name INTO person_id, person_name, company
      FROM people_numbers AS pn
      JOIN people p ON pn.person = p.id
      JOIN companies c ON p.company = c.id
      WHERE pn.number ILIKE '%' || right(NEW.number, -4)
      ORDER BY p.last_seen DESC LIMIT 1;

    NEW.person := person_id;
    payload := json_build_object(
      'number', NEW.number,
      'country', NEW.country,
      'ts', NEW.ts,
      'person_id', person_id,
      'person_name', person_name,
      'company', company
    );
    -- notify no channel "call"
    PERFORM pg_notify('call', payload::text);
    RETURN NEW;
  END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS calls_insert on calls;
CREATE TRIGGER calls_insert BEFORE INSERT ON calls FOR EACH ROW EXECUTE PROCEDURE on_call();
