-- Alcovia operations data layer (PostgreSQL 14+)
-- One database fed by n8n (Meta Ads, Razorpay, ClickUp, Google Calendar, wearables)
-- and by the student app's event stream. Dashboards only read from here.

CREATE SCHEMA IF NOT EXISTS alcovia;
SET search_path TO alcovia;

-- ---------------------------------------------------------------
-- GTM: leads, funnel, payments, invoices, ads
-- ---------------------------------------------------------------

-- Funnel stages, in order. stage_index is what funnel queries count on.
CREATE TABLE funnel_stages (
  stage_index  smallint PRIMARY KEY,
  stage        text NOT NULL UNIQUE
);
INSERT INTO funnel_stages VALUES
  (0, 'Lead'), (1, 'Qualified'), (2, 'Discovery call set'), (3, 'Discovery call attended'),
  (4, 'Ambition interview'), (5, 'Architect session'), (6, 'Signed up');

-- One row per lead. Synced from ClickUp on every status change (n8n/clickup_lead_sync.json).
CREATE TABLE leads (
  lead_id        text PRIMARY KEY,               -- ClickUp task id
  created_on     date NOT NULL,
  channel        text NOT NULL CHECK (channel IN ('Meta', 'Organic', 'Referral')),
  campaign       text,                           -- from UTM; '(organic)' when none
  ad_set         text,
  asset          text,
  stage_index    smallint NOT NULL REFERENCES funnel_stages,  -- furthest stage reached
  outcome        text NOT NULL CHECK (outcome IN ('Open', 'Signed up', 'Lost')),
  lost_reason    text,
  plan           text CHECK (plan IN ('3-month trial', 'Full program')),
  closed_on      date
);
CREATE INDEX ON leads (created_on);
CREATE INDEX ON leads (closed_on);

-- Every stage a lead entered, with its timestamp (ClickUp status history).
CREATE TABLE lead_stage_events (
  lead_id      text REFERENCES leads ON DELETE CASCADE,
  stage_index  smallint REFERENCES funnel_stages,
  entered_on   date NOT NULL,
  PRIMARY KEY (lead_id, stage_index)
);

-- Fortnightly career workshops, sold at Rs 3,999 a seat.
CREATE TABLE workshops (
  workshop_id  text PRIMARY KEY,
  held_on      date NOT NULL,
  title        text,
  seat_price   integer NOT NULL DEFAULT 3999
);

-- Razorpay invoices (program sign-ups and trial upgrades).
CREATE TABLE invoices (
  invoice_id   text PRIMARY KEY,
  family       text NOT NULL,
  item         text NOT NULL CHECK (item IN ('3-month trial', 'Full program', 'Trial upgrade')),
  amount_inr   integer NOT NULL,
  issued_on    date NOT NULL,
  status       text NOT NULL CHECK (status IN ('Paid', 'Unpaid', 'Cancelled')),
  paid_on      date,
  owner        text                               -- sales owner chased by the alerts
);

-- Every rupee collected. Written by the Razorpay webhook (n8n/razorpay_webhook.json).
CREATE TABLE payments (
  razorpay_payment_id  text PRIMARY KEY,
  paid_on      date NOT NULL,
  stream       text NOT NULL CHECK (stream IN ('Program', 'Workshop')),
  plan         text NOT NULL,                     -- '3-month trial' | 'Full program' | 'Workshop seat'
  payment_type text NOT NULL,                     -- 'New sign-up' | 'Trial upgrade' | 'Workshop seat'
  amount_inr   integer NOT NULL,
  invoice_id   text REFERENCES invoices,
  workshop_id  text REFERENCES workshops
);
CREATE INDEX ON payments (paid_on);

-- 3-month trials and their renewal status (ClickUp student record).
CREATE TABLE trials (
  family         text PRIMARY KEY,
  trial_start    date NOT NULL,
  trial_end      date NOT NULL,
  advisor        text NOT NULL,
  renewal_call   text NOT NULL DEFAULT 'Not booked'   -- Not booked | Booked | Done – likely | Done – at risk | Renewed | Churned
);

