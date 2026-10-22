"""Atomic bulk upserts with immutable run audits and record-level rejection evidence."""

import argparse
import json
import logging

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from product.database import TABLES, Rejection, Run, sessions, utcnow
from product.generation import generate
from product.validation import ORDER, validate_bundle

log = logging.getLogger(__name__)


def ingest(data: dict, url: str | None = None, replace: bool = False) -> int:
    factory = sessions(url)
    with factory.begin() as db:
        run = Run()
        db.add(run)
        db.flush()
        run_id = run.id
    try:
        clean, rejections = validate_bundle(data)
        accepted = sum(map(len, clean.values()))
        with factory.begin() as db:
            if replace:
                for table in reversed(ORDER):
                    db.execute(delete(TABLES[table]))
            for table in ORDER:
                model = TABLES[table]
                rows = clean[table]
                if table in {"events", "requests"}:
                    rows = [dict(**r, ingested_at=utcnow(), run_id=run_id) for r in rows]
                if rows:
                    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
                    stmt = insert(model)
                    update = {
                        c.name: stmt.excluded[c.name]
                        for c in model.__table__.columns
                        if c.name != "id"
                    }
                    # Executemany avoids oversized parameter lists on large synthetic batches.
                    db.execute(stmt.on_conflict_do_update(index_elements=["id"], set_=update), rows)
            db.add_all(Rejection(run_id=run_id, **r) for r in rejections)
            run = db.get(Run, run_id)
            run.accepted, run.rejected = accepted, len(rejections)
            run.status = "completed_with_rejections" if rejections else "completed"
            run.finished_at = utcnow()
        log.info(
            json.dumps(
                dict(
                    event="ingestion_completed",
                    run_id=run_id,
                    accepted=accepted,
                    rejected=len(rejections),
                )
            )
        )
    except Exception as exc:
        with factory.begin() as db:
            run = db.get(Run, run_id)
            run.status, run.error_type, run.finished_at = "failed", type(exc).__name__, utcnow()
        log.error(
            json.dumps(dict(event="ingestion_failed", run_id=run_id, error_type=type(exc).__name__))
        )
        raise
    return run_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Atomically replace scenario records; retain run/rejection audit",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(ingest(generate(args.seed), replace=args.replace))


if __name__ == "__main__":
    main()
