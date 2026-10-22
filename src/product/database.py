import os
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    segment: Mapped[str]


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Run(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(default="running")
    accepted: Mapped[int] = mapped_column(default=0)
    rejected: Mapped[int] = mapped_column(default=0)
    error_type: Mapped[str | None]


class Event(Base):
    __tablename__ = "product_events"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    name: Mapped[str] = mapped_column(index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"))
    properties: Mapped[dict] = mapped_column(JSON, default=dict)


class Request(Base):
    __tablename__ = "api_requests"
    __table_args__ = (CheckConstraint("latency_ms >= 0 AND status >= 100 AND status <= 599"),)
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    endpoint: Mapped[str] = mapped_column(index=True)
    status: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float)
    release_id: Mapped[str] = mapped_column(ForeignKey("releases.id"))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"))


class ApiError(Base):
    __tablename__ = "api_errors"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("api_requests.id"), unique=True)
    error_type: Mapped[str]


class Release(Base):
    __tablename__ = "releases"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str]


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    endpoint: Mapped[str]
    description: Mapped[str]


class Rejection(Base):
    __tablename__ = "rejections"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"), index=True)
    table_name: Mapped[str]
    record_id: Mapped[str]
    reason: Mapped[str]
    raw: Mapped[dict] = mapped_column(JSON)


TABLES = {
    "users": User,
    "sessions": Session,
    "releases": Release,
    "incidents": Incident,
    "events": Event,
    "requests": Request,
    "errors": ApiError,
}


def engine(url: str | None = None):
    target = url or os.getenv("DATABASE_URL", "sqlite:///product.db")
    db = create_engine(target, poolclass=StaticPool if target == "sqlite://" else NullPool)
    if db.dialect.name == "sqlite":

        @event.listens_for(db, "connect")
        def fk(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return db


def sessions(url: str | None = None):
    return sessionmaker(engine(url), expire_on_commit=False)
