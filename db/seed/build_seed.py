"""Turn the sample JSON files into seed.sql for db/schema.sql.

Usage:  python3 db/seed/build_seed.py   ->  writes db/seed/seed.sql
The sample data is invented (20 made-up Alcovians, anchored on 25 Oct 2026).
"""
import json, random, datetime as dt, pathlib

HERE = pathlib.Path(__file__).parent
S = HERE / "sample"
load = lambda n: json.load(open(S / f"sample_{n}.json"))
random.seed(5)
out = ["SET search_path TO alcovia;", "BEGIN;"]

def lit(v):
    if v is None: return "NULL"
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return str(v)
    return "'" + str(v).replace("'", "''") + "'"

def insert(table, cols, rows, chunk=500):
    for i in range(0, len(rows), chunk):
        vals = ",\n".join("(" + ",".join(lit(r[c]) for c in cols) + ")" for r in rows[i:i + chunk])
        out.append(f"INSERT INTO {table} ({','.join(cols)}) VALUES\n{vals};")

# --- GTM -------------------------------------------------------
leads = load("leads")
for l in leads:
    l["created_on"] = l["created"]; l["closed_on"] = l["closed"]
insert("leads", ["lead_id", "created_on", "channel", "campaign", "ad_set", "asset", "stage_index", "outcome", "plan", "closed_on"], leads)
ev = []
for l in leads:
    d = dt.date.fromisoformat(l["created"])
    for s in range(l["stage_index"] + 1):
        if s: d += dt.timedelta(days=random.randint(1, 3))
        ev.append(dict(lead_id=l["lead_id"], stage_index=s, entered_on=d.isoformat()))
insert("lead_stage_events", ["lead_id", "stage_index", "entered_on"], ev)

pay = load("payments"); inv = load("invoices")
insert("invoices", ["invoice_id", "family", "item", "amount_inr", "issued_on", "status", "paid_on", "owner"],
       [dict(r, issued_on=r["issued"], amount_inr=r["amount"]) for r in inv])
ws = sorted({p["type"].replace("Workshop ", "") for p in pay if p["stream"] == "Workshop"})
insert("workshops", ["workshop_id", "held_on", "title"],
       [dict(workshop_id="WS-" + d, held_on=d, title="Career simulation workshop") for d in ws])
rows = []
for i, p in enumerate(pay):
    rows.append(dict(razorpay_payment_id=f"pay_{i:05d}", paid_on=p["date"], stream=p["stream"], plan=p["plan"],
                     payment_type="Workshop seat" if p["stream"] == "Workshop" else p["type"], amount_inr=p["amount"],
                     invoice_id=p["ref"] if p["ref"].startswith("INV-") else None,
                     workshop_id="WS-" + p["type"].replace("Workshop ", "") if p["stream"] == "Workshop" else None))
insert("payments", ["razorpay_payment_id", "paid_on", "stream", "plan", "payment_type", "amount_inr", "invoice_id", "workshop_id"], rows)
insert("trials", ["family", "trial_start", "trial_end", "advisor", "renewal_call"], load("renewals"))
insert("monthly_targets", ["month", "revenue_target", "signup_target", "cpql_target"],
       [dict(r, month=r["month"] + "-01") for r in load("targets")])
insert("ad_daily", ["day", "campaign_type", "campaign", "ad_set", "asset", "format", "landing_page", "spend_inr", "impressions",
                    "reach", "frequency_7d", "clicks", "lp_visits", "lp_submits", "lp_load_s"],
       [dict(r, day=r["date"], spend_inr=r["spend"]) for r in load("ads")])

# --- Students --------------------------------------------------
stu = load("students")
for s in stu:
    s["student_id"] = "S" + s["student"].split()[-1]; s["display_name"] = s["student"]; s["enrolled_on"] = "2026-04-01"
sid = {s["student"]: s["student_id"] for s in stu}
insert("students", ["student_id", "display_name", "grade", "advisor", "wearable", "enrolled_on"], stu)
daily = load("daily")
insert("student_daily", ["day", "student_id", "active", "app_min", "focus_min", "quiz_taken", "quiz_score", "tasks_planned",
                         "tasks_done", "tasks_on_time", "est_min", "actual_min", "slots_planned", "slots_done", "sleep_h", "active_min"],
       [dict(r, day=r["date"], student_id=sid[r["student"]], active=bool(r["active"]), quiz_taken=bool(r["quiz_taken"])) for r in daily])
