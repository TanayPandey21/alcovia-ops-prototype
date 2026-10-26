"""Generates the importable n8n workflow JSON files in n8n/.
Credentials are referenced by name; create them once in n8n (Postgres 'Alcovia DB', 'Meta Ads token',
'ClickUp API', 'Razorpay webhook secret', 'WhatsApp Cloud API', 'Alcovia app API', 'Smallest.ai API', 'Google Calendar')."""
import json, pathlib, uuid
OUT = pathlib.Path(__file__).resolve().parent.parent / "n8n"
OUT.mkdir(exist_ok=True)

def node(name, typ, params, pos, ver=1, creds=None):
    n = {"parameters": params, "id": str(uuid.uuid5(uuid.NAMESPACE_URL, name + typ)), "name": name,
         "type": typ, "typeVersion": ver, "position": pos}
    if creds: n["credentials"] = creds
    return n
PG = {"postgres": {"id": "1", "name": "Alcovia DB"}}
def sched(name, rule, pos=[0, 300]): return node(name, "n8n-nodes-base.scheduleTrigger", {"rule": {"interval": [rule]}}, pos, 1.2)
def pg(name, sql, pos): return node(name, "n8n-nodes-base.postgres", {"operation": "executeQuery", "query": sql, "options": {}}, pos, 2.5, PG)
def code(name, js, pos): return node(name, "n8n-nodes-base.code", {"jsCode": js}, pos, 2)
def http(name, method, url, pos, body=None, headers=None, cred_name=None):
    p = {"method": method, "url": url, "options": {}}
    if body is not None: p.update({"sendBody": True, "specifyBody": "json", "jsonBody": body})
    if headers: p.update({"sendHeaders": True, "headerParameters": {"parameters": [{"name": k, "value": v} for k, v in headers.items()]}})
    if cred_name: p.update({"authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth"})
    return node(name, "n8n-nodes-base.httpRequest", p, pos, 4.2,
                {"httpHeaderAuth": {"id": "2", "name": cred_name}} if cred_name else None)
def ifn(name, left, op, right, pos):
    return node(name, "n8n-nodes-base.if", {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"},
        "conditions": [{"leftValue": left, "rightValue": right, "operator": {"type": "string" if isinstance(right, str) else "number", "operation": op}}],
        "combinator": "and"}, "options": {}}, pos, 2)
def wf(fname, title, nodes, edges, note):
    conns = {}
    for a, b, *rest in edges:
        out = rest[0] if rest else 0
        c = conns.setdefault(a, {"main": []})
        while len(c["main"]) <= out: c["main"].append([])
        c["main"][out].append({"node": b, "type": "main", "index": 0})
    nodes = [node("About this workflow", "n8n-nodes-base.stickyNote", {"content": f"## {title}\n{note}", "width": 420, "height": 220}, [-40, 40], 1)] + nodes
    json.dump({"name": title, "nodes": nodes, "connections": conns, "active": False,
               "settings": {"executionOrder": "v1", "timezone": "Asia/Kolkata"}, "tags": [{"name": "alcovia"}]},
              open(OUT / fname, "w"), indent=2)

