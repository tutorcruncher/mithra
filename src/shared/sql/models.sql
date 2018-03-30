DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
CREATE EXTENSION pg_trgm;

CREATE TABLE companies (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  ic_id VARCHAR(63) NOT NULL UNIQUE,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  login_url VARCHAR(255),
  has_support BOOLEAN DEFAULT FALSE,
  details JSONB
);
CREATE INDEX company_ic_id ON companies USING btree (ic_id);

CREATE TABLE people (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  ic_id VARCHAR(63) NOT NULL UNIQUE,
  last_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  search TEXT,
  details JSONB
);
CREATE INDEX people_last_seen ON people USING btree (last_seen);
CREATE INDEX search_index ON people USING GIN (search gin_trgm_ops);

CREATE TABLE people_numbers (
  person INT NOT NULL REFERENCES people ON DELETE CASCADE,
  number VARCHAR(127),
  UNIQUE (person, number)
);
CREATE INDEX number_index ON people_numbers USING GIN (number gin_trgm_ops);

CREATE TYPE BOUND AS ENUM ('inbound', 'outbound');
CREATE TABLE calls (
  id SERIAL PRIMARY KEY,
  call_id VARCHAR(127) NOT NULL,
  ext_number VARCHAR(127),
  int_number VARCHAR(127),
  bound BOUND NOT NULL,
  answered BOOLEAN DEFAULT FALSE,
  finished BOOLEAN DEFAULT FALSE,
  person INT REFERENCES people,
  country VARCHAR(31),
  ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  duration INTERVAL NOT NULL,
  details JSONB
);
CREATE INDEX call_id ON calls USING btree (call_id);
CREATE INDEX call_ts ON calls USING btree (ts);

CREATE TABLE call_events (
  id SERIAL PRIMARY KEY,
  call INT REFERENCES calls,
  ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  event VARCHAR(31) NOT NULL,
  details JSONB
);
