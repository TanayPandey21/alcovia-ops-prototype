import json, random, datetime as dt
random.seed(7)
D=dt.date
TODAY=D(2026,10,25); START=D(2026,4,1)
days=[START+dt.timedelta(i) for i in range((TODAY-START).days+1)]
iso=lambda d:d.isoformat()
# assets: (campaign_type,campaign,ad_set,asset,format,lp, base_spend, ctr0, ctr_end, freq0,freq_end, lp_conv, qual, lp_load, lead_quality)
A=[
 ("Program","PRG Career Clarity","NCR parents 38-50","Day-in-the-life reel","Video","lp/career-clarity",2600,0.019,0.018,1.6,2.1,0.030,0.40,1.8,1.25),
 ("Program","PRG Career Clarity","Lookalike 3%","Roadmap carousel","Carousel","lp/career-clarity",1800,0.012,0.011,1.5,2.3,0.026,0.31,1.8,1.0),
 ("Program","PRG Parent Anxiety","NCR parents 38-50","Board-exam stress reel","Video","lp/parent-guide",2200,0.021,0.009,1.7,3.7,0.026,0.33,2.2,0.95),
 ("Program","PRG Parent Anxiety","Interest: education","Checklist static","Static","lp/parent-guide",1400,0.006,0.005,1.4,2.6,0.02,0.12,2.2,0.55),
 ("Program","PRG Topper Stories","Lookalike 3%","Alcovian story video","Video","lp/stories",2000,0.017,0.016,1.5,2.2,0.010,0.36,4.3,1.0),
 ("Program","PRG Topper Stories","Mumbai + Bengaluru parents","Podcast clip","Video","lp/stories",1200,0.013,0.012,1.3,1.9,0.011,0.30,4.3,0.9),
 ("Workshop","WS Day in the Life","NCR parents 38-50","Simulation pilot reel","Video","lp/workshop",1500,0.020,0.019,1.5,2.0,0.09,0,1.6,1.0),
 ("Workshop","WS Day in the Life","Teens 14-17 interests","Career quiz static","Static","lp/workshop",900,0.014,0.007,1.6,3.3,0.06,0,1.6,1.0),
 ("Workshop","WS Simulation Teaser","Lookalike workshop buyers","Teaser carousel","Carousel","lp/workshop",1000,0.016,0.015,1.4,2.4,0.08,0,1.6,1.0),
]
ads=[]; leadseeds=[]
n=len(days)
for ai,a in enumerate(A):
  ctype,camp,adset,asset,fmt,lp,sp,c0,c1,f0,f1,lpc,qual,load,lq=a
  for i,d in enumerate(days):
    t=i/(n-1)
    spend=round(sp*random.uniform(.8,1.2)*(1+0.4*t))
    cpm=random.uniform(160,230)
    imp=int(spend/cpm*1000)
    freq=round(f0+(f1-f0)*(t**2)+random.uniform(-.1,.1),2)
    reach=int(imp/max(freq,1.05))
    ctr=(c0+(c1-c0)*(t**2))*random.uniform(.85,1.15)
    clicks=int(imp*ctr)
    visits=int(clicks*random.uniform(.78,.9))
    ld=round(load*random.uniform(.9,1.12),2)
    subm=sum(1 for _ in range(visits) if random.random()<lpc)
    ads.append(dict(date=iso(d),campaign_type=ctype,campaign=camp,ad_set=adset,asset=asset,format=fmt,landing_page=lp,spend=spend,impressions=imp,reach=reach,frequency_7d=freq,clicks=clicks,lp_visits=visits,lp_submits=subm,lp_load_s=ld))
    if ctype=="Program":
      for _ in range(subm): leadseeds.append((d,"Meta",camp,adset,asset,qual,lq))
    else:
      leadseeds  # workshop registrations handled below
# organic leads
for d in days:
  for _ in range(random.choice([1,2,2,2,3])):
    leadseeds.append((d,random.choice(["Organic","Organic","Referral"]),"(organic)","(none)","(none)",0.55,1.3))