# 1 Meta Ads hourly sync -------------------------------------------------------
wf("01_meta_ads_sync.json", "Meta Ads → ad_daily (hourly)", [
    sched("Every hour", {"field": "hours", "hoursInterval": 1}),
    http("Get ad insights", "GET",
         "=https://graph.facebook.com/v21.0/act_{{$env.META_AD_ACCOUNT_ID}}/insights?level=ad&time_increment=1&date_preset=last_3d&fields=campaign_name,adset_name,ad_name,spend,impressions,reach,frequency,clicks&limit=500",
         [240, 300], cred_name="Meta Ads token"),
    code("Map to ad_daily rows", """// Campaign names follow the naming rule: 'PRG ...' = program, 'WS ...' = workshop.
const rows = $input.first().json.data || [];
return rows.map(r => ({ json: {
  day: r.date_start,
  campaign_type: r.campaign_name.startsWith('WS') ? 'Workshop' : 'Program',
  campaign: r.campaign_name, ad_set: r.adset_name, asset: r.ad_name,
  spend_inr: Math.round(Number(r.spend)), impressions: Number(r.impressions), reach: Number(r.reach),
  frequency_7d: Number(r.frequency), clicks: Number(r.clicks)
}}));""", [480, 300]),
    pg("Upsert ad_daily", """INSERT INTO alcovia.ad_daily (day, campaign_type, campaign, ad_set, asset, spend_inr, impressions, reach, frequency_7d, clicks, lp_visits, lp_submits)
VALUES ('{{$json.day}}', '{{$json.campaign_type}}', '{{$json.campaign}}', '{{$json.ad_set}}', '{{$json.asset}}', {{$json.spend_inr}}, {{$json.impressions}}, {{$json.reach}}, {{$json.frequency_7d}}, {{$json.clicks}}, 0, 0)
ON CONFLICT (day, asset) DO UPDATE SET spend_inr = EXCLUDED.spend_inr, impressions = EXCLUDED.impressions,
  reach = EXCLUDED.reach, frequency_7d = EXCLUDED.frequency_7d, clicks = EXCLUDED.clicks;""", [720, 300]),
], [("Every hour", "Get ad insights"), ("Get ad insights", "Map to ad_daily rows"), ("Map to ad_daily rows", "Upsert ad_daily")],
"Pulls the last 3 days of ad-level insights every hour (Meta revises recent days) and upserts them. Landing-page visits, submits and load time are filled by the daily GA4 + PageSpeed step in workflow 04.")

# 2 Razorpay webhook -------------------------------------------------------------
wf("02_razorpay_webhook.json", "Razorpay → payments & invoices (real time)", [
    node("Razorpay webhook", "n8n-nodes-base.webhook", {"httpMethod": "POST", "path": "razorpay", "options": {"rawBody": True}}, [0, 300], 2),
    code("Verify signature + map", """// Reject anything not signed with our Razorpay webhook secret.
const crypto = require('crypto');
const item = $input.first();
const raw = item.binary?.data ? Buffer.from(item.binary.data.data, 'base64').toString() : JSON.stringify(item.json.body);
const expected = crypto.createHmac('sha256', $env.RAZORPAY_WEBHOOK_SECRET).update(raw).digest('hex');
if (expected !== item.json.headers['x-razorpay-signature']) throw new Error('Bad Razorpay signature');
const body = item.json.body;
if (body.event !== 'payment.captured') return [];
const p = body.payload.payment.entity, notes = p.notes || {};
return [{ json: {
  razorpay_payment_id: p.id,
  paid_on: new Date(p.created_at * 1000).toISOString().slice(0, 10),
  stream: notes.workshop_id ? 'Workshop' : 'Program',
  plan: notes.plan || 'Workshop seat',                 // set on the payment link / invoice
  payment_type: notes.payment_type || 'Workshop seat',
  amount_inr: p.amount / 100,
  invoice_id: notes.invoice_id || null, workshop_id: notes.workshop_id || null
}}];""", [240, 300]),
    pg("Insert payment + mark invoice paid", """INSERT INTO alcovia.payments (razorpay_payment_id, paid_on, stream, plan, payment_type, amount_inr, invoice_id, workshop_id)
VALUES ('{{$json.razorpay_payment_id}}', '{{$json.paid_on}}', '{{$json.stream}}', '{{$json.plan}}', '{{$json.payment_type}}', {{$json.amount_inr}},
        NULLIF('{{$json.invoice_id}}', 'null'), NULLIF('{{$json.workshop_id}}', 'null'))
ON CONFLICT (razorpay_payment_id) DO NOTHING;
UPDATE alcovia.invoices SET status = 'Paid', paid_on = '{{$json.paid_on}}' WHERE invoice_id = NULLIF('{{$json.invoice_id}}', 'null');""", [480, 300]),
], [("Razorpay webhook", "Verify signature + map"), ("Verify signature + map", "Insert payment + mark invoice paid")],
"Every captured payment lands in Postgres within seconds. Payment links and invoices carry notes {plan, payment_type, invoice_id, workshop_id} so each rupee is attributed to trial, full program, upgrade or a specific workshop.")

