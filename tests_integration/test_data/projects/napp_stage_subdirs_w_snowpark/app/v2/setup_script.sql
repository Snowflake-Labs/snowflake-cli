
CREATE APPLICATION ROLE IF NOT EXISTS app_public;

CREATE OR ALTER VERSIONED SCHEMA core;
GRANT USAGE ON SCHEMA core TO APPLICATION ROLE app_public;
