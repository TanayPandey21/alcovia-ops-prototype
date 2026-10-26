-- Revenue per fortnightly workshop (Rs 3,999 a seat), straight from Razorpay payments.
SET search_path TO alcovia;
WITH params AS (SELECT DATE '2026-07-01' AS start_date, DATE '2026-10-25' AS end_date)
SELECT w.workshop_id,
       w.held_on,
       COUNT(p.*)                         AS seats_sold,
       COALESCE(SUM(p.amount_inr), 0)     AS revenue_inr,
       MIN(p.paid_on)                     AS first_seat_paid_on
FROM workshops w
JOIN params ON w.held_on BETWEEN start_date AND end_date
LEFT JOIN payments p ON p.workshop_id = w.workshop_id
GROUP BY w.workshop_id, w.held_on
ORDER BY w.held_on DESC;
