# 11. Transform layer: dbt on Postgres

Status: Accepted — 2026-10-11. Amended by ADR 31 (Transform Runs).

## Decision
Layering: raw (JSONB Raw Responses) → staging → marts, modelled in dbt with the Postgres adapter. dbt runs as a Temporal activity after each match ingest. dbt tests (unique, not_null, relationships) provide baseline data quality.
