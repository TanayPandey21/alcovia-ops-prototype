-- Meta + organic funnel for leads created in the period: count reaching each stage,
-- step conversion, and drop-off. Show-up rate = attended ÷ discovery call set.
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-10-01' AS start_date, DATE '2026-10-25' AS end_date),
cohort AS (SELECT * FROM leads, params WHERE created_on BETWEEN start_date AND end_date),
counts AS (
  SELECT s.stage_index, s.stage, COUNT(c.lead_id) AS leads_reached
  FROM funnel_stages s
  LEFT JOIN cohort c ON c.stage_index >= s.stage_index
  GROUP BY s.stage_index, s.stage
)
SELECT stage_index, stage, leads_reached,
       ROUND(leads_reached::numeric / NULLIF(LAG(leads_reached) OVER (ORDER BY stage_index), 0), 3) AS step_conversion,
       LAG(leads_reached) OVER (ORDER BY stage_index) - leads_reached                             AS dropped_before_stage
FROM counts
ORDER BY stage_index;
