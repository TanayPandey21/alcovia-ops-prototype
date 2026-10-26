-- Landing page health: visits, submits, conversion, drop-off and average mobile load time.
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-09-26' AS start_date, DATE '2026-10-25' AS end_date)
SELECT landing_page,
       SUM(lp_visits)                                              AS visits,
       SUM(lp_submits)                                             AS submits,
       ROUND(SUM(lp_submits)::numeric / NULLIF(SUM(lp_visits), 0), 3)     AS conversion,
       ROUND(1 - SUM(lp_submits)::numeric / NULLIF(SUM(lp_visits), 0), 3) AS drop_off,
       ROUND(AVG(lp_load_s), 1)                                    AS load_s,
       AVG(lp_load_s) > 3                                          AS slow_page
FROM ad_daily, params
WHERE day BETWEEN start_date AND end_date
GROUP BY landing_page
ORDER BY drop_off DESC;
