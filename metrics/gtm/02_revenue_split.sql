-- Revenue and counts by stream: 3-month trials, full program (new), trial upgrades, workshops.
-- Also gives students onboarded (new trials + new full-program sign-ups) and program vs workshop share.
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-10-01' AS start_date, DATE '2026-10-25' AS end_date),
x AS (
  SELECT CASE WHEN stream = 'Workshop'             THEN 'Workshop'
              WHEN payment_type = 'Trial upgrade'  THEN 'Trial upgrade'
              WHEN plan = '3-month trial'          THEN '3-month trial'
              ELSE 'Full program (new)' END AS revenue_line,
         amount_inr
  FROM payments, params
  WHERE paid_on BETWEEN start_date AND end_date
)
SELECT revenue_line,
       COUNT(*)                                             AS payments,
       SUM(amount_inr)                                      AS revenue_inr,
       ROUND(SUM(amount_inr)::numeric / SUM(SUM(amount_inr)) OVER (), 3) AS share_of_revenue
FROM x
GROUP BY revenue_line
ORDER BY revenue_inr DESC;

-- Students onboarded in the period: new trials + new full-program sign-ups.
-- SELECT COUNT(*) FROM payments, params WHERE paid_on BETWEEN start_date AND end_date AND payment_type = 'New sign-up';