CREATE TABLE monthly_targets (
  month           date PRIMARY KEY,                 -- first day of month
  revenue_target  integer NOT NULL,
  signup_target   integer NOT NULL,
  cpql_target     integer NOT NULL DEFAULT 1900,   -- cost per qualified lead, program ads
  cpr_workshop    integer NOT NULL DEFAULT 300     -- cost per workshop registration
);

-- Meta Ads insights, one row per ad per day (n8n/meta_ads_sync.json), with landing-page health joined in.
CREATE TABLE ad_daily (
  day            date NOT NULL,
  campaign_type  text NOT NULL CHECK (campaign_type IN ('Program', 'Workshop')),
  campaign       text NOT NULL,
  ad_set         text NOT NULL,
  asset          text NOT NULL,
  format         text,
  landing_page   text,
  spend_inr      integer NOT NULL,
  impressions    integer NOT NULL,
  reach          integer NOT NULL,
  frequency_7d   numeric(5,2),
  clicks         integer NOT NULL,
  lp_visits      integer NOT NULL,                 -- GA4
  lp_submits     integer NOT NULL,                 -- GA4 form submit
  lp_load_s      numeric(4,2),                     -- PageSpeed, mobile
  PRIMARY KEY (day, asset)
);

-- ---------------------------------------------------------------
-- Students: app usage, academics, activities
-- ---------------------------------------------------------------

CREATE TABLE students (
  student_id   text PRIMARY KEY,                  -- pseudonymous id used in analytics
  display_name text NOT NULL,
  grade        smallint,
  advisor      text NOT NULL,
  parent_phone text,                              -- WhatsApp, E.164
  wearable     text NOT NULL DEFAULT 'None',      -- Apple Watch | Samsung Watch | WHOOP | Garmin | None
  enrolled_on  date,
  status       text NOT NULL DEFAULT 'Active'
);

