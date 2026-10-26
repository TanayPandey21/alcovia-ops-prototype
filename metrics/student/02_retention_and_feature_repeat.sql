-- D7 / D30 retention and 7-day feature repeat rate, from raw app_events.
-- (Runs on the production event stream; the sample seed has no raw events, so it returns no rows there.)
SET search_path TO alcovia;
WITH first_seen AS (
  SELECT student_id, MIN(occurred_at)::date AS first_day FROM app_events GROUP BY student_id
),
retention AS (
  SELECT f.student_id,
         BOOL_OR(e.occurred_at::date BETWEEN f.first_day + 7 AND f.first_day + 13) AS retained_d7,
         BOOL_OR(e.occurred_at::date BETWEEN f.first_day + 30 AND f.first_day + 36) AS retained_d30
  FROM first_seen f JOIN app_events e USING (student_id) GROUP BY f.student_id
),
feature_first AS (
  SELECT student_id, feature, MIN(occurred_at) AS first_use
  FROM app_events WHERE event_name = 'feature_viewed' GROUP BY 1, 2
),
feature_repeat AS (
  SELECT ff.feature,
         COUNT(DISTINCT ff.student_id) AS first_time_users,
         COUNT(DISTINCT ff.student_id) FILTER (WHERE EXISTS (
           SELECT 1 FROM app_events e WHERE e.student_id = ff.student_id AND e.feature = ff.feature
             AND e.occurred_at > ff.first_use + INTERVAL '1 hour' AND e.occurred_at <= ff.first_use + INTERVAL '7 days')) AS repeat_users
  FROM feature_first ff GROUP BY ff.feature
)
SELECT 'retention' AS metric, NULL AS feature,
       ROUND(AVG(retained_d7::int), 3) AS d7_or_repeat_rate, ROUND(AVG(retained_d30::int), 3) AS d30
FROM retention
UNION ALL
SELECT 'feature_repeat_7d', feature, ROUND(repeat_users::numeric / NULLIF(first_time_users, 0), 3), NULL
FROM feature_repeat;
