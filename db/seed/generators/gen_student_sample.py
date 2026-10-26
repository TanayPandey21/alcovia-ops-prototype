import json, random, datetime as dt, math
random.seed(11)
D=dt.date; TODAY=D(2026,10,25); START=D(2026,7,27)  # Monday
days=[START+dt.timedelta(i) for i in range((TODAY-START).days+1)]
iso=lambda d:d.isoformat()
advisors=["Riya","Kabir","Meher"]
segs=["Focus regular"]*5+["Realm player"]*8+["Was dormant"]*7
random.shuffle(segs)
wear=random.sample(range(20),9)
students=[]
for i in range(20):
  students.append(dict(student=f"Alcovian {i+1:02d}",grade=random.choice([9,10,11,12]),advisor=advisors[i%3],segment=segs[i],wearable=(["Apple Watch","Samsung Watch","WHOOP","Garmin"][i%4] if i in wear else "None"),ability=round(random.uniform(.55,1.0),2)))
subjects=["Biology","Chemistry","Economics","English","History","Math"]
daily=[];quiz=[]
n=len(days)
for d_i,d in enumerate(days):
  t=d_i/(n-1)
  quiz.append(dict(date=iso(d),quiz_sent=0 if random.random()<0.03 else 1,topic=random.choice(["Sports","History","Logical reasoning","Brand logos","Science","Current affairs","Geography"])))
for s in students:
  seg=s["segment"];ab=s["ability"]
  for d_i,d in enumerate(days):
    t=d_i/(n-1)
    if seg=="Focus regular": p_act=.75+.15*t; base=8+40*t
    elif seg=="Realm player": p_act=.55+.3*t; base=3+26*t
    else: p_act=(.08 if t<.45 else .25+.5*(t-.45)/.55); base=2+18*max(0,t-.45)/.55
    active=random.random()<p_act
    weekend=d.weekday()>=5
    focus=0;app=0
    if active:
      focus=max(0,int(random.gauss(base*.75,base*.25))) if random.random()<.85 else 0
      app=focus+random.randint(2,8)
    qt=1 if (active and quiz[d_i]["quiz_sent"] and random.random()<.55+.35*t*(1 if seg!="Was dormant" else .7)) else 0
    qs=round(min(10,max(1,random.gauss(5.5+3*ab,1.5)))) if qt else None
    tp=0 if weekend else random.randint(2,5)
    td=sum(1 for _ in range(tp) if random.random()<(.45+.35*ab)*(1 if active else .5))
    tot=min(td,sum(1 for _ in range(td) if random.random()<.8))
    est=tp*30; act=round(est*random.uniform(.7,1.6)) if tp else 0
    hw=s["wearable"]!="None"
    daily.append(dict(date=iso(d),student=s["student"],active=1 if active else 0,app_min=app,focus_min=focus,quiz_taken=qt,quiz_score=qs,tasks_planned=tp,tasks_done=td,tasks_on_time=tot,est_min=est if td else 0,actual_min=act if td else 0,slots_planned=0 if weekend else 2,slots_done=(0 if weekend else min(2,int(focus>=20)+int(focus>=45))),sleep_h=round(random.gauss(7.4,.7),1) if hw else None,active_min=int(max(5,random.gauss(48,18))) if hw else None))
# sessions
sessions=[]
def add(date,typ,level,who,p_held,rating_mu,skill=False):
  held=1 if random.random()<p_held else 0
  for s in who:
    att=1 if held and random.random()<(.93 if s["segment"]!="Was dormant" or date>D(2026,9,15) else .6) else 0
    r=None
    if att and random.random()<.8: r=int(min(5,max(1,round(random.gauss(rating_mu,.7)))))
    sk=round(min(5,max(1,random.gauss(2.9+1.3*s["ability"],.4))),1) if (skill and att) else None
    sessions.append(dict(date=iso(date),activity=typ,level=level,student=s["student"],planned=1,held=held,attended=att,rating=r,skill_score=sk))
mon=START
while mon<=TODAY:
  for s in students:
    add(mon+dt.timedelta(1),"Academic session 1","Week",[s],.95,4.2)
    if mon+dt.timedelta(4)<=TODAY: add(mon+dt.timedelta(4),"Academic session 2","Week",[s],.9,4.1)
  mon+=dt.timedelta(7)
