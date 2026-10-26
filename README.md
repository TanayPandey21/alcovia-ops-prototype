# Alcovia ops prototype

The data layer behind Alcovia's GTM tracker and student progress dashboard: a Postgres schema, the SQL for every metric, the n8n workflows that fill it with no manual entry, and the app tracking plan.

**Live dashboards (sample data):**
- [GTM & revenue tracker](https://claude.ai/artifact/EBiH4yhvy7ENkCQi82XSN3): revenue vs target, trial / program / workshop split, Meta funnel, campaign health, scale / refresh / kill actions, unpaid invoices, trial renewals.
- [Student progress](https://claude.ai/artifact/2haUfAJrCkJGoLh6KPna7P): Conducted / Liked / Performed scorecard, app adoption trend, every activity on three lenses, student list, Student 360.

Executive brief and full plan: [brief](https://claude.ai/artifact/QJbCpTqjDrEFF5iZUjKirK) · [full plan](https://claude.ai/artifact/FHMTUWz5NjFHdKX4esouCR)

## How data flows

```
Meta Ads API ──┐                          ┌─> GTM tracker
Razorpay ──────┤                          │
ClickUp ───────┼─> n8n ─> Postgres ───────┼─> Student progress dashboard
Google Cal ────┤      (schema.sql)        │
Student app ───┤                          └─> n8n alerts: ClickUp chat, WhatsApp, in-app pushes
Wearables ─────┘
```

Capture once, reuse everywhere: no figure on a dashboard is typed by hand. The only manual inputs are 1-tap ratings, exam scores (with a photo), score targets once a term, and facilitator soft-skill scores during workshops.

## What's in the repo

| Path | What it is | Answers |
| --- | --- | --- |
| `db/schema.sql` | 20 tables: leads and funnel stages, payments, invoices, workshops, trials, targets, Meta ad data, students, app events, daily rollups, activities, syllabus snapshots, roadmaps, pulse, advisor inputs, sprints | All four problem statements |
| `db/views.sql` | Views the n8n workflows read (escalations, last-7-day ad set actions) | |
| `db/rollups/student_daily.sql` | Nightly rollup of app events into meaningful minutes, focus, quiz and tasks per student per day | App adoption (2.15 → 30 min) |
| `db/seed/` | Sample data (20 made-up students, Apr–Oct 2026), the generators and `seed.sql` | Lets the queries run |
| `metrics/gtm/01–10` | Revenue vs target, revenue split, revenue per workshop, unpaid invoices, trial renewals, funnel, funnel KPIs (CPQL, conversion, show-up, journey), campaign assets, ad set actions, landing pages | GTM tracker |
| `metrics/student/01–07` | App adoption (mean + median meaningful minutes, north-star), D7/D30 retention and feature repeat, 12-KPI scorecard, per-student KPIs and health score, every activity on three lenses, advisor input KPIs, escalations | Student dashboard, app adoption |
| `n8n/01–07` | Importable workflows: Meta Ads hourly sync, Razorpay webhook, ClickUp lead sync + no-show rebooking (Smallest.ai), daily GTM alerts, session rating push, syllabus escalations, nightly rollup + missing-inputs digest | Minimal human intervention |
| `tracking/events.yaml` | App event plan (13 events) | App adoption |
| `dashboards/` | Source of both dashboard pages | Live dashboards |

## Run it

```bash
npm install
npm test          # loads schema + seed into in-memory Postgres 16 and runs all 17 metric queries
```

Each metric file starts with a `params` line (`start_date`, `end_date`), so it runs as-is in any Postgres client; change the dates to move the window.

To use the n8n workflows: import `n8n/*.json`, create the credentials named in each node (`Alcovia DB`, `Meta Ads token`, `ClickUp API`, `Alcovia app API`, `WhatsApp Cloud API`, `Smallest.ai API`, `Google Calendar`) and set the environment variables they reference (`META_AD_ACCOUNT_ID`, `RAZORPAY_WEBHOOK_SECRET`, `CLICKUP_TEAM_ID`, …). Regenerate them with `npm run n8n`.

## Key definitions

- **Meaningful minutes:** time between app events on learning features, capped at 2 minutes per gap so idle time doesn't count; time inside a focus session counts in full. Reported as mean and median.
- **Cost per qualified lead:** Meta spend on program ads ÷ qualified leads from Meta in the period. Target ₹1,900.
- **Program conversion:** sign-ups closed in the period ÷ qualified leads created in it.
- **Ad set action:** Watch (< ₹5,000 spent) → Fix LP (CTR ≥ 1% but load > 3 s or weak LP conversion) → Kill (cost > 2× target) → Refresh (frequency ≥ 3 or CTR down 30%) → Scale (≤ target, frequency < 2.5) → Hold.
- **Chapter readiness (0–100):** read 10, notes 15, practice at 70%+ 25, timed past paper 25, exam-ready at 80%+ 25.
- **Pace gap:** syllabus completion minus expected completion (25% a quarter, pro-rated by day). −10 nudges the student, −20 messages the parent and starts a sprint, −20 for two months triggers tutor support.
- **Health score (0–100):** academics 40, habits 25, wellbeing 15, growth 20.

## Limits

- All data is sample data; targets are starting proposals to reset after a week-1 baseline audit.
- With 20 students, experiment results are directional, not statistically significant.
- Retention and feature-repeat queries need the raw app event stream, which the sample seed doesn't include.
- The n8n workflows are tested for structure, not against live accounts; API field names (ClickUp custom fields, Razorpay notes) must match Alcovia's setup.