# 3 ClickUp lead sync + no-show rebooking ------------------------------------------
wf("03_clickup_lead_sync.json", "ClickUp leads → leads & funnel (on status change)", [
    node("ClickUp status changed", "n8n-nodes-base.clickUpTrigger", {"team": "={{$env.CLICKUP_TEAM_ID}}", "events": ["taskStatusUpdated", "taskCreated"], "filters": {"listId": "={{$env.CLICKUP_LEADS_LIST_ID}}"}}, [0, 300], 1,
         {"clickUpApi": {"id": "3", "name": "ClickUp API"}}),
    http("Get task", "GET", "=https://api.clickup.com/api/v2/task/{{$json.task_id}}?include_subtasks=false", [240, 300], cred_name="ClickUp API"),
    code("Map task to lead", """const t = $input.first().json;
const field = (n) => (t.custom_fields.find(f => f.name === n) || {}).value ?? null;
const stages = ['Lead','Qualified','Discovery call set','Discovery call attended','Ambition interview','Architect session','Signed up'];
const status = t.status.status;                        // ClickUp statuses mirror the funnel stages + 'Lost'
const idx = stages.indexOf(status);
return [{ json: {
  lead_id: t.id, created_on: new Date(Number(t.date_created)).toISOString().slice(0,10),
  channel: field('utm_source') ? 'Meta' : (field('Referral') ? 'Referral' : 'Organic'),
  campaign: field('utm_campaign') || '(organic)', ad_set: field('utm_term') || '(none)', asset: field('utm_content') || '(none)',
  stage_index: idx >= 0 ? idx : Number(field('Furthest stage') || 0),
  outcome: status === 'Signed up' ? 'Signed up' : status === 'Lost' ? 'Lost' : 'Open',
  lost_reason: field('Lost reason'), plan: field('Plan'),
  closed_on: ['Signed up','Lost'].includes(status) ? new Date().toISOString().slice(0,10) : null,
  no_show: status === 'Discovery no-show', phone: field('Parent phone')
}}];""", [480, 300]),
    pg("Upsert lead + stage event", """INSERT INTO alcovia.leads (lead_id, created_on, channel, campaign, ad_set, asset, stage_index, outcome, lost_reason, plan, closed_on)
VALUES ('{{$json.lead_id}}', '{{$json.created_on}}', '{{$json.channel}}', '{{$json.campaign}}', '{{$json.ad_set}}', '{{$json.asset}}', {{$json.stage_index}},
        '{{$json.outcome}}', NULLIF('{{$json.lost_reason}}','null'), NULLIF('{{$json.plan}}','null'), NULLIF('{{$json.closed_on}}','null')::date)
ON CONFLICT (lead_id) DO UPDATE SET stage_index = GREATEST(alcovia.leads.stage_index, EXCLUDED.stage_index),
  outcome = EXCLUDED.outcome, lost_reason = EXCLUDED.lost_reason, plan = EXCLUDED.plan, closed_on = EXCLUDED.closed_on;
INSERT INTO alcovia.lead_stage_events VALUES ('{{$json.lead_id}}', {{$json.stage_index}}, CURRENT_DATE) ON CONFLICT DO NOTHING;""", [720, 300]),
    ifn("Discovery no-show?", "={{$json.no_show}}", "equals", "true", [960, 300]),
    http("Smallest.ai rebooking call", "POST", "https://api.smallest.ai/v1/calls", [1200, 220],
         body='={"to": "{{$json.phone}}", "agent_id": "{{$env.SMALLEST_REBOOK_AGENT}}", "metadata": {"lead_id": "{{$json.lead_id}}"}}', cred_name="Smallest.ai API"),
], [("ClickUp status changed", "Get task"), ("Get task", "Map task to lead"), ("Map task to lead", "Upsert lead + stage event"),
    ("Upsert lead + stage event", "Discovery no-show?"), ("Discovery no-show?", "Smallest.ai rebooking call", 0)],
"Keeps the funnel live: every ClickUp status change updates the lead and logs the stage with its date. A discovery-call no-show triggers a Smallest.ai rebooking call within minutes.")