# funnel progression
stages=["Lead","Qualified","Discovery call set","Discovery call attended","Ambition interview","Architect session","Signed up"]
leads=[]; won=[]
for k,(d,ch,camp,adset,asset,qual,lq) in enumerate(sorted(leadseeds)):
  st=0; p=[qual,0.60,0.70,0.75,0.70,min(0.9,0.35*lq)]
  for pr in p:
    if random.random()<pr: st+=1
    else: break
  days_in=0
  for s in range(st): days_in+=random.randint(1,4) if s else random.randint(0,2)
  close=d+dt.timedelta(days_in+random.randint(1,4))
  if st==6: outcome="Signed up"
  elif close>TODAY and st>=1: outcome="Open"
  else: outcome="Lost"
  if outcome=="Open": close=None
  lid=f"L{10000+k}"
  plan=None
  if outcome=="Signed up":
    if close>TODAY: outcome="Open"; close=None
    else:
      plan="3-month trial" if random.random()<0.66 else "Full program"
      won.append((lid,close,plan))
  leads.append(dict(lead_id=lid,created=iso(d),channel=ch,campaign=camp,ad_set=adset,asset=asset,stage_reached=stages[st],stage_index=st,qualified=st>=1,outcome=outcome,plan=plan,closed=iso(close) if close else None))
# invoices & payments
PR={"3-month trial":45000,"Full program":180000,"Trial upgrade":135000}
advisors=["Riya","Kabir","Meher"]
invoices=[];payments=[];renewals=[]
ic=5000
for lid,cl,plan in won:
  ic+=1; fam=f"Family {lid[1:]}"
  unpaid = (TODAY-cl).days<=24 and random.random()<0.22
  paid_on=None if unpaid else cl+dt.timedelta(random.randint(0,3))
  if paid_on and paid_on>TODAY: paid_on=None
  invoices.append(dict(invoice_id=f"INV-{ic}",family=fam,item=plan,amount=PR[plan],issued=iso(cl),status="Paid" if paid_on else "Unpaid",paid_on=iso(paid_on) if paid_on else None,days_open=None if paid_on else (TODAY-cl).days,owner=random.choice(["Sales: Aarav","Sales: Naina"])))
  if paid_on:
    payments.append(dict(date=iso(paid_on),stream="Program",plan=plan,type="New sign-up",amount=PR[plan],ref=f"INV-{ic}"))
  if plan=="3-month trial":
    end=cl+dt.timedelta(90)
    if end<=TODAY:
      if random.random()<0.55:
        ic+=1; pd=end+dt.timedelta(random.randint(-5,2))
        if pd<=TODAY:
          invoices.append(dict(invoice_id=f"INV-{ic}",family=fam,item="Trial upgrade",amount=PR["Trial upgrade"],issued=iso(pd),status="Paid",paid_on=iso(pd),days_open=None,owner="Sales: Naina"))
          payments.append(dict(date=iso(pd),stream="Program",plan="Full program",type="Trial upgrade",amount=PR["Trial upgrade"],ref=f"INV-{ic}"))
    elif (end-TODAY).days<=45:
      renewals.append(dict(family=fam,trial_start=iso(cl),trial_end=iso(end),days_left=(end-TODAY).days,advisor=random.choice(advisors),renewal_call=random.choice(["Booked","Booked","Not booked","Done – likely","Done – at risk"])))
# workshops fortnightly Saturdays
w=D(2026,4,4)
while w<=TODAY:
  seats=random.randint(18,34)
  for s in range(seats):
    pd=w-dt.timedelta(random.randint(0,12))
    payments.append(dict(date=iso(pd),stream="Workshop",plan="Workshop seat",type=f"Workshop {iso(w)}",amount=3999,ref=f"rzp_ws_{iso(w)}_{s}"))
  w+=dt.timedelta(14)
payments.sort(key=lambda r:r["date"])
targets=[dict(month=m,revenue_target=t,signup_target=s,cpql_target=1900) for m,t,s in [("2026-04",1000000,8),("2026-05",1400000,10),("2026-06",1600000,11),("2026-07",2000000,13),("2026-08",2600000,15),("2026-09",3200000,17),("2026-10",3400000,18),("2026-11",3600000,20),("2026-12",3800000,22)]]
for nm,obj in [("ads",ads),("leads",leads),("invoices",invoices),("payments",payments),("renewals",renewals),("targets",targets)]:
  json.dump(obj,open(f"sample_{nm}.json","w"),separators=(",",":"))
import collections
oct_rev=sum(p["amount"] for p in payments if p["date"]>="2026-10-01")
print(len(ads),len(leads),len(invoices),len(payments),len(renewals),"oct rev",oct_rev, "won",len(won))
print(collections.Counter(l["stage_reached"] for l in leads if l["created"]>="2026-10-01"))
print(sum(a["spend"] for a in ads if a["date"]>="2026-10-01" and a["campaign_type"]=="Program"))
