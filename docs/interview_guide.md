# Interview preparation

## 45-second explanation

I built a product KPI and incident investigation platform with reproducible synthetic SaaS
telemetry. The pipeline validates event schemas, timestamps, references and user journeys before
storing accepted records and rejection evidence in PostgreSQL. Streamlit shows engagement,
conversion, retention and reliability. Statistical detectors compare metrics with prior-only
baselines, and investigations link changes to endpoint errors, segments and actual requests.
Reports work without a model; optional AI selects only existing evidence and approved suggestions.

## Two-minute explanation

A product analyst needs consistent definitions before deciding whether a KPI changed. I modeled
users, sessions, events, requests, errors, releases and incidents using a seeded90-day simulation.
It includes activity growth, declining feature use, a reliability incident, lower conversion and
recovery. Validation rejects malformed records while preserving evidence. Stable IDs and transactional
upserts make reruns reproducible, and independent run audits record failures.

SQL aggregates reliability while Python calculates distinct-user and cohort metrics. DAU/WAU/MAU
use explicit trailing windows. Conversion excludes immature signups and requires register, login,
dashboard and activation in order within seven days. Retention displays complete cohort weeks.
These decisions prevent denominator and time-window errors.

Z-score and MAD use previous observations only. Isolation Forest trains on an initial baseline.
I measure precision and recall against synthetic incident-day labels and explain why adaptive
baselines miss later days. Investigation compares endpoint rates, segments, error categories,
failed-request IDs and nearby releases, without claiming causation. Optional model output must
reference existing evidence and template IDs; numerical facts never come from generated prose.
Tests cover hand-checkable metrics, defects, incident onset, database idempotency and all dashboard
sections. PostgreSQL, Alembic, Docker Compose and CI support reproduction; SQLite makes an offline
recruiter demonstration simple.

## Execution flow and decisions

Read generation.py → validation.py → pipeline.py → database.py → services.py → analytics.py →
detection.py → investigation.py → reporting.py → app/dashboard.py. Generation is an explicitly
synthetic simulation. Validation checks syntax and reference meaning. SQLAlchemy supplies safe
queries, constraints and transactions; Alembic versions schema changes. Pandas handles cohorts,
distinct counts and quantiles; NumPy supplies seeded sampling; Scikit-learn supplies Isolation
Forest and evaluation; Plotly/Streamlit make evidence interactive.

The modular monolith avoids unnecessary queue/service infrastructure. SQL examples demonstrate
conditional request aggregation, prior-only windows, endpoint ranking and rejection reporting.
The model is optional because analytics must function without API spend or network access.
Restricting it to evidence/template selection sacrifices free prose for verifiable output.

## Ten likely questions

1. **Can WAU equal summed DAU?** Usually no: one user active on several days still counts once.
2. **Is stickiness retention?** No. DAU/MAU describes current activity frequency; retention follows
   a fixed acquisition cohort over later periods.
3. **Which users enter conversion?** Signups with a complete seven-day observed horizon; the same
   cohort supplies every funnel-stage denominator.
4. **Why require order?** A user completing events in an incompatible sequence did not traverse
   the defined journey. Strict timestamps prevent simultaneous events implying a sequence.
5. **How do you avoid retention censoring?** Omit incomplete cohort weeks instead of marking them zero.
6. **Why Z-score and MAD?** Z-score is interpretable but outlier-sensitive; median deviations resist
   a few extremes. Both require calibration and can adapt to sustained changes.
7. **Why shift the baseline?** Including today's value leaks the observation into its own comparison.
8. **Did v2 cause the incident?** Timing supports a hypothesis; trace, rollback or experimental evidence
   is needed to establish causality.
9. **How is AI grounded?** JSON facts and strict ID allowlists. Computed evidence supplies every fact;
   malformed or invented references fall back deterministically.
10. **How do reruns work?** Stable primary keys and bulk upserts. A different seed should use explicit
    transactional replacement to remove obsolete scenario rows while retaining audits.

## Edge cases and tests

Reject required nulls, naive/future dates, duplicates, wrong-user sessions, out-of-session events,
events before registration, features before login, bad status/latency and bad release/error references.
Null properties become {}; lists are rejected. Empty KPI denominators are NA. Rolling methods use
a variance floor; Isolation Forest rejects an entirely constant training matrix. Warm-up days are
excluded from evaluation. No observed requests does not imply zero failures. HTML is escaped;
API errors log safe categories only and preserve deterministic reports. Separate unit, persistence,
UI and mocked API tests check those behaviors; coverage's denominator is explicitly documented.

## Trade-offs and follow-up challenges

Discuss synthetic labels versus realism, rolling adaptation versus fixed baselines, timely conversion
versus complete observation, and constrained AI versus free prose. Never claim unmeasured production
accuracy or commercial value.

Five challenges: evaluate held-out seeds; separate acquisition-channel effects; support late events
with watermarks; deduplicate alerts across incident lifecycles; design a controlled rollout to test
the release hypothesis. Define expected behavior and manual fixtures before adding infrastructure.

## Ordered learning checklist

1. Event schemas, session semantics and synthetic scenarios —45minutes.
2. Trailing distinct-user counts and adoption denominators —45minutes.
3. Ordered funnels and observation censoring —60minutes.
4. Retention cohorts and returning-user definitions —60minutes.
5. Conditional SQL, windows, upserts and transactions —90minutes.
6. Z-score, MAD, variance floors and leakage —60minutes.
7. Isolation Forest, precision/recall and label limits —60minutes.
8. Association, causality and investigation evidence —45minutes.
9. Optional API contracts and untrusted log defense —45minutes.
10. Reproduce tests and rehearse all six sections —60minutes.

A Technical Product Analyst defines measurable behavior, validates inputs, investigates changes
and communicates evidence and uncertainty to product and engineering stakeholders.
