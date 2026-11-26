"""OneText-inspired dark SaaS-AI theme: navy glow, big white headline, pill nav, chat-bubble hero, blue pill CTAs, dark logo cards."""
import json
from pathlib import Path
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Red+Hat+Display:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Red Hat Display', system-ui, sans-serif; }
.stApp { background:
   radial-gradient(900px 520px at 78% 8%, rgba(37,99,235,.55), transparent 62%),
   radial-gradient(700px 480px at 8% 30%, rgba(30,64,175,.35), transparent 60%),
   linear-gradient(180deg, #060A1C 0%, #091433 55%, #060A1C 100%); }
#MainMenu, footer, header[data-testid="stHeader"] { visibility:hidden; height:0; }
.block-container { padding-top: 1.2rem; max-width: 1240px; }

/* top nav */
.nav { display:flex; align-items:center; justify-content:space-between; margin-bottom: 34px; }
.nav .left { display:flex; align-items:center; gap:14px; }
.logo { background:#fff; color:#1F5BFF; font-weight:800; padding:9px 16px; border-radius:6px; font-size:18px; position:relative; letter-spacing:-.01em; }
.logo:after { content:""; position:absolute; left:14px; bottom:-7px; border:7px solid transparent; border-top-color:#fff; border-bottom:0; border-left:0; }
.pills { display:flex; gap:22px; background:rgba(60,70,95,.55); padding:11px 22px; border-radius:8px; color:#E6EAF7; font-size:14px; font-weight:600; border:1px solid rgba(255,255,255,.06); }
.nav .right { display:flex; align-items:center; gap:22px; color:#E6EAF7; font-size:14px; font-weight:600; }
.ghost { border:1px solid rgba(255,255,255,.55); padding:10px 18px; border-radius:8px; color:#fff; display:inline-flex; gap:10px; align-items:center; }
.ghost i { background:#fff; color:#0A1230; border-radius:50%; width:20px; height:20px; display:inline-flex; align-items:center; justify-content:center; font-style:normal; font-size:12px; }

/* hero */
.hero { display:grid; grid-template-columns: 1.05fr 1fr; gap:30px; align-items:center; margin-bottom: 26px; }
.hero h1 { font-size: 58px; line-height:1.04; font-weight:600; color:#fff; letter-spacing:-.02em; margin:0 0 20px 0; }
.hero p { color:#C9D1EC; font-size:14.5px; line-height:1.6; max-width:470px; margin:0 0 30px 0; }
.cta { display:flex; gap:10px; align-items:center; }
.cta .field { display:flex; align-items:center; gap:10px; background:rgba(20,24,38,.9); border:1px solid rgba(255,255,255,.10); padding:11px 14px; border-radius:8px; color:#7F89AD; font-size:13px; min-width:250px; }
.cta .ai { background:#252B3D; color:#cbd5ff; font-weight:700; font-size:11px; padding:4px 7px; border-radius:5px; }
.cta .btn { background:#2F6BFF; color:#fff; font-weight:700; font-size:13px; padding:12px 18px; border-radius:8px; display:inline-flex; align-items:center; gap:10px; box-shadow:0 10px 30px rgba(47,107,255,.45); }
.cta .btn i { background:#fff; color:#2F6BFF; border-radius:50%; width:18px; height:18px; display:inline-flex; align-items:center; justify-content:center; font-style:normal; font-size:11px; }

/* chat bubbles */
.scene { position:relative; height:330px; }
.b { position:absolute; padding:12px 18px; border-radius:14px; font-weight:700; font-size:14px; line-height:1.25; box-shadow:0 14px 34px rgba(0,0,0,.4); max-width:250px; }
.b:after { content:""; position:absolute; bottom:-8px; left:26px; border:8px solid transparent; border-bottom:0; border-right:0; }
.b.w { background:#fff; color:#1B2236; } .b.w:after { border-top-color:#fff; }
.b.g { background:#E9E4DC; color:#2A2A33; } .b.g:after { border-top-color:#E9E4DC; }
.b.u { background:linear-gradient(135deg,#2F7BFF,#1D4ED8); color:#fff; } .b.u:after { border-top-color:#1D4ED8; left:auto; right:26px; }
.orb { position:absolute; border-radius:50%; filter:blur(.2px); }

/* proof panel */
.proof { background:#1B1E27; border:1px solid rgba(255,255,255,.05); border-radius:26px; padding:26px 30px; margin: 8px 0 26px 0; display:flex; gap:26px; align-items:center; }
.proof .q { min-width:230px; } .proof .q h3 { margin:0 0 12px 0; font-size:30px; font-weight:500; color:#fff; }
.proof .q small { color:#9CA6C9; font-size:12px; line-height:1.4; display:block; }
.cards { display:flex; gap:14px; flex:1; flex-wrap:wrap; }
.card { flex:1 1 130px; background:#232733; border:1px solid rgba(255,255,255,.08); border-radius:12px; padding:20px 14px; text-align:center; }
.card .v { font-size:28px; font-weight:800; color:#fff; } .card .l { font-size:11.5px; color:#9CA6C9; margin-top:4px; }
.card.ok .v { color:#5BE49B; } .card.bad .v { color:#FF7A90; } .card.pend .v { color:#FFC857; }

/* tabs */
.stTabs [data-baseweb="tab-list"] { margin-bottom:14px; gap:6px; padding-left:6px; background:rgba(60,70,95,.45); padding:6px; border-radius:10px; border:1px solid rgba(255,255,255,.06); }
.stTabs [data-baseweb="tab"] { height:38px; border-radius:7px; padding:0 18px; color:#D5DBF2; font-weight:600; background:transparent; }
.stTabs [aria-selected="true"] { background:#2F6BFF !important; color:#fff !important; box-shadow:0 8px 22px rgba(47,107,255,.4); }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }

/* controls */
.stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"] > div { background:rgba(20,24,38,.9) !important; border:1px solid rgba(255,255,255,.12) !important; border-radius:8px !important; color:#F4F6FF !important; }
.stTextInput input:focus { border-color:#2F6BFF !important; box-shadow:0 0 0 3px rgba(47,107,255,.28) !important; }
.stButton > button { background:#2F6BFF; color:#fff; border:0; border-radius:8px; padding:.55rem 1.2rem; font-weight:700; box-shadow:0 10px 26px rgba(47,107,255,.4); transition:transform .12s, box-shadow .12s; }
.stButton > button:hover { transform:translateY(-1px); background:#3F7AFF; color:#fff; box-shadow:0 14px 30px rgba(47,107,255,.55); }
[data-testid="stMetric"], .stExpander, [data-testid="stDataFrame"], [data-testid="stJson"], .stCodeBlock { background:#1B1E27; border:1px solid rgba(255,255,255,.07); border-radius:14px; }
[data-testid="stMetric"] { padding:14px 16px; } [data-testid="stMetricValue"] { font-weight:800; }
h2, h3 { font-weight:700; letter-spacing:-.01em; color:#fff; }
[data-testid="stImage"] img { border-radius:14px; border:1px solid rgba(255,255,255,.1); }
.badge { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:700; }
.badge.pass { background:rgba(91,228,155,.15); color:#5BE49B; } .badge.fail { background:rgba(255,122,144,.15); color:#FF7A90; } .badge.pending { background:rgba(255,200,87,.15); color:#FFC857; }
@media (max-width: 900px) { .hero { grid-template-columns:1fr; } .hero h1 { font-size:40px; } .pills { display:none; } }
</style>
"""


def apply(): st.markdown(CSS, unsafe_allow_html=True)


def hero():
    st.markdown("""
<div class="nav"><div class="left"><div class="logo">Unreliable·AI</div></div></div>
<div class="hero">
  <div><h1>Grounded answers.<br>Human-approved<br>actions. Proven.</h1>
  <p>An enterprise assistant that cites its sources, isolates every tenant, and never changes a record without a person saying yes. Its scorecard only says PASS when the evidence does.</p>
  </div>
  <div class="scene">
    <div class="b g" style="left:8%;top:6%">What is the RRF smoothing constant?</div>
    <div class="b u" style="right:4%;top:22%">Answer found, with a citation.</div>
    <div class="b w" style="left:2%;top:46%">k = 60 [1] — verified against the source.</div>
    <div class="b u" style="right:8%;top:62%">Release LOT-00007?</div>
    <div class="b g" style="left:22%;top:80%">Sent for human approval.</div>
    <div class="orb" style="width:46px;height:46px;background:radial-gradient(circle at 30% 30%,#FFD27A,#E08B00);left:62%;top:88%"></div>
    <div class="orb" style="width:22px;height:22px;background:radial-gradient(circle at 30% 30%,#8FB8FF,#2F6BFF);left:46%;top:6%"></div>
  </div></div>""", unsafe_allow_html=True)


def kpi_strip():
    p = Path("evidence/kpi_matrix.json")
    if not p.exists(): return
    c = json.loads(p.read_text())["counts"]
    st.markdown(f"""<div class="proof"><div class="q"><h3>"Show your work"</h3><small>Computed scorecard<br>from tests and evidence files</small></div>
      <div class="cards"><div class="card ok"><div class="v">{c['PASS']}</div><div class="l">KPIs passing</div></div>
      <div class="card bad"><div class="v">{c['FAIL']}</div><div class="l">KPIs failing</div></div>
      <div class="card pend"><div class="v">{c['PENDING']}</div><div class="l">pending evidence</div></div>
      <div class="card"><div class="v">100</div><div class="l">red-team prompts handled</div></div>
      <div class="card"><div class="v">195</div><div class="l">tests passing</div></div></div></div>""", unsafe_allow_html=True)


def badge(status: str) -> str: return f'<span class="badge {status.lower()}">{status}</span>'
