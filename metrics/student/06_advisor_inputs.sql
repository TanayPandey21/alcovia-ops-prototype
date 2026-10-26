-- Input metrics for the academic advisor (the brief's section 4):
--   targets set and parent-signed, weekly inputs done on time, catch-up sprints started and closing the gap.
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-09-26' AS start_date, DATE '2026-10-25' AS end_date),
t AS (
  SELECT st.advisor,
         COUNT(DISTINCT st.student_id) AS students,
         COUNT(DISTINCT sc.student_id) FILTER (WHERE sc.parent_signed_on IS NOT NULL) AS students_with_signed_targets
  FROM students st LEFT JOIN score_targets sc USING (student_id) GROUP BY st.advisor
),
i AS (
  SELECT st.advisor,
         AVG((l.done_on IS NOT NULL AND l.done_on <= l.due_on)::int) AS inputs_on_time,
         COUNT(*) FILTER (WHERE l.done_on IS NULL) AS inputs_missing
  FROM advisor_input_log l JOIN students st USING (student_id), params
  WHERE l.due_on BETWEEN start_date AND end_date GROUP BY st.advisor
),
s AS (
  SELECT st.advisor,
         COUNT(*) AS sprints_triggered,
         AVG((sp.started_on IS NOT NULL AND sp.started_on - sp.triggered_on <= 7)::int) AS sprints_started_within_7d,
         AVG(sp.gap_after - sp.pace_gap) FILTER (WHERE sp.closed_on IS NOT NULL) AS avg_gap_recovered_pts
  FROM sprints sp JOIN students st USING (student_id) GROUP BY st.advisor
)
SELECT t.advisor, t.students,
       ROUND(t.students_with_signed_targets::numeric / t.students, 2) AS targets_parent_signed,
       ROUND(i.inputs_on_time, 2)          AS inputs_on_time,
       i.inputs_missing,
       s.sprints_triggered,
       ROUND(s.sprints_started_within_7d, 2) AS sprints_started_within_7d,
       ROUND(s.avg_gap_recovered_pts, 1)   AS avg_gap_recovered_pts
FROM t LEFT JOIN i USING (advisor) LEFT JOIN s USING (advisor)
ORDER BY t.advisor;
