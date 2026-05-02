# Schema Agents

## Scope
`observations.sql` is the SQLite schema used by the kiosk runtime and tests.

## Local Rules
- Prefer additive schema changes over destructive rewrites.
- Keep indexes aligned with the UI access patterns: recent observations, per-node history, and class filters.
- Any schema change must be reflected in tests and in the installer path that initializes the database.