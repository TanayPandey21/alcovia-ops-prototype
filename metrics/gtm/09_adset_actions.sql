-- RCA: one action per ad set from fixed rules, checked in order.
--   Watch     spend under Rs 5,000
--   Fix LP    CTR >= 1% but load > 3 s or LP conversion under 1.5% (program) / 4% (workshop)
--   Kill      cost per result over 2x target (Rs 1,900 per qualified lead, Rs 300 per workshop registration)
--   Refresh   frequency >= 3 or CTR down 30%+ vs previous period
--   Scale     cost at or under target and frequency under 2.5  (+20% budget a week)
--   Hold      none of the above
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-09-26' AS start_date, DATE '2026-10-25' AS end_date, 1900 AS cpql_target, 300 AS cpr_workshop_target),
p AS (SELECT *, start_date - (end_date - start_date + 1) AS prev_start, start_date - 1 AS prev_end FROM params),
cur AS (
  SELECT campaign_type, campaign || ' / ' || ad_set AS ad_set_key, campaign, ad_set,
         SUM(spend_inr) AS spend, SUM(clicks)::numeric / NULLIF(SUM(impressions), 0) AS ctr,
         SUM(lp_submits)::numeric / NULLIF(SUM(lp_visits), 0) AS lp_conv, AVG(lp_load_s) AS load_s,
         AVG(frequency_7d) FILTER (WHERE day > p.end_date - 7) AS freq, SUM(lp_submits) AS regs
  FROM ad_daily, p WHERE day BETWEEN p.start_date AND p.end_date GROUP BY 1, 2, 3, 4
),
prev AS (
  SELECT campaign, ad_set, SUM(clicks)::numeric / NULLIF(SUM(impressions), 0) AS ctr
  FROM ad_daily, p WHERE day BETWEEN p.prev_start AND p.prev_end GROUP BY 1, 2
),
ql AS (
  SELECT campaign, ad_set, COUNT(*) AS q FROM leads, p
  WHERE channel = 'Meta' AND stage_index >= 1 AND created_on BETWEEN p.start_date AND p.end_date GROUP BY 1, 2
),
m AS (
  SELECT cur.*, ROUND(cur.ctr / NULLIF(prev.ctr, 0) - 1, 3) AS ctr_change,
         CASE WHEN campaign_type = 'Program' THEN COALESCE(ql.q, 0) ELSE regs END AS results,
         CASE WHEN campaign_type = 'Program' THEN (SELECT cpql_target FROM params) ELSE (SELECT cpr_workshop_target FROM params) END AS target,
         CASE WHEN campaign_type = 'Program' THEN 0.015 ELSE 0.04 END AS lp_min
  FROM cur LEFT JOIN prev USING (campaign, ad_set) LEFT JOIN ql USING (campaign, ad_set)
)
SELECT ad_set_key, campaign_type, spend AS spend_inr,
       ROUND(spend / NULLIF(results, 0)) AS cost_per_result_inr, ROUND(freq, 2) AS frequency_7d, ctr_change,
       ROUND(lp_conv, 3) AS lp_conversion, ROUND(load_s, 1) AS lp_load_s,
       CASE
         WHEN spend < 5000                                                  THEN 'Watch'
         WHEN ctr >= 0.01 AND (load_s > 3 OR lp_conv < lp_min)              THEN 'Fix LP'
         WHEN results = 0 OR spend / results > 2 * target                   THEN 'Kill'
         WHEN freq >= 3 OR ctr_change <= -0.3                               THEN 'Refresh'
         WHEN spend / results <= target AND freq < 2.5                      THEN 'Scale'
         ELSE 'Hold'
       END AS action
FROM m
ORDER BY array_position(ARRAY['Kill','Fix LP','Refresh','Scale','Hold','Watch'],
         CASE WHEN spend < 5000 THEN 'Watch' WHEN ctr >= 0.01 AND (load_s > 3 OR lp_conv < lp_min) THEN 'Fix LP'
              WHEN results = 0 OR spend / results > 2 * target THEN 'Kill' WHEN freq >= 3 OR ctr_change <= -0.3 THEN 'Refresh'
              WHEN spend / results <= target AND freq < 2.5 THEN 'Scale' ELSE 'Hold' END), spend DESC;