# 4 Daily GTM alerts --------------------------------------------------------------------
wf("04_gtm_daily_alerts.json", "GTM daily alerts: unpaid invoices, renewals, ad sets (09:00)", [
    sched("Daily 09:00", {"field": "cronExpression", "expression": "0 9 * * *"}),
    pg("Unpaid on day 7 or 15", """SELECT invoice_id, family, amount_inr, owner, CURRENT_DATE - issued_on AS days_open
FROM alcovia.invoices WHERE status = 'Unpaid' AND CURRENT_DATE - issued_on IN (7, 15);""", [240, 160]),
    pg("Trials ending in 21 days, no call booked", """SELECT family, trial_end, advisor FROM alcovia.trials
WHERE trial_end = CURRENT_DATE + 21 AND renewal_call = 'Not booked';""", [240, 320]),
    pg("Ad sets needing action (see metrics/gtm/09)", """-- view defined in db/views.sql (= metrics/gtm/09 over the last 7 days)
SELECT ad_set_key, action FROM alcovia.v_adset_actions_7d WHERE action IN ('Kill','Refresh','Fix LP','Scale');""", [240, 480]),
    code("Build messages", """const msgs = [];
for (const r of $('Unpaid on day 7 or 15').all()) msgs.push(`${r.json.owner}: invoice ${r.json.invoice_id} (${r.json.family}, Rs ${r.json.amount_inr}) unpaid for ${r.json.days_open} days.`);
for (const r of $('Trials ending in 21 days, no call booked').all()) msgs.push(`${r.json.advisor}: ${r.json.family}'s trial ends ${r.json.trial_end}; no renewal call booked.`);
for (const r of $('Ad sets needing action (see metrics/gtm/09)').all()) msgs.push(`Marketing: ${r.json.action} -> ${r.json.ad_set_key}`);
return msgs.length ? [{ json: { text: msgs.join('\\n') } }] : [];""", [520, 320]),
    http("Post to ClickUp chat", "POST", "=https://api.clickup.com/api/v3/workspaces/{{$env.CLICKUP_TEAM_ID}}/chat/channels/{{$env.CLICKUP_GTM_CHANNEL}}/messages",
         [760, 320], body='={"content": {{JSON.stringify($json.text)}}}', cred_name="ClickUp API"),
], [("Daily 09:00", "Unpaid on day 7 or 15"), ("Daily 09:00", "Trials ending in 21 days, no call booked"), ("Daily 09:00", "Ad sets needing action (see metrics/gtm/09)"),
    ("Ad sets needing action (see metrics/gtm/09)", "Build messages"), ("Build messages", "Post to ClickUp chat")],
"One morning digest in the GTM ClickUp channel: invoices unpaid at day 7 and 15, trials 21 days from ending with no renewal call, and every ad set whose rule says scale / refresh / fix / kill.")

# 5 Session rating push ---------------------------------------------------------------------
wf("05_session_rating_push.json", "Sessions → held/attended + 1-tap rating push (every 10 min)", [
    sched("Every 10 minutes", {"field": "minutes", "minutesInterval": 10}),
    node("Events ended in last 10 min", "n8n-nodes-base.googleCalendar",
         {"operation": "getAll", "calendar": {"__rl": True, "mode": "id", "value": "={{$env.ALCOVIA_SESSIONS_CALENDAR}}"},
          "timeMin": "={{$now.minus({minutes: 20}).toISO()}}", "timeMax": "={{$now.minus({minutes: 10}).toISO()}}", "options": {"singleEvents": True}},
         [240, 300], 1.2, {"googleCalendarOAuth2Api": {"id": "4", "name": "Google Calendar"}}),
    code("One row per invited Alcovian", """// Event titles follow '<Activity> | <level>'; attendees carry student emails mapped in the app.
const out = [];
for (const ev of $input.all().map(i => i.json)) {
  const [activity, level] = ev.summary.split('|').map(s => s.trim());
  for (const a of (ev.attendees || []).filter(a => a.email.endsWith('@students.alcovia.life'))) {
    out.push({ json: { day: ev.start.dateTime.slice(0,10), activity, level: level || 'Week', email: a.email,
      held: ev.status !== 'cancelled', attended: a.responseStatus === 'accepted' } });   // Meet attendance report overrides when available
  }
}
return out;""", [480, 300]),
    pg("Log activity", """INSERT INTO alcovia.activity_log (day, activity, level, student_id, held, attended)
SELECT '{{$json.day}}', '{{$json.activity}}', '{{$json.level}}', student_id, {{$json.held}}, {{$json.attended}}
FROM alcovia.students WHERE student_id = split_part('{{$json.email}}', '@', 1)   -- student email = <student_id>@students.alcovia.life
RETURNING activity_id, student_id;""", [720, 300]),
    http("Push 1-tap rating", "POST", "={{$env.ALCOVIA_APP_API}}/v1/push/rating", [960, 300],
         body='={"student_id": "{{$json.student_id}}", "activity_id": {{$json.activity_id}}, "question": "How useful was this session?", "scale": 5}',
         cred_name="Alcovia app API"),
], [("Every 10 minutes", "Events ended in last 10 min"), ("Events ended in last 10 min", "One row per invited Alcovian"),
    ("One row per invited Alcovian", "Log activity"), ("Log activity", "Push 1-tap rating")],
"Captures Conducted and Liked with no typing: each session that ended is logged as held / attended from Google Calendar, then the app pushes a 1-tap rating 10 minutes after; the app writes the answer back to activity_log.rating.")

