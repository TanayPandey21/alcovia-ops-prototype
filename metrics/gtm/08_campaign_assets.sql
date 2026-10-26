-- Every ad asset in the period: spend, CTR, CTR change vs previous period, 7-day frequency at period end,
-- results (qualified leads for program ads, registrations for workshop ads) and cost per result.
-- best_ctr / worst_ctr mark the assets to scale and to refresh within each campaign type.
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-09-26' AS start_date, DATE '2026-10-25' AS end_date),
p AS (SELECT start_date, end_date, start_date - (end_date - start_date + 1) AS prev_start, start_date - 1 AS prev_end FROM params),
cur AS (
  SELECT a.campaign_type, a.campaign, a.ad_set, a.asset,
         SUM(spend_inr) AS spend_inr, SUM(clicks)::numeric / NULLIF(SUM(impressions), 0) AS ctr,
         AVG(frequency_7d) FILTER (WHERE day > p.end_date - 7) AS frequency_end,
         SUM(lp_submits) AS registrations
  FROM ad_daily a, p WHERE day BETWEEN p.start_date AND p.end_date
  GROUP BY 1, 2, 3, 4
),
prev AS (
  SELECT asset, SUM(clicks)::numeric / NULLIF(SUM(impressions), 0) AS ctr
  FROM ad_daily, p WHERE day BETWEEN p.prev_start AND p.prev_end GROUP BY asset
),
ql AS (
  SELECT asset, COUNT(*) AS qualified
  FROM leads, p WHERE channel = 'Meta' AND stage_index >= 1 AND created_on BETWEEN p.start_date AND p.end_date
  GROUP BY asset
)
SELECT cur.campaign_type, cur.campaign, cur.ad_set, cur.asset, cur.spend_inr,
       ROUND(cur.ctr, 4)                                   AS ctr,
       ROUND(cur.ctr / NULLIF(prev.ctr, 0) - 1, 3)         AS ctr_change,
       ROUND(cur.frequency_end, 2)                         AS frequency_7d,
       CASE WHEN cur.campaign_type = 'Program' THEN COALESCE(ql.qualified, 0) ELSE cur.registrations END AS results,
       ROUND(cur.spend_inr / NULLIF(CASE WHEN cur.campaign_type = 'Program' THEN ql.qualified ELSE cur.registrations END, 0)) AS cost_per_result_inr,
       cur.ctr = MAX(cur.ctr) OVER (PARTITION BY cur.campaign_type) AS best_ctr,
       cur.ctr = MIN(cur.ctr) OVER (PARTITION BY cur.campaign_type) AS worst_ctr,
       cur.frequency_end >= 3                              AS frequency_alert
FROM cur
LEFT JOIN prev USING (asset)
LEFT JOIN ql USING (asset)
ORDER BY cur.campaign_type, cur.spend_inr DESC;
