-- Nightly rollup: app_events (+ wearable rows) -> student_daily for one day.
-- Run by n8n/nightly_student_rollup.json at 01:00 IST for the previous day ($1 = day).
-- Meaningful minutes = time between consecutive events in a session, capped at 2 min per gap
-- (so an app left open while idle does not count), only on learning features.
-- Time inside a focus session counts in full: the phone is locked to the app, so it is never idle.
SET search_path TO alcovia;
WITH e AS (
  SELECT student_id, session_id, event_name, feature, occurred_at, props,
         LEAD(occurred_at) OVER (PARTITION BY session_id ORDER BY occurred_at) AS next_at
  FROM app_events
  WHERE occurred_at >= $1::date AND occurred_at < $1::date + 1
),
mins AS (
  SELECT student_id,
         SUM(CASE WHEN next_at IS NULL THEN 0            -- last event of a session adds nothing
                  WHEN event_name = 'focus_started' THEN EXTRACT(EPOCH FROM (next_at - occurred_at)) / 60
                  ELSE LEAST(EXTRACT(EPOCH FROM (next_at - occurred_at)) / 60, 2) END)
           FILTER (WHERE feature IN ('home', 'focus', 'study', 'tasks', 'quiz', 'planner', 'realm')) AS app_min,
         SUM((props->>'minutes')::numeric) FILTER (WHERE event_name = 'focus_completed')          AS focus_min,
         BOOL_OR(event_name IN ('focus_completed', 'chapter_stage_completed', 'task_completed', 'quiz_answered')) AS active,
         BOOL_OR(event_name = 'quiz_answered')                                                       AS quiz_taken,
         MAX((props->>'score')::int) FILTER (WHERE event_name = 'quiz_answered')                    AS quiz_score,
         COUNT(*) FILTER (WHERE event_name = 'task_completed')                                       AS tasks_done,
         COUNT(*) FILTER (WHERE event_name = 'task_completed' AND (props->>'on_time')::boolean)      AS tasks_on_time,
         SUM((props->>'est_min')::int) FILTER (WHERE event_name = 'task_completed')                  AS est_min,
         SUM((props->>'actual_min')::int) FILTER (WHERE event_name = 'task_completed')               AS actual_min
  FROM e GROUP BY student_id
)
INSERT INTO student_daily (day, student_id, active, app_min, focus_min, quiz_taken, quiz_score, tasks_done, tasks_on_time, est_min, actual_min)
SELECT $1::date, s.student_id, COALESCE(m.active, false), COALESCE(m.app_min, 0), COALESCE(m.focus_min, 0),
       COALESCE(m.quiz_taken, false), m.quiz_score, COALESCE(m.tasks_done, 0), COALESCE(m.tasks_on_time, 0),
       COALESCE(m.est_min, 0), COALESCE(m.actual_min, 0)
FROM students s LEFT JOIN mins m USING (student_id)
WHERE s.status = 'Active'
ON CONFLICT (day, student_id) DO UPDATE SET
  active = EXCLUDED.active, app_min = EXCLUDED.app_min, focus_min = EXCLUDED.focus_min,
  quiz_taken = EXCLUDED.quiz_taken, quiz_score = EXCLUDED.quiz_score, tasks_done = EXCLUDED.tasks_done,
  tasks_on_time = EXCLUDED.tasks_on_time, est_min = EXCLUDED.est_min, actual_min = EXCLUDED.actual_min;
-- tasks_planned, slots_* come from the timetable sync; sleep_h / active_min from the wearable sync.
