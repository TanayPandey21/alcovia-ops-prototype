-- One row per Alcovian: habits, academics, wellbeing, growth and a health score out of 100
-- (academics 40, habits 25, wellbeing 15, growth 20), plus a red / amber / green flag. Feeds Student 360.
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-09-26' AS start_date, DATE '2026-10-25' AS end_date),
d AS (
  SELECT student_id,
         AVG(app_min) AS app_min_day, AVG(focus_min) AS focus_min_day, AVG(quiz_taken::int) AS quiz_participation,
         SUM(tasks_done)::numeric / NULLIF(SUM(tasks_planned), 0) AS task_completion,
         SUM(tasks_on_time)::numeric / NULLIF(SUM(tasks_planned), 0) AS deadline_adherence,
         GREATEST(0, 1 - ABS(SUM(actual_min) - SUM(est_min))::numeric / NULLIF(SUM(est_min), 0)) AS time_estimate_accuracy,
         AVG(sleep_h) AS sleep_h
  FROM student_daily, params WHERE day BETWEEN start_date AND end_date GROUP BY student_id
),
c AS (
  SELECT student_id, AVG(readiness) AS readiness, AVG(completion_pct - expected_pct) AS pace_gap
  FROM chapter_snapshots WHERE week_end = (SELECT MAX(week_end) FROM chapter_snapshots, params WHERE week_end <= end_date)
  GROUP BY student_id
),
r AS (SELECT student_id, SUM(milestones_on_time)::numeric / NULLIF(SUM(milestones_due), 0) AS roadmap_on_time FROM roadmaps GROUP BY student_id),
s AS (
  SELECT st.student_id, st.display_name, st.advisor, d.*, c.readiness, c.pace_gap, r.roadmap_on_time,
         ROUND(
           40 * (0.5 * c.readiness / 100 + 0.5 * LEAST(1, GREATEST(0, (c.pace_gap + 20) / 30)))
         + 25 * (COALESCE(d.task_completion, 0) + LEAST(1, d.focus_min_day / 60)) / 2
         + 15 * COALESCE(LEAST(1, d.sleep_h / 8), 0.7)
         + 20 * COALESCE(r.roadmap_on_time, 0)) AS health_score
  FROM students st JOIN d USING (student_id) JOIN c USING (student_id) LEFT JOIN r USING (student_id)
)
SELECT display_name, advisor, health_score,
       CASE WHEN health_score >= 70 THEN 'Green' WHEN health_score >= 55 THEN 'Amber' ELSE 'Red' END AS rag,
       ROUND(app_min_day, 1) AS app_min_day, ROUND(focus_min_day, 1) AS focus_min_day,
       ROUND(quiz_participation, 2) AS quiz_participation, ROUND(task_completion, 2) AS task_completion,
       ROUND(deadline_adherence, 2) AS deadline_adherence, ROUND(time_estimate_accuracy, 2) AS time_estimate_accuracy,
       ROUND(readiness) AS readiness, ROUND(pace_gap, 1) AS pace_gap, ROUND(sleep_h, 1) AS sleep_h,
       CASE WHEN pace_gap < -10 THEN 'Behind on syllabus'
            WHEN app_min_day < 5 THEN 'Barely using the app'
            WHEN quiz_participation < 0.3 THEN 'Skipping the daily quiz'
            WHEN sleep_h < 7 THEN 'Sleeping under 7 h'
            WHEN task_completion < 0.5 THEN 'Low task completion'
            ELSE 'On track' END AS flag
FROM s
ORDER BY health_score;