-- Raw app events (see tracking/events.yaml). Kept for funnels and retention.
CREATE TABLE app_events (
  event_id     bigserial PRIMARY KEY,
  student_id   text NOT NULL REFERENCES students,
  session_id   text NOT NULL,
  event_name   text NOT NULL,
  feature      text,
  occurred_at  timestamptz NOT NULL,
  props        jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX ON app_events (student_id, occurred_at);
CREATE INDEX ON app_events (event_name, occurred_at);

-- Nightly rollup of app_events + wearables, one row per student per day
-- (n8n/nightly_student_rollup.json). Most student KPIs read from here.
CREATE TABLE student_daily (
  day              date NOT NULL,
  student_id       text NOT NULL REFERENCES students,
  active           boolean NOT NULL,              -- did at least one meaningful action
  app_min          numeric(6,1) NOT NULL DEFAULT 0,   -- meaningful minutes, idle excluded
  focus_min        numeric(6,1) NOT NULL DEFAULT 0,
  quiz_taken       boolean NOT NULL DEFAULT false,
  quiz_score       smallint,                      -- out of 10
  tasks_planned    smallint NOT NULL DEFAULT 0,
  tasks_done       smallint NOT NULL DEFAULT 0,
  tasks_on_time    smallint NOT NULL DEFAULT 0,
  est_min          integer NOT NULL DEFAULT 0,    -- estimated minutes on done tasks
  actual_min       integer NOT NULL DEFAULT 0,    -- focus minutes tagged to those tasks
  slots_planned    smallint NOT NULL DEFAULT 0,   -- self-study slots in timetable
  slots_done       smallint NOT NULL DEFAULT 0,
  sleep_h          numeric(3,1),                  -- wearable, null when none
  active_min       smallint,                      -- wearable
  PRIMARY KEY (day, student_id)
);

CREATE TABLE quiz_days (
  day       date PRIMARY KEY,
  sent      boolean NOT NULL,
  topic     text
);

-- Every planned activity per Alcovian: academic sessions, workshops, pods, peers, mentor calls,
-- branding shoots, podcasts, competitions, parent-child and out-of-city events.
-- held/attended from Google Calendar + Meet (n8n), rating from the 1-tap push (n8n/session_rating_push.json),
-- skill_score from the facilitator form during workshop simulations.
CREATE TABLE activity_log (
  activity_id  bigserial PRIMARY KEY,
  day          date NOT NULL,
  activity     text NOT NULL,
  level        text NOT NULL CHECK (level IN ('Day', 'Week', 'Month', 'Quarter')),
  student_id   text NOT NULL REFERENCES students,
  planned      boolean NOT NULL DEFAULT true,
  held         boolean NOT NULL,
  attended     boolean NOT NULL DEFAULT false,
  rating       smallint CHECK (rating BETWEEN 1 AND 5),
  skill_score  numeric(2,1),                      -- average of the 11 soft skills, 1–5
  outcome      text                               -- e.g. competition result, podcast published
);
CREATE INDEX ON activity_log (day);

-- Weekly snapshot of syllabus progress per subject (from chapter stages in the app).
CREATE TABLE chapter_snapshots (
  week_end          date NOT NULL,
  student_id        text NOT NULL REFERENCES students,
  subject           text NOT NULL,
  completion_pct    numeric(5,1) NOT NULL,        -- chapters at readiness 100 / chapters in syllabus
  expected_pct      numeric(5,1) NOT NULL,        -- 25% per quarter, pro-rated by day
  readiness         numeric(5,1) NOT NULL,        -- 0–100, 5-stage rigour weights 10/15/25/25/25
  rigour_adherence  numeric(3,2) NOT NULL,        -- chapters done with all 5 stages / chapters marked done
  PRIMARY KEY (week_end, student_id, subject)
);

CREATE TABLE roadmaps (
  student_id          text REFERENCES students,
  roadmap             text CHECK (roadmap IN ('Academic', 'Personal', 'Career')),
  is_current          boolean NOT NULL,
  milestones_due      smallint NOT NULL,
  milestones_on_time  smallint NOT NULL,
  PRIMARY KEY (student_id, roadmap)
);

-- Monthly 0–10 would-recommend pulse.
CREATE TABLE pulse (
  month        date NOT NULL,
  student_id   text REFERENCES students,
  respondent   text CHECK (respondent IN ('Alcovian', 'Parent')),
  score        smallint CHECK (score BETWEEN 0 AND 10),
  PRIMARY KEY (month, student_id, respondent)
);

-- Advisor inputs that keep the automations accurate.
CREATE TABLE score_targets (
  student_id        text REFERENCES students,
  subject           text,
  exam_type         text CHECK (exam_type IN ('Formative', 'Unit test', 'Mid-term', 'Final')),
  target_pct        smallint NOT NULL,
  set_on            date NOT NULL,
  parent_signed_on  date,
  PRIMARY KEY (student_id, subject, exam_type)
);

-- Inputs the advisor owes each week (timetable published, notes logged, targets reviewed).
CREATE TABLE advisor_input_log (
  week_start   date NOT NULL,
  student_id   text REFERENCES students,
  input        text NOT NULL,                     -- 'Timetable' | 'Call notes' | 'Exam score entry'
  due_on       date NOT NULL,
  done_on      date,
  PRIMARY KEY (week_start, student_id, input)
);

-- 2-week catch-up sprints triggered by pace gap (n8n/syllabus_escalation.json).
CREATE TABLE sprints (
  sprint_id    bigserial PRIMARY KEY,
  student_id   text REFERENCES students,
  subject      text NOT NULL,
  triggered_on date NOT NULL,
  pace_gap     numeric(5,1) NOT NULL,
  started_on   date,                              -- null = advisor has not started it
  closed_on    date,
  gap_after    numeric(5,1)
);
