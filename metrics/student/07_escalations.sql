-- Subjects to escalate this week (read by n8n/syllabus_escalation.json):
--   gap <= -10 -> nudge student + flag advisor; <= -20 -> message parent + 2-week sprint;
--   <= -20 for two consecutive monthly snapshots -> trigger pre-agreed tutor support.
SET search_path TO alcovia;
WITH latest AS (SELECT MAX(week_end) AS w FROM chapter_snapshots),
cur AS (
  SELECT c.student_id, c.subject, c.completion_pct - c.expected_pct AS gap
  FROM chapter_snapshots c, latest WHERE c.week_end = latest.w
),
month_ago AS (
  SELECT c.student_id, c.subject, c.completion_pct - c.expected_pct AS gap
  FROM chapter_snapshots c, latest
  WHERE c.week_end = (SELECT MAX(week_end) FROM chapter_snapshots, latest WHERE week_end <= latest.w - 28)
)
SELECT st.display_name, st.advisor, cur.subject, ROUND(cur.gap, 1) AS pace_gap, ROUND(m.gap, 1) AS gap_month_ago,
       CASE WHEN cur.gap <= -20 AND m.gap <= -20 THEN 'Trigger tutor support'
            WHEN cur.gap <= -20 THEN 'Message parent + start 2-week sprint'
            ELSE 'Nudge student + flag advisor' END AS action
FROM cur JOIN students st USING (student_id) LEFT JOIN month_ago m USING (student_id, subject)
WHERE cur.gap <= -10
ORDER BY cur.gap;
