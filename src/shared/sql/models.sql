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
CREATE INDEX number_index ON people_numbers USING btree (number);

CREATE TABLE calls (
  id SERIAL PRIMARY KEY,
  number VARCHAR(127) NOT NULL,
  person INT REFERENCES people,
  country VARCHAR(31),
  ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX call_ts ON calls USING btree (ts);
