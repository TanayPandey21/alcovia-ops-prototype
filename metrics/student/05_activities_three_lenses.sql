-- Every scheduled activity in the Alcovia rigour on three lenses:
--   Conducted = held ÷ planned, Liked = attendance + average rating (+ repeat participation),
--   Performed = soft-skill average where scored.
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-07-27' AS start_date, DATE '2026-10-25' AS end_date),
a AS (SELECT al.* FROM activity_log al, params WHERE day BETWEEN start_date AND end_date),
repeat AS (
  -- students who attended the activity type more than once ÷ students who attended it at least once
  SELECT activity, COUNT(*) FILTER (WHERE n > 1)::numeric / NULLIF(COUNT(*), 0) AS repeat_participation
  FROM (SELECT activity, student_id, COUNT(*) FILTER (WHERE attended) AS n FROM a GROUP BY 1, 2 HAVING COUNT(*) FILTER (WHERE attended) > 0) x
  GROUP BY activity
)
SELECT a.activity, MIN(a.level) AS level,
       COUNT(*)                                                  AS planned,
       ROUND(AVG(held::int), 3)                                  AS conducted_rate,
       ROUND(AVG(attended::int) FILTER (WHERE held), 3)          AS attendance,
       ROUND(AVG(rating) FILTER (WHERE held), 2)                 AS avg_rating,
       ROUND(MAX(repeat.repeat_participation), 3)                AS repeat_participation,
       ROUND(AVG(skill_score) FILTER (WHERE attended), 2)        AS soft_skill_avg
FROM a LEFT JOIN repeat USING (activity)
GROUP BY a.activity
ORDER BY array_position(ARRAY['Week','Month','Quarter'], MIN(a.level)), a.activity;
