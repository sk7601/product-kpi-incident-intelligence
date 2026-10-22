"""SQL-backed read models; filters use bound parameters and predeclared functions."""

import pandas as pd
from sqlalchemy import case, func, select

from product.analytics import utc
from product.database import (
    ApiError,
    Event,
    Incident,
    Rejection,
    Release,
    Request,
    Run,
    Session,
    User,
    engine,
)


def load(end: str, segment: str = "all") -> dict[str, pd.DataFrame]:
    cutoff = utc(end).to_pydatetime()
    db = engine()

    def segment_filter(query):
        return query if segment == "all" else query.where(User.segment == segment)

    with db.connect() as conn:
        users = pd.read_sql(segment_filter(select(User).where(User.registered_at < cutoff)), conn)
        events = pd.read_sql(
            segment_filter(
                select(Event).join(User, Event.user_id == User.id).where(Event.occurred_at < cutoff)
            ),
            conn,
        )
        requests = pd.read_sql(
            segment_filter(
                select(Request, User.segment)
                .join(User, Request.user_id == User.id)
                .where(Request.occurred_at < cutoff)
            ),
            conn,
        )
        # SQL performs daily reliability aggregation before the dashboard computes comparisons.
        day = (
            func.date(func.timezone("UTC", Request.occurred_at))
            if db.dialect.name == "postgresql"
            else func.date(Request.occurred_at)
        )
        daily_query = select(
            day.label("date"),
            func.count().label("requests"),
            func.sum(case((Request.status >= 400, 1), else_=0)).label("errors"),
            func.avg(Request.latency_ms).label("mean_latency_ms"),
        )
        daily_query = segment_filter(
            daily_query.join(User, Request.user_id == User.id)
            .where(Request.occurred_at < cutoff)
            .group_by(day)
        )
        daily = pd.read_sql(daily_query, conn)
        errors = pd.read_sql(
            select(ApiError)
            .join(Request, ApiError.request_id == Request.id)
            .join(User, Request.user_id == User.id)
            .where(Request.occurred_at < cutoff)
            .where(True if segment == "all" else User.segment == segment),
            conn,
        )
        auxiliary = {
            name: pd.read_sql(select(model), conn)
            for name, model in [
                ("releases", Release),
                ("incidents", Incident),
                ("runs", Run),
                ("rejections", Rejection),
                ("sessions", Session),
            ]
        }
    if not daily.empty:
        daily["date"] = pd.to_datetime(daily.date, utc=True)
        daily = daily.set_index("date").sort_index()
        daily["error_rate"] = daily.errors / daily.requests
    return dict(
        users=users, events=events, requests=requests, errors=errors, daily=daily, **auxiliary
    )
