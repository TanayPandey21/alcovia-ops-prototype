-- Headline funnel KPIs for the period:
--   cost per qualified lead (Meta spend on program ads ÷ qualified Meta leads)
--   program conversion (sign-ups closed in period ÷ qualified leads created in period)
--   discovery show-up rate, organic lead count, average lead journey (days lead → signed up / lost)
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-10-01' AS start_date, DATE '2026-10-25' AS end_date),
c AS (SELECT l.* FROM leads l, params WHERE created_on BETWEEN start_date AND end_date),
closed AS (SELECT l.* FROM leads l, params WHERE closed_on BETWEEN start_date AND end_date),
spend AS (SELECT SUM(spend_inr) AS s FROM ad_daily, params WHERE day BETWEEN start_date AND end_date AND campaign_type = 'Program')
SELECT
  (SELECT COUNT(*) FROM c)                                                          AS total_leads,
  (SELECT COUNT(*) FROM c WHERE stage_index >= 1)                                   AS qualified_leads,
  ROUND((SELECT s FROM spend) / NULLIF((SELECT COUNT(*) FROM c WHERE stage_index >= 1 AND channel = 'Meta'), 0)) AS cost_per_qualified_lead_inr,
  ROUND((SELECT COUNT(*) FROM closed WHERE outcome = 'Signed up')::numeric
        / NULLIF((SELECT COUNT(*) FROM c WHERE stage_index >= 1), 0), 3)            AS program_conversion,
  ROUND((SELECT COUNT(*) FROM c WHERE stage_index >= 3)::numeric
        / NULLIF((SELECT COUNT(*) FROM c WHERE stage_index >= 2), 0), 3)            AS discovery_show_up_rate,
  ROUND(1 - (SELECT COUNT(*) FROM c WHERE stage_index >= 4)::numeric
        / NULLIF((SELECT COUNT(*) FROM c WHERE stage_index >= 3), 0), 3)            AS ambition_interview_drop_off,
  (SELECT COUNT(*) FROM c WHERE channel <> 'Meta')                                  AS organic_and_referral_leads,
  ROUND((SELECT AVG(closed_on - created_on) FROM closed), 1)                        AS avg_lead_journey_days;
