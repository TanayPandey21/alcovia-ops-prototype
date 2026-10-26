-- The 12-KPI cohort scorecard: four KPIs each for Conducted, Liked, Performed, with target, red line and status.
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-09-26' AS start_date, DATE '2026-10-25' AS end_date),
a AS (SELECT al.* FROM activity_log al, params WHERE day BETWEEN start_date AND end_date),
q AS (SELECT qd.* FROM quiz_days qd, params WHERE day BETWEEN start_date AND end_date),
d AS (SELECT sd.* FROM student_daily sd, params WHERE day BETWEEN start_date AND end_date),
snap AS (SELECT * FROM chapter_snapshots WHERE week_end = (SELECT MAX(week_end) FROM chapter_snapshots, params WHERE week_end <= end_date)),
n AS (SELECT COUNT(*)::numeric AS students FROM students),
kpi AS (
  SELECT 'Conducted' AS lens, 'Sessions delivered' AS kpi, (SELECT AVG(held::int) FROM a) AS value, 0.95 AS target, 0.85 AS red_line
  UNION ALL SELECT 'Conducted', 'Daily quiz run rate', (SELECT AVG(sent::int) FROM q), 1.0, 0.97
  UNION ALL SELECT 'Conducted', 'Roadmaps current',
    (SELECT COUNT(*) FROM (SELECT student_id FROM roadmaps GROUP BY student_id HAVING BOOL_AND(is_current) AND COUNT(*) = 3) x) / (SELECT students FROM n), 1.0, 0.9
  UNION ALL SELECT 'Conducted', 'Data coverage (last 7 days)',
    (SELECT COUNT(DISTINCT student_id) FROM d, params WHERE day > end_date - 7 AND active) / (SELECT students FROM n), 0.9, 0.75
  UNION ALL SELECT 'Liked', 'Average session rating', (SELECT AVG(rating) FROM a WHERE held AND rating IS NOT NULL), 4.3, 3.8
  UNION ALL SELECT 'Liked', 'Attendance', (SELECT AVG(attended::int) FROM a WHERE held), 0.9, 0.8
  UNION ALL SELECT 'Liked', 'Quiz participation',
    (SELECT COUNT(*) FILTER (WHERE quiz_taken) FROM d) / NULLIF((SELECT COUNT(*) FILTER (WHERE sent) FROM q) * (SELECT students FROM n), 0), 0.7, 0.5
  UNION ALL SELECT 'Liked', 'Would recommend (NPS)',
    (SELECT 100.0 * (COUNT(*) FILTER (WHERE score >= 9) - COUNT(*) FILTER (WHERE score <= 6)) / COUNT(*)
       FROM pulse, params WHERE month = date_trunc('month', end_date)::date), 50, 20
  UNION ALL SELECT 'Performed', 'Chapter readiness', (SELECT AVG(readiness) FROM snap), 75, 60
  UNION ALL SELECT 'Performed', 'Pace gap (pts)', (SELECT AVG(completion_pct - expected_pct) FROM snap), 0, -10
  UNION ALL SELECT 'Performed', 'Habit score',
    (SELECT AVG((tc + da + LEAST(1, fm / 120)) / 3) FROM (
       SELECT student_id, SUM(tasks_done)::numeric / NULLIF(SUM(tasks_planned), 0) AS tc,
              SUM(tasks_on_time)::numeric / NULLIF(SUM(tasks_planned), 0) AS da, AVG(focus_min) AS fm
       FROM d GROUP BY student_id) h), 0.75, 0.6
  UNION ALL SELECT 'Performed', 'Roadmap milestones on time', (SELECT SUM(milestones_on_time)::numeric / SUM(milestones_due) FROM roadmaps), 0.8, 0.6
)
SELECT lens, kpi, ROUND(value::numeric, 3) AS value, target, red_line,
       CASE WHEN value IS NULL THEN 'No data' WHEN value >= target THEN 'Green' WHEN value >= red_line THEN 'Amber' ELSE 'Red' END AS status
FROM kpi;
