DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

CREATE TABLE companies (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  login_url VARCHAR(255),
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  details JSONB
);

CREATE TABLE people (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  last_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  details JSONB
);
CREATE INDEX people_last_seen ON people USING btree (last_seen);

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
