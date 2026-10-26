-- Revenue collected vs target for a period, with the change on the previous period of equal length.
-- Target = monthly target pro-rated by the days of each month that fall inside the period.
-- Change :start_date / :end_date in params to move the window.
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-10-01' AS start_date, DATE '2026-10-25' AS end_date),
p AS (
  SELECT start_date, end_date,
         start_date - (end_date - start_date + 1) AS prev_start, start_date - 1 AS prev_end
  FROM params
),
target AS (
  SELECT SUM(t.revenue_target
             * (LEAST(p.end_date, (t.month + INTERVAL '1 month - 1 day')::date) - GREATEST(p.start_date, t.month) + 1)
             / EXTRACT(DAY FROM (t.month + INTERVAL '1 month - 1 day'))) AS target_inr
  FROM monthly_targets t, p
  WHERE t.month <= p.end_date AND (t.month + INTERVAL '1 month - 1 day')::date >= p.start_date
)
SELECT
  SUM(pay.amount_inr) FILTER (WHERE pay.paid_on BETWEEN p.start_date AND p.end_date)          AS revenue_inr,
  ROUND((SELECT target_inr FROM target))                                                     AS target_inr,
  ROUND(SUM(pay.amount_inr) FILTER (WHERE pay.paid_on BETWEEN p.start_date AND p.end_date)
        / NULLIF((SELECT target_inr FROM target), 0), 3)                                     AS attainment,
  SUM(pay.amount_inr) FILTER (WHERE pay.paid_on BETWEEN p.prev_start AND p.prev_end)          AS prev_revenue_inr,
  ROUND(SUM(pay.amount_inr) FILTER (WHERE pay.paid_on BETWEEN p.start_date AND p.end_date)::numeric
        / NULLIF(SUM(pay.amount_inr) FILTER (WHERE pay.paid_on BETWEEN p.prev_start AND p.prev_end), 0) - 1, 3) AS change_vs_prev
FROM payments pay, p
GROUP BY p.start_date;
