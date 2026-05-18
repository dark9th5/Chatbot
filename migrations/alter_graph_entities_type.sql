-- Migration: widen graph_entities.type to allow full NER types
-- Run this on your MySQL server if `graph_entities.type` is an ENUM with limited values.

ALTER TABLE graph_entities
  MODIFY COLUMN `type` VARCHAR(50) NOT NULL;

-- Optional: if you want a normalized set of allowed types, create a foreign table
-- or a CHECK constraint in newer MySQL versions.