# 6 Syllabus escalation ---------------------------------------------------------------------
wf("06_syllabus_escalation.json", "Syllabus pace escalations (Mondays 07:00)", [
    sched("Mondays 07:00", {"field": "cronExpression", "expression": "0 7 * * 1"}),
    pg("Run metrics/student/07_escalations.sql", "SELECT * FROM alcovia.v_escalations;  -- db/views.sql", [240, 300]),
    node("Route by action", "n8n-nodes-base.switch", {"rules": {"values": [
        {"conditions": {"conditions": [{"leftValue": "={{$json.action}}", "rightValue": "Nudge student + flag advisor", "operator": {"type": "string", "operation": "equals"}}]}, "renameOutput": True, "outputKey": "nudge"},
        {"conditions": {"conditions": [{"leftValue": "={{$json.action}}", "rightValue": "Message parent + start 2-week sprint", "operator": {"type": "string", "operation": "equals"}}]}, "renameOutput": True, "outputKey": "sprint"},
        {"conditions": {"conditions": [{"leftValue": "={{$json.action}}", "rightValue": "Trigger tutor support", "operator": {"type": "string", "operation": "equals"}}]}, "renameOutput": True, "outputKey": "tutor"}]}, "options": {}},
        [480, 300], 3),
    http("In-app nudge", "POST", "={{$env.ALCOVIA_APP_API}}/v1/push/nudge", [760, 140],
         body='={"student_id": "{{$json.student_id}}", "text": "{{$json.subject}} is {{Math.abs($json.pace_gap)}} pts behind plan. 2 focus sessions this week closes it."}', cred_name="Alcovia app API"),
    http("WhatsApp parent", "POST", "=https://graph.facebook.com/v21.0/{{$env.WA_PHONE_ID}}/messages", [760, 300],
         body='={"messaging_product": "whatsapp", "to": "{{$json.parent_phone}}", "type": "template", "template": {"name": "syllabus_sprint", "language": {"code": "en"}}}', cred_name="WhatsApp Cloud API"),
    pg("Open sprint", "INSERT INTO alcovia.sprints (student_id, subject, triggered_on, pace_gap) VALUES ('{{$json.student_id}}', '{{$json.subject}}', CURRENT_DATE, {{$json.pace_gap}});", [1000, 300]),
    http("ClickUp task: tutor support", "POST", "=https://api.clickup.com/api/v2/list/{{$env.CLICKUP_ADVISOR_LIST_ID}}/task", [760, 460],
         body='={"name": "Tutor support: {{$json.display_name}} – {{$json.subject}}", "assignees": [], "description": "Pace gap {{$json.pace_gap}} pts for two months. Trigger pre-agreed tutor."}', cred_name="ClickUp API"),
], [("Mondays 07:00", "Run metrics/student/07_escalations.sql"), ("Run metrics/student/07_escalations.sql", "Route by action"),
    ("Route by action", "In-app nudge", 0), ("Route by action", "WhatsApp parent", 1), ("WhatsApp parent", "Open sprint"), ("Route by action", "ClickUp task: tutor support", 2)],
"Applies the escalation ladder every Monday: -10 pts = student nudge + advisor flag; -20 pts = parent WhatsApp + 2-week sprint logged; -20 pts for two months = ClickUp task to trigger tutor support.")

