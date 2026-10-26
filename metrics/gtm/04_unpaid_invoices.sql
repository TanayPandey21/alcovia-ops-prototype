-- Invoices raised but not paid, aged into 0–7 / 8–15 / 15+ day buckets (as of :today).
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-10-25' AS today)
SELECT invoice_id, family, item, amount_inr, issued_on, owner,
       today - issued_on AS days_open,
       CASE WHEN today - issued_on <= 7  THEN '0–7 days'
            WHEN today - issued_on <= 15 THEN '8–15 days'
            ELSE '15+ days' END AS age_bucket
FROM invoices, params
WHERE status = 'Unpaid'
ORDER BY days_open DESC;
