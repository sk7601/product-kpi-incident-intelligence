-- UTC daily SQL aggregation; denominator is every API request, including successful ones.
WITH daily AS (
 SELECT DATE(occurred_at AT TIME ZONE 'UTC') AS day, endpoint,
        COUNT(*) AS requests, COUNT(*) FILTER (WHERE status >= 400) AS failures
 FROM api_requests GROUP BY 1, 2
), rates AS (
 SELECT *, failures::double precision / NULLIF(requests, 0) AS error_rate FROM daily
)
SELECT *, AVG(error_rate) OVER (PARTITION BY endpoint ORDER BY day
 ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING) AS past_only_baseline,
 DENSE_RANK() OVER (PARTITION BY day ORDER BY error_rate DESC) AS endpoint_rank
FROM rates ORDER BY day;

-- Ordered seven-day activation: cohort denominator is mature signups, not active users.
-- Use bound :cutoff timestamp and :cohort_start when running via SQLAlchemy text().
WITH eligible AS (
 SELECT id, registered_at FROM users
 WHERE registered_at >= :cohort_start
   AND registered_at < :cutoff - INTERVAL '7 days'
), activated AS (
 SELECT DISTINCT u.id FROM eligible u JOIN product_events e ON e.user_id = u.id
 WHERE e.name = 'activate' AND e.occurred_at >= u.registered_at
   AND e.occurred_at < u.registered_at + INTERVAL '7 days'
)
SELECT COUNT(a.id)::double precision / NULLIF(COUNT(u.id),0) AS activation_rate
FROM eligible u LEFT JOIN activated a ON a.id = u.id;
-- This query reports activation only; Python's multi-step funnel additionally enforces
-- chronological register/login/dashboard/activate order for the same eligible cohort.

-- Rejection audit for pipeline root-cause investigation.
SELECT r.id, r.status, q.table_name, q.reason, COUNT(*) AS exceptions
FROM ingestion_runs r JOIN rejections q ON r.id = q.run_id
GROUP BY r.id, r.status, q.table_name, q.reason ORDER BY exceptions DESC;
