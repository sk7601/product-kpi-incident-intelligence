# Relational schema

| Table | Relationships and purpose |
|---|---|
| users | Stable synthetic ID, UTC registration, starter/enterprise segment |
| sessions | User FK, start/end bounds |
| product_events | Event ID, user/session FKs, name, occurrence/ingestion times, run FK, JSON properties |
| api_requests | Request ID, user/session/release FKs, status/latency CHECKs, endpoint, timestamps, run FK |
| api_errors | Error ID, unique request FK, category |
| releases | Version ID and UTC deployment |
| incidents | ID, start/end UTC interval, endpoint and synthetic label |
| ingestion_runs | Independent status, timestamps, accepted/rejected counts, safe error type |
| rejections | Run FK, record ID/table, reason, stringified raw fields |

Primary IDs enforce uniqueness. User/date/endpoint/event-name indexes serve analyst reads.
SQLite explicitly enables foreign keys. PostgreSQL tests exercise the same bulk upserts.
Alembic supports upgrade and destructive downgrade on disposable databases.

Validation follows reference dependency order. Unknown fields and required nulls are rejected;
missing/null properties become {}, lists are invalid. Dates require timezone, cannot be future,
must follow registration and fall inside their session. Features require login; activation also
requires dashboard. Funnel analytics additionally enforce strictly increasing timestamps.
Status and finite nonnegative latency are validated. Error rows reference failing requests.
Duplicate batch IDs are rejected; database upserts make reruns idempotent.

Run creation commits before the batch. Accepted records and rejection evidence load transactionally;
exceptions roll back data and independently mark the run failed. Replacement deletes children
before parents in that same transaction, retaining audit rows. Use one ingestion worker.
Occurrence time and actual UTC ingestion time are stored separately. Arbitrary event properties
and descriptions are untrusted and never sent to the model.