# 7 Nightly rollup + missing inputs ----------------------------------------------------------
wf("07_nightly_student_rollup.json", "Nightly student rollup + advisor missing-inputs digest (01:00)", [
    sched("Daily 01:00", {"field": "cronExpression", "expression": "0 1 * * *"}),
    pg("Roll up yesterday (db/rollups/student_daily.sql)", "WITH e AS (\n  SELECT student_id, session_id, event_name, feature, occurred_at, props,\n         LEAD(occurred_at) OVER (PARTITION BY session_id ORDER BY occurred_at) AS next_at\n  FROM alcovia.app_events\n  WHERE occurred_at >= (CURRENT_DATE - 1) AND occurred_at < (CURRENT_DATE - 1) + 1\n),\nmins AS (\n  SELECT student_id,\n         SUM(CASE WHEN next_at IS NULL THEN 0            -- last event of a session adds nothing\n                  WHEN event_name = 'focus_started' THEN EXTRACT(EPOCH FROM (next_at - occurred_at)) / 60\n                  ELSE LEAST(EXTRACT(EPOCH FROM (next_at - occurred_at)) / 60, 2) END)\n           FILTER (WHERE feature IN ('home', 'focus', 'study', 'tasks', 'quiz', 'planner', 'realm')) AS app_min,\n         SUM((props->>'minutes')::numeric) FILTER (WHERE event_name = 'focus_completed')          AS focus_min,\n         BOOL_OR(event_name IN ('focus_completed', 'chapter_stage_completed', 'task_completed', 'quiz_answered')) AS active,\n         BOOL_OR(event_name = 'quiz_answered')                                                       AS quiz_taken,\n         MAX((props->>'score')::int) FILTER (WHERE event_name = 'quiz_answered')                    AS quiz_score,\n         COUNT(*) FILTER (WHERE event_name = 'task_completed')                                       AS tasks_done,\n         COUNT(*) FILTER (WHERE event_name = 'task_completed' AND (props->>'on_time')::boolean)      AS tasks_on_time,\n         SUM((props->>'est_min')::int) FILTER (WHERE event_name = 'task_completed')                  AS est_min,\n         SUM((props->>'actual_min')::int) FILTER (WHERE event_name = 'task_completed')               AS actual_min\n  FROM e GROUP BY student_id\n)\nINSERT INTO alcovia.student_daily (day, student_id, active, app_min, focus_min, quiz_taken, quiz_score, tasks_done, tasks_on_time, est_min, actual_min)\nSELECT (CURRENT_DATE - 1), s.student_id, COALESCE(m.active, false), COALESCE(m.app_min, 0), COALESCE(m.focus_min, 0),\n       COALESCE(m.quiz_taken, false), m.quiz_score, COALESCE(m.tasks_done, 0), COALESCE(m.tasks_on_time, 0),\n       COALESCE(m.est_min, 0), COALESCE(m.actual_min, 0)\nFROM alcovia.students s LEFT JOIN mins m USING (student_id)\nWHERE s.status = 'Active'\nON CONFLICT (day, student_id) DO UPDATE SET\n  active = EXCLUDED.active, app_min = EXCLUDED.app_min, focus_min = EXCLUDED.focus_min,\n  quiz_taken = EXCLUDED.quiz_taken, quiz_score = EXCLUDED.quiz_score, tasks_done = EXCLUDED.tasks_done,\n  tasks_on_time = EXCLUDED.tasks_on_time, est_min = EXCLUDED.est_min, actual_min = EXCLUDED.actual_min;\n-- tasks_planned, slots_* come from the timetable sync; sleep_h / active_min from the wearable sync.\n", [240, 300]),
    pg("Missing advisor inputs", """SELECT s.advisor, string_agg(s.display_name || ': ' || l.input, ', ') AS missing
FROM alcovia.advisor_input_log l JOIN alcovia.students s USING (student_id)
WHERE l.done_on IS NULL AND l.due_on < CURRENT_DATE GROUP BY s.advisor;""", [480, 300]),
    http("Post digest to each advisor", "POST", "=https://api.clickup.com/api/v3/workspaces/{{$env.CLICKUP_TEAM_ID}}/chat/channels/{{$env.CLICKUP_ADVISORS_CHANNEL}}/messages",
         [720, 300], body='={"content": "{{$json.advisor}}, inputs still missing: {{$json.missing}}"}', cred_name="ClickUp API"),
], [("Daily 01:00", "Roll up yesterday (db/rollups/student_daily.sql)"), ("Roll up yesterday (db/rollups/student_daily.sql)", "Missing advisor inputs"),
    ("Missing advisor inputs", "Post digest to each advisor")],
"Turns yesterday's app events into student_daily (meaningful minutes, focus, quiz, tasks) and tells each advisor which inputs are overdue, so gaps are chased before the weekly review.")
print("wrote", sorted(p.name for p in OUT.glob("*.json")))
