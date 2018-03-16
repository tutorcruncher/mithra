CREATE OR REPLACE FUNCTION fill_call() RETURNS trigger AS $$
  DECLARE
    person_id INT;
  BEGIN
   SELECT p.id INTO person_id
      FROM people_numbers AS pn
      JOIN people p ON pn.person = p.id
      WHERE pn.number ILIKE '%' || right(NEW.number, -4)
      ORDER BY p.last_seen DESC LIMIT 1;

    NEW.person := person_id;
    RETURN NEW;
  END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS calls_insert on calls;
DROP TRIGGER IF EXISTS before_calls_insert on calls;
CREATE TRIGGER before_calls_insert BEFORE INSERT ON calls FOR EACH ROW EXECUTE PROCEDURE fill_call();

CREATE OR REPLACE FUNCTION call_notify() RETURNS trigger AS $$
  DECLARE
    payload JSON;
    person_name VARCHAR(255);
    company VARCHAR(255);
    has_support BOOLEAN;
  BEGIN
   SELECT p.name, co.name, co.has_support INTO person_name, company, has_support
      FROM calls
      JOIN people AS p ON calls.person = p.id
      JOIN companies AS co ON p.company = co.id
      WHERE calls.id=NEW.id;

    payload := json_build_object(
      'id', NEW.id,
      'number', NEW.number,
      'country', NEW.country,
      'ts', NEW.ts,
      'person_name', person_name,
      'company', company,
      'has_support', has_support
    );
    -- notify no channel "call"
    PERFORM pg_notify('call', payload::text);
    RETURN NEW;
  END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS after_calls_insert on calls;
CREATE TRIGGER after_calls_insert AFTER INSERT ON calls FOR EACH ROW EXECUTE PROCEDURE call_notify();
