-- 3-month trials ending in the next 30 days, flagged when the renewal call is not booked or at risk.
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-10-25' AS today, 30 AS horizon_days)
SELECT family, trial_start, trial_end, trial_end - today AS days_left, advisor, renewal_call,
       renewal_call IN ('Not booked', 'Done – at risk') AS needs_action
FROM trials, params
WHERE trial_end BETWEEN today AND today + horizon_days
ORDER BY days_left;
