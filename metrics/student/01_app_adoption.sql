-- App adoption by week: meaningful minutes per enrolled student per day (mean AND median),
-- focus minutes, daily active students, and students with at least one learning action (north-star).
SET search_path TO alcovia;
WITH per_student_week AS (
  SELECT date_trunc('week', day)::date AS week, student_id,
         AVG(app_min) AS app_min_day, AVG(focus_min) AS focus_min_day,
         BOOL_OR(active) AS had_learning_action
  FROM student_daily GROUP BY 1, 2
),
daily_active AS (
  SELECT date_trunc('week', day)::date AS week, AVG(n) AS avg_daily_active
  FROM (SELECT day, COUNT(*) FILTER (WHERE active) AS n FROM student_daily GROUP BY day) d GROUP BY 1
)
SELECT w.week,
       ROUND(AVG(app_min_day), 1)                                              AS mean_meaningful_min_day,
       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY app_min_day)::numeric, 1) AS median_meaningful_min_day,
       ROUND(AVG(focus_min_day), 1)                                            AS mean_focus_min_day,
       ROUND(MAX(d.avg_daily_active), 1)                                       AS avg_daily_active_students,
       COUNT(*) FILTER (WHERE had_learning_action)                             AS weekly_students_with_learning_action,
       COUNT(*)                                                                AS enrolled
FROM per_student_week w JOIN daily_active d USING (week)
GROUP BY w.week ORDER BY w.week;