for m in [D(2026,8,1),D(2026,9,1),D(2026,10,1)]:
  for typ,off,mu,sk,ph in [("Workshop 1 (career)",8,4.5,True,1),("Workshop 2 (career)",22,4.4,True,1),("Pod session",15,4.3,False,.95),("Peer session",12,4.0,False,.85),("Mentor call",18,4.6,False,.9),("Personal branding shoot",25,4.1,False,.8)]:
    dd=m+dt.timedelta(off)
    if dd>TODAY: continue
    if typ.startswith("Workshop") or typ.startswith("Pod"): add(dd,typ,"Month",students,ph,mu,sk)
    else:
      for s in students: add(dd+dt.timedelta(random.randint(-3,3)),typ,"Month",[s],ph,mu)
add(D(2026,9,19),"Parent-child workshop","Quarter",students,1,4.7)
add(D(2026,8,29),"Out-of-city experience","Quarter",students,1,4.8,True)
for s in random.sample(students,6): add(D(2026,9,10)+dt.timedelta(random.randint(0,30)),"Podcast shoot","Quarter",[s],.85,4.6)
for s in random.sample(students,10): add(D(2026,9,5)+dt.timedelta(random.randint(0,40)),"Competition prep","Quarter",[s],.9,4.2)
sessions=[x for x in sessions if x["date"]<=iso(TODAY)]
sessions.sort(key=lambda r:r["date"])
# chapter snapshots weekly
chap=[]
wk=START+dt.timedelta(6)
weeks=[]
while wk<=TODAY+dt.timedelta(0):
  weeks.append(wk); wk+=dt.timedelta(7)
if weeks[-1]!=TODAY: weeks.append(TODAY)
qstart=D(2026,7,1); qlen=92
for s in students:
  for sub in subjects:
    aff=random.uniform(.6,1.15)
    lag=random.uniform(-12,6)*(1.4 if s["segment"]=="Was dormant" else 1)
    for w in weeks:
      if w<D(2026,10,1): base=0; el=(w-qstart).days/qlen
      else: base=25; el=(w-D(2026,10,1)).days/92
      expected=round(25+25*el,1) if w<D(2026,10,1) else round(25+25*el,1)
      # expected cumulative completion: Q3 25->50, Q4 50->75? keep: Q3 covers 25..50
      expected=round((25+25*el) if w<D(2026,10,1) else (50+25*el),1)
      t=(w-START).days/90
      comp=max(0,min(100,expected+lag*(1-.4*t*(s["segment"]!="Was dormant"))*aff+random.uniform(-2,2)))
      readiness=round(min(100,max(20,55+30*s["ability"]*aff-8+10*t+random.uniform(-4,4))),1)
      rigour=round(min(1,max(.3,.55+.3*s["ability"]+.1*t+random.uniform(-.08,.08))),2)
      chap.append(dict(week_end=iso(w),student=s["student"],subject=sub,completion_pct=round(comp,1),expected_pct=expected,readiness=readiness,rigour_adherence=rigour))
roadmaps=[]
for s in students:
  for rm in ["Academic","Personal","Career"]:
    due=random.randint(3,6); on=sum(1 for _ in range(due) if random.random()<.55+.35*s["ability"])
    roadmaps.append(dict(student=s["student"],roadmap=rm,current=0 if random.random()<.06 else 1,milestones_due=due,milestones_on_time=on))
pulse=[]
for m in ["2026-08","2026-09","2026-10"]:
  for s in students:
    for who in ["Alcovian","Parent"]:
      if random.random()<.75:
        pulse.append(dict(month=m,student=s["student"],respondent=who,score=int(min(10,max(3,round(random.gauss(8.4 if who=="Parent" else 8.0,1.4)))))))
for nm,o in [("students",students),("daily",daily),("quiz",quiz),("sessions",sessions),("chapters",chap),("roadmaps",roadmaps),("pulse",pulse)]:
  json.dump(o,open(f"sample_{nm}.json","w"),separators=(",",":"))
import statistics as st
for wk0 in range(0,13):
  a=START+dt.timedelta(7*wk0); b=a+dt.timedelta(6)
  rows=[r for r in daily if iso(a)<=r["date"]<=iso(b)]
  print(iso(a), round(sum(r["app_min"] for r in rows)/len(rows),1))
print(len(daily),len(sessions),len(chap))
