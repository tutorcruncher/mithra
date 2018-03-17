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
DROP TRIGGER IF EXISTS before_calls_insert ON calls;
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
DROP TRIGGER IF EXISTS after_calls_insert ON calls;
CREATE TRIGGER after_calls_insert AFTER INSERT ON calls FOR EACH ROW EXECUTE PROCEDURE call_notify();


-- not a trigger as peole_numbers needs to have been updated before this is called
CREATE OR REPLACE FUNCTION update_search(person_id INT) RETURNS void AS $$
  DECLARE
    company_id INT;
    person_name VARCHAR(255);
    person_details JSONB;
    company_name VARCHAR(255);
    company_login_url VARCHAR(255);
    numbers TEXT;
  BEGIN
    SELECT name, details, company INTO person_name, person_details, company_id FROM people WHERE id=person_id;
    SELECT co.name, co.login_url INTO company_name, company_login_url FROM companies AS co WHERE co.id=company_id;
    SELECT array_to_string(array_agg(number), ' | ') INTO numbers FROM people_numbers WHERE person=person_id;

    UPDATE people SET search=concat_ws(' | ',
        person_name,
        COALESCE(numbers, ''),
        company_name,
        COALESCE(company_login_url, ''),
        COALESCE(person_details->>'city', ''),
        COALESCE(person_details->>'country', '')
    ) WHERE id=person_id;
  END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS update_search ON people;