insert("quiz_days", ["day", "sent", "topic"], [dict(r, day=r["date"], sent=bool(r["quiz_sent"])) for r in load("quiz")])
insert("activity_log", ["day", "activity", "level", "student_id", "planned", "held", "attended", "rating", "skill_score"],
       [dict(r, day=r["date"], student_id=sid[r["student"]], planned=True, held=bool(r["held"]), attended=bool(r["attended"])) for r in load("sessions")])
insert("chapter_snapshots", ["week_end", "student_id", "subject", "completion_pct", "expected_pct", "readiness", "rigour_adherence"],
       [dict(r, student_id=sid[r["student"]]) for r in load("chapters")])
insert("roadmaps", ["student_id", "roadmap", "is_current", "milestones_due", "milestones_on_time"],
       [dict(r, student_id=sid[r["student"]], is_current=bool(r["current"])) for r in load("roadmaps")])
insert("pulse", ["month", "student_id", "respondent", "score"],
       [dict(r, month=r["month"] + "-01", student_id=sid[r["student"]]) for r in load("pulse")])

# --- Advisor inputs (generated here) ----------------------------
subjects = ["Biology", "Chemistry", "Economics", "English", "History", "Math"]
tg = []
for s in stu:
    for sub in subjects:
        for ex in ["Unit test", "Mid-term"]:
            if random.random() < 0.9:
                tg.append(dict(student_id=s["student_id"], subject=sub, exam_type=ex, target_pct=random.randint(70, 92),
                               set_on="2026-08-05", parent_signed_on="2026-08-1" + str(random.randint(0, 9)) if random.random() < 0.8 else None))
insert("score_targets", ["student_id", "subject", "exam_type", "target_pct", "set_on", "parent_signed_on"], tg)
log = []
wk = dt.date(2026, 7, 27)
while wk <= dt.date(2026, 10, 19):
    for s in stu:
        for inp, due in [("Timetable", -1), ("Call notes", 2), ("Exam score entry", 6)]:
            d = wk + dt.timedelta(days=due)
            late = random.random()
            if late < 0.08: done = None                                   # never done
            elif late < 0.30: done = d + dt.timedelta(days=random.choice([1, 2, 3]))  # late
            else: done = d - dt.timedelta(days=random.randint(0, 1))     # on time
            log.append(dict(week_start=wk.isoformat(), student_id=s["student_id"], input=inp, due_on=d.isoformat(), done_on=done.isoformat() if done else None))
    wk += dt.timedelta(days=7)
insert("advisor_input_log", ["week_start", "student_id", "input", "due_on", "done_on"], log)
sp = []
for r in load("chapters"):
    gap = r["completion_pct"] - r["expected_pct"]
    if gap < -10 and r["week_end"] in ("2026-08-30", "2026-09-27", "2026-10-25") and random.random() < 0.6:
        st = dt.date.fromisoformat(r["week_end"]) + dt.timedelta(days=random.randint(1, 4))
        started = st if random.random() < 0.75 and st <= dt.date(2026, 10, 25) else None
        sp.append(dict(student_id=sid[r["student"]], subject=r["subject"], triggered_on=r["week_end"], pace_gap=round(gap, 1),
                       started_on=started.isoformat() if started else None,
                       closed_on=(st + dt.timedelta(days=14)).isoformat() if started and st + dt.timedelta(days=14) <= dt.date(2026, 10, 25) else None,
                       gap_after=round(gap + random.uniform(4, 12), 1) if started and st + dt.timedelta(days=14) <= dt.date(2026, 10, 25) else None))
insert("sprints", ["student_id", "subject", "triggered_on", "pace_gap", "started_on", "closed_on", "gap_after"], sp)

out.append("COMMIT;")
(HERE / "seed.sql").write_text("\n".join(out))
print("wrote", HERE / "seed.sql")
