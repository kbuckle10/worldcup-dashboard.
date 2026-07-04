"""
World Cup 2026 Dashboard & Explorer
Deployable on Streamlit Community Cloud.

Default data source: https://worldcup26.ir public World Cup 2026 API
Optional token support: set WORLDCUP26_TOKEN in Streamlit secrets if your API instance requires auth.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DEFAULT_API_BASE = "https://worldcup26.ir"

STAGE_LABELS = {
    "group": "Group Stage",
    "r32": "Round of 32",
    "r16": "Round of 16",
    "qf": "Quarterfinals",
    "sf": "Semifinals",
    "third": "Third Place",
    "final": "Final",
}
STAGE_ORDER = ["group", "r32", "r16", "qf", "sf", "third", "final"]
GROUPS = list("ABCDEFGHIJKL")

TEAM_FLAG_MAP: Dict[str, str] = {}

FALLBACK_FLAGS = {
    "Argentina": "🇦🇷", "Australia": "🇦🇺", "Austria": "🇦🇹", "Belgium": "🇧🇪",
    "Bosnia and Herzegovina": "🇧🇦", "Brazil": "🇧🇷", "Canada": "🇨🇦", "Cape Verde": "🇨🇻",
    "Cabo Verde": "🇨🇻", "Colombia": "🇨🇴", "Croatia": "🇭🇷", "Czechia": "🇨🇿",
    "DR Congo": "🇨🇩", "Congo DR": "🇨🇩", "Democratic Republic of the Congo": "🇨🇩",
    "Ecuador": "🇪🇨", "Egypt": "🇪🇬", "England": "🏴", "France": "🇫🇷", "Germany": "🇩🇪",
    "Ghana": "🇬🇭", "Haiti": "🇭🇹", "Iran": "🇮🇷", "IR Iran": "🇮🇷", "Iraq": "🇮🇶",
    "Ivory Coast": "🇨🇮", "Côte d’Ivoire": "🇨🇮", "Japan": "🇯🇵", "Jordan": "🇯🇴",
    "Mexico": "🇲🇽", "Morocco": "🇲🇦", "Netherlands": "🇳🇱", "New Zealand": "🇳🇿",
    "Norway": "🇳🇴", "Panama": "🇵🇦", "Paraguay": "🇵🇾", "Portugal": "🇵🇹",
    "Qatar": "🇶🇦", "Saudi Arabia": "🇸🇦", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Senegal": "🇸🇳",
    "South Africa": "🇿🇦", "Korea Republic": "🇰🇷", "South Korea": "🇰🇷", "Spain": "🇪🇸",
    "Sweden": "🇸🇪", "Switzerland": "🇨🇭", "Tunisia": "🇹🇳", "Turkey": "🇹🇷", "Turkiye": "🇹🇷",
    "United States": "🇺🇸", "USA": "🇺🇸", "Uruguay": "🇺🇾", "Uzbekistan": "🇺🇿",
    "Algeria": "🇩🇿", "Curaçao": "🇨🇼", "Curacao": "🇨🇼",
}

TEAM_CODE_MAP = {
    "Argentina":"ARG", "Australia":"AUS", "Austria":"AUT", "Belgium":"BEL", "Bosnia and Herzegovina":"BIH",
    "Brazil":"BRA", "Canada":"CAN", "Cape Verde":"CPV", "Cabo Verde":"CPV", "Colombia":"COL", "Croatia":"CRO",
    "Czechia":"CZE", "DR Congo":"COD", "Congo DR":"COD", "Democratic Republic of the Congo":"COD", "Ecuador":"ECU",
    "Egypt":"EGY", "England":"ENG", "France":"FRA", "Germany":"GER", "Ghana":"GHA", "Haiti":"HAI", "Iran":"IRN",
    "IR Iran":"IRN", "Iraq":"IRQ", "Ivory Coast":"CIV", "Côte d’Ivoire":"CIV", "Japan":"JPN", "Jordan":"JOR",
    "Mexico":"MEX", "Morocco":"MAR", "Netherlands":"NED", "New Zealand":"NZL", "Norway":"NOR", "Panama":"PAN",
    "Paraguay":"PAR", "Portugal":"POR", "Qatar":"QAT", "Saudi Arabia":"KSA", "Scotland":"SCO", "Senegal":"SEN",
    "South Africa":"RSA", "Korea Republic":"KOR", "South Korea":"KOR", "Spain":"ESP", "Sweden":"SWE", "Switzerland":"SUI",
    "Tunisia":"TUN", "Turkey":"TUR", "Turkiye":"TUR", "United States":"USA", "USA":"USA", "Uruguay":"URU",
    "Uzbekistan":"UZB", "Algeria":"ALG", "Curaçao":"CUW", "Curacao":"CUW",
}

TEAM_ISO2_MAP = {
    "Argentina":"ar", "Australia":"au", "Austria":"at", "Belgium":"be", "Bosnia and Herzegovina":"ba", "Brazil":"br",
    "Canada":"ca", "Cape Verde":"cv", "Cabo Verde":"cv", "Colombia":"co", "Croatia":"hr", "Czechia":"cz", "DR Congo":"cd",
    "Congo DR":"cd", "Democratic Republic of the Congo":"cd", "Ecuador":"ec", "Egypt":"eg", "England":"gb-eng",
    "France":"fr", "Germany":"de", "Ghana":"gh", "Haiti":"ht", "Iran":"ir", "IR Iran":"ir", "Iraq":"iq", "Ivory Coast":"ci",
    "Côte d’Ivoire":"ci", "Japan":"jp", "Jordan":"jo", "Mexico":"mx", "Morocco":"ma", "Netherlands":"nl", "New Zealand":"nz",
    "Norway":"no", "Panama":"pa", "Paraguay":"py", "Portugal":"pt", "Qatar":"qa", "Saudi Arabia":"sa", "Scotland":"gb-sct",
    "Senegal":"sn", "South Africa":"za", "Korea Republic":"kr", "South Korea":"kr", "Spain":"es", "Sweden":"se", "Switzerland":"ch",
    "Tunisia":"tn", "Turkey":"tr", "Turkiye":"tr", "United States":"us", "USA":"us", "Uruguay":"uy", "Uzbekistan":"uz",
    "Algeria":"dz", "Curaçao":"cw", "Curacao":"cw",
}

st.set_page_config(
    page_title="World Cup 2026 Dashboard",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      :root {
        --wc-bg: #06111f;
        --wc-panel: rgba(12, 25, 43, 0.94);
        --wc-panel-2: rgba(15, 31, 53, 0.90);
        --wc-border: rgba(148, 163, 184, 0.24);
        --wc-text: #f8fafc;
        --wc-muted: #a8b3c7;
        --wc-gold: #f7c948;
        --wc-green: #22c55e;
        --wc-red: #ef4444;
        --wc-blue: #38bdf8;
      }
      html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(circle at top left, rgba(14, 165, 233, 0.16), transparent 34rem),
          radial-gradient(circle at top right, rgba(34, 197, 94, 0.12), transparent 32rem),
          linear-gradient(180deg, #07101d 0%, #081423 42%, #050914 100%) !important;
        color: var(--wc-text) !important;
      }
      [data-testid="stHeader"], [data-testid="stToolbar"] {background: transparent !important;}
      [data-testid="stSidebar"] {background: linear-gradient(180deg, #07111f 0%, #0b1728 100%) !important; border-right: 1px solid var(--wc-border);}
      h1, h2, h3, h4, h5, h6, p, span, label, div {color: inherit;}
      .main-title {font-size: 2.4rem; font-weight: 900; margin-bottom: 0.2rem; color: var(--wc-text); letter-spacing: -0.04em;}
      .subtle {color: var(--wc-muted) !important; font-size: 0.95rem;}
      .wc-hero {position: relative; overflow: hidden; border: 1px solid rgba(247, 201, 72, 0.38); border-radius: 20px; padding: 16px 24px; margin: 0 0 12px 0; background: linear-gradient(120deg, rgba(2, 6, 23, .95), rgba(11, 42, 70, .92)), radial-gradient(circle at 12% 20%, rgba(247, 201, 72, .23), transparent 16rem), radial-gradient(circle at 85% 45%, rgba(34, 197, 94, .18), transparent 20rem); box-shadow: 0 22px 55px rgba(0, 0, 0, 0.35);}
      .wc-hero::after {content: ""; position: absolute; inset: 0; background-image: linear-gradient(120deg, transparent 0%, transparent 60%, rgba(255,255,255,.06) 60%, transparent 78%), repeating-linear-gradient(90deg, rgba(255,255,255,.035) 0 1px, transparent 1px 90px); pointer-events: none;}
      .wc-hero-inner {position: relative; z-index: 1; display: flex; justify-content: space-between; align-items: center; gap: 20px;}
      .wc-hero-kicker {color: var(--wc-gold); font-weight: 800; text-transform: uppercase; letter-spacing: .16em; font-size: .78rem;}
      .wc-hero-title {color: #fff; font-size: clamp(1.8rem, 3.2vw, 3.2rem); line-height: .94; font-weight: 950; letter-spacing: -.06em; margin: 8px 0;}
      .wc-hero-title strong {display: inline-block; margin-left: .25rem; color: var(--wc-gold); text-shadow: 0 0 20px rgba(247, 201, 72, .30);}
      .wc-hosts {display:flex; flex-wrap:wrap; gap:8px; margin-top:10px;}
      .wc-host-pill {display:inline-flex; align-items:center; gap:7px; border: 1px solid rgba(255,255,255,.16); background: rgba(255,255,255,.08); color:#fff; border-radius: 999px; padding: 5px 10px; font-weight: 800; backdrop-filter: blur(10px);}
      .wc-trophy {width: 76px; height: 76px; min-width: 76px; border-radius: 20px; display:flex; align-items:center; justify-content:center; font-size: 3rem; background: linear-gradient(135deg, rgba(247,201,72,.24), rgba(255,255,255,.07)); border: 1px solid rgba(247,201,72,.36); box-shadow: inset 0 0 45px rgba(247,201,72,.08), 0 18px 50px rgba(0,0,0,.32);}
      .wc-stat-card, .match-card, .wc-live-card, .wc-bracket-card {border: 1px solid var(--wc-border); border-radius: 18px; background: linear-gradient(180deg, rgba(15, 31, 53, .92), rgba(8, 20, 36, .92)); color: var(--wc-text) !important; box-shadow: 0 14px 38px rgba(0,0,0,.22);}
      .wc-stat-card {padding: 16px; display:flex; align-items:center; gap:14px;}
      .wc-stat-icon {height:48px; width:48px; border-radius:16px; display:flex; align-items:center; justify-content:center; background: rgba(56,189,248,.13); font-size:1.55rem;}
      .wc-stat-value {font-size:1.85rem; line-height:1; font-weight:950; color:#fff;}
      .wc-stat-label {color:var(--wc-muted); font-size:.86rem; margin-top:4px;}
      .match-card {padding: 15px; margin-bottom: 12px;}
      .match-card h4, .match-card b {color: #ffffff !important;}
      .wc-match-line {display:flex; align-items:center; justify-content:space-between; gap:12px; margin:11px 0 7px;}
      .wc-team-name {font-weight:850; color:#fff;}
      .wc-score {color:#fff; font-size:1.35rem; font-weight:950; white-space:nowrap;}
      .wc-flag {font-size:1.32rem; margin-right:6px; vertical-align:-1px;}
      .tag {display:inline-block; padding:3px 9px; border-radius:999px; background:rgba(148,163,184,.14); color:var(--wc-text); font-size:.76rem; font-weight:800; margin-right:5px; border:1px solid rgba(255,255,255,.08);}
      .live {background:rgba(239,68,68,.16); color:#fecaca; border-color:rgba(239,68,68,.4); animation:pulseLive 1.5s infinite;}
      .finished {background:rgba(34,197,94,.14); color:#bbf7d0; border-color:rgba(34,197,94,.32);}
      .scheduled {background:rgba(59,130,246,.13); color:#bfdbfe; border-color:rgba(59,130,246,.30);}
      @keyframes pulseLive {0%,100%{box-shadow:0 0 0 rgba(239,68,68,0)} 50%{box-shadow:0 0 18px rgba(239,68,68,.32)}}
      .explain {background:linear-gradient(90deg, rgba(56,189,248,.12), rgba(34,197,94,.08)); color:var(--wc-text); border-left:4px solid var(--wc-blue); padding:14px 16px; border-radius:14px;}
      .wc-live-card {padding:18px; margin-bottom:12px; position:relative; overflow:hidden;}
      .wc-live-teams {display:grid; grid-template-columns:1fr auto 1fr; gap:16px; align-items:center; margin-top:14px;}
      .wc-live-team {text-align:center; font-weight:900;}
      .wc-live-flag {font-size:2.4rem; display:block; margin-bottom:4px;}
      .wc-live-score {font-size:3rem; font-weight:950; color:#fff;}
      .wc-timeline {height:6px; border-radius:999px; background:rgba(148,163,184,.22); margin-top:16px; overflow:hidden;}
      .wc-timeline-fill {height:100%; background:linear-gradient(90deg, #22c55e, #f7c948); border-radius:999px;}
      .wc-bracket-grid {display:grid; grid-template-columns:repeat(6, minmax(210px, 1fr)); gap:12px; overflow-x:auto; padding-bottom:8px;}
      .wc-bracket-col {min-width:210px;}
      .wc-bracket-title {color:var(--wc-gold); font-size:.78rem; text-transform:uppercase; letter-spacing:.12em; font-weight:900; margin:0 0 10px 2px;}
      .wc-bracket-card {padding:11px; margin-bottom:10px; position:relative;}
      .wc-bracket-card::after {content:""; position:absolute; right:-10px; top:50%; width:10px; height:1px; background:rgba(247,201,72,.35);}
      .wc-bracket-team {display:flex; justify-content:space-between; align-items:center; gap:8px; font-weight:800; margin:4px 0;}
      .wc-bracket-team span:first-child {white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
      .wc-bracket-score {font-weight:950; color:#fff;}
      .wc-bracket-winner {border-left:3px solid var(--wc-green); padding-left:6px;}
      .stTabs [data-baseweb="tab-list"] {gap: 10px;}
      .stTabs [data-baseweb="tab"] {color: var(--wc-muted); font-weight: 800;}
      .stTabs [aria-selected="true"] {color: #fff !important;}
      div[data-testid="stMetricValue"] {font-size: 1.65rem;}
      div[data-testid="stDataFrame"] {border-radius: 16px; overflow: hidden;}

      .wc-trophy-img {width:58px; height:58px; object-fit:contain; filter:drop-shadow(0 8px 18px rgba(247,201,72,.28));}
      .wc-live-dot {width:10px; height:10px; display:inline-block; border-radius:999px; background:#ef4444; margin-right:7px; box-shadow:0 0 0 rgba(239,68,68,.7); animation:dotPulse 1.2s infinite;}
      @keyframes dotPulse {0%{box-shadow:0 0 0 0 rgba(239,68,68,.75)}70%{box-shadow:0 0 0 10px rgba(239,68,68,0)}100%{box-shadow:0 0 0 0 rgba(239,68,68,0)}}
      .wc-win-row {display:flex; justify-content:space-between; align-items:center; gap:18px; margin-top:8px; font-weight:900; color:#f8fafc;}
      .wc-win-row span {white-space:nowrap;}
      .wc-win-home {color:#f43f5e;} .wc-win-away {color:#22d3ee;}
      .wc-live-card .wc-team-name {display:flex; justify-content:center;}
      .flag-img {width:25px; height:17px; object-fit:cover; border-radius:3px; box-shadow:0 0 0 1px rgba(255,255,255,.20); vertical-align:-3px; margin-right:8px;}
      .team-chip {display:inline-flex; align-items:center; gap:4px; min-width:0;}
      .team-chip .team-name {font-weight:900; color:#fff; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
      .team-code {font-size:.68rem; color:#94a3b8; font-weight:950; letter-spacing:.06em; margin-left:4px;}
      .wc-team-hero-code {display:block; color:#9fb0c9; font-size:.78rem; font-weight:900; margin-top:4px;}
    </style>
    """,
    unsafe_allow_html=True,
)


def secret(name: str, default: str = "") -> str:
    """Safely read Streamlit secrets locally or on Streamlit Cloud."""
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    value = str(value).strip()
    if value.lower() in {"none", "null", "nan", ""}:
        return default
    return value



def esc(value: Any) -> str:
    import html as _html
    return _html.escape(clean_text(value), quote=True)

def team_code(team: Any) -> str:
    name = clean_text(team)
    if not name:
        return "TBD"
    if name.upper() in TEAM_CODE_MAP.values() and len(name) == 3:
        return name.upper()
    return TEAM_CODE_MAP.get(name, re.sub(r"[^A-Za-z]", "", name).upper()[:3].ljust(3, "X"))

def team_iso2(team: Any) -> str:
    return TEAM_ISO2_MAP.get(clean_text(team), "")

def flag_img(team: Any) -> str:
    name = clean_text(team)
    iso = team_iso2(name)
    emoji = TEAM_FLAG_MAP.get(name) or FALLBACK_FLAGS.get(name) or "⚽"
    if iso:
        return f'<img class="flag-img" src="https://flagcdn.com/w40/{iso}.png" alt="{esc(name)} flag" loading="lazy">'
    return f'<span class="wc-flag">{emoji}</span>'

def team_chip(team: Any, show_code: bool = True) -> str:
    name = clean_text(team, "TBD")
    code_html = f'<span class="team-code">{team_code(name)}</span>' if show_code else ""
    return f'<span class="team-chip">{flag_img(name)}<span class="team-name">{esc(name)}</span>{code_html}</span>'

def build_flag_map(teams_df: pd.DataFrame) -> Dict[str, str]:
    flags = dict(FALLBACK_FLAGS)
    if not teams_df.empty:
        for _, row in teams_df.iterrows():
            team = clean_text(row.get("team"))
            flag = clean_text(row.get("flag"))
            code = clean_text(row.get("code"))
            if team and flag and not flag.lower().startswith("http"):
                flags[team] = flag
            if team and code and team not in flags:
                flags[team] = FALLBACK_FLAGS.get(team, "⚽")
    return flags


def team_flag(team: Any) -> str:
    name = clean_text(team)
    return TEAM_FLAG_MAP.get(name) or FALLBACK_FLAGS.get(name) or "⚽"


def live_minute(row: pd.Series) -> str:
    if row.get("status") != "Live":
        return ""
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    for value in [row.get("elapsed"), raw.get("elapsed"), raw.get("time_elapsed"), raw.get("minute"), raw.get("match_minute"), raw.get("current_minute"), raw.get("status_short")]:
        txt = clean_text(value)
        low = txt.lower()
        if not txt or low in {"live", "in_play", "in play", "0", "scheduled", "notstarted", "not started"}:
            continue
        if low in {"ht", "half time", "halftime"}:
            return "HT"
        if re.search(r"\d", txt):
            return txt if txt.endswith("'") else f"{txt}'"
        return txt.upper()
    dt = row.get("date_time")
    if isinstance(dt, datetime):
        mins = int((datetime.now() - dt).total_seconds() // 60)
        if 0 <= mins <= 130:
            if 45 <= mins < 60:
                return "HT"
            if mins > 105:
                return "ET"
            return f"{max(1, mins)}'"
    return "LIVE"

def timeline_percent(row: pd.Series) -> int:
    minute = live_minute(row)
    m = re.search(r"\d+", minute)
    if not m:
        return 8 if row.get("status") == "Live" else 0
    return max(4, min(100, int(int(m.group()) / 90 * 100)))


def render_hero(matches_df: pd.DataFrame, source: str = "") -> None:
    live_count = int((matches_df["status"] == "Live").sum()) if not matches_df.empty else 0
    finished_count = int((matches_df["status"] == "Finished").sum()) if not matches_df.empty else 0
    total_count = len(matches_df) if not matches_df.empty else 0
    st.markdown(
        f'''
        <section class="wc-hero">
          <div class="wc-hero-inner">
            <div>
              <div class="wc-hero-kicker">United States • Canada • Mexico</div>
              <div class="wc-hero-title">FIFA World Cup<strong>2026™</strong></div>
              <div class="subtle" style="font-size:1.08rem;">Live scores, standings, knockout routes and fan-friendly insights in one place.</div>
              <div class="wc-hosts">
                <span class="wc-host-pill">🇺🇸 United States</span>
                <span class="wc-host-pill">🇨🇦 Canada</span>
                <span class="wc-host-pill">🇲🇽 Mexico</span>
                <span class="wc-host-pill">🔴 {live_count} live</span>
                <span class="wc-host-pill">✅ {finished_count}/{total_count} completed</span>
              </div>
            </div>
            <div class="wc-trophy"><img class="wc-trophy-img" src="data:image/png;base64,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" alt="FIFA World Cup trophy"></div>
          </div>
        </section>
        ''',
        unsafe_allow_html=True,
    )


def render_stat_card(icon: str, value: Any, label: str) -> None:
    st.markdown(
        f'''
        <div class="wc-stat-card">
          <div class="wc-stat-icon">{icon}</div>
          <div>
            <div class="wc-stat-value">{value}</div>
            <div class="wc-stat-label">{label}</div>
          </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


def to_int(value: Any, default: Optional[int] = 0) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    try:
        text = str(value).strip()
        if text.lower() in {"", "none", "null", "nan", "tbd", "-"}:
            return default
        return int(float(text))
    except Exception:
        return default


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "finished", "complete", "ft"}


def unwrap(payload: Any, preferred_keys: Iterable[str]) -> List[Dict[str, Any]]:
    """Normalize API responses that may be list, {games:[...]}, {data:[...]}, etc."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in preferred_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
            if isinstance(value, dict):
                return [value]
        # Some endpoints return one object directly.
        if any(k in payload for k in ["id", "group", "name_en", "home_team_id"]):
            return [payload]
    return []


def stage_name(stage_code: str) -> str:
    return STAGE_LABELS.get(clean_text(stage_code).lower(), clean_text(stage_code, "Unknown").title())


def normalize_stage(row: Dict[str, Any]) -> str:
    raw = clean_text(row.get("type") or row.get("stage") or row.get("round") or row.get("group"), "group").lower()
    raw = raw.replace("round_of_32", "r32").replace("round of 32", "r32")
    raw = raw.replace("round_of_16", "r16").replace("round of 16", "r16")
    raw = raw.replace("quarterfinal", "qf").replace("quarter-final", "qf").replace("quarter finals", "qf")
    raw = raw.replace("semifinal", "sf").replace("semi-final", "sf")
    raw = raw.replace("3rd", "third").replace("third place playoff", "third")
    if raw in STAGE_LABELS:
        return raw
    if raw in [g.lower() for g in GROUPS]:
        return "group"
    return raw or "group"


def normalize_status(row: Dict[str, Any]) -> str:
    finished = row.get("finished") or row.get("status") or row.get("match_status")
    elapsed = clean_text(row.get("time_elapsed") or row.get("elapsed") or row.get("minute"), "")
    status_text = clean_text(row.get("status") or row.get("match_status"), "").lower()
    if boolish(finished) or status_text in {"finished", "complete", "ft", "full time"}:
        return "Finished"
    if elapsed and elapsed.lower() not in {"notstarted", "not started", "scheduled", "0"}:
        return "Live"
    if status_text in {"live", "in_play", "1h", "2h", "ht", "et", "p"}:
        return "Live"
    return "Scheduled"


def parse_dt(value: Any) -> Optional[datetime]:
    text = clean_text(value)
    if not text:
        return None
    # Main worldcup26 format: 06/11/2026 13:00
    for fmt in ["%m/%d/%Y %H:%M", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        ts = pd.to_datetime(text, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


def format_dt(value: Any) -> str:
    dt = parse_dt(value)
    if dt is None:
        return clean_text(value, "TBD")
    return dt.strftime("%a, %b %d • %I:%M %p").replace(" 0", " ").replace("• 0", "• ") if hasattr(dt, "strftime") else str(value)


def response_or_none(resp: requests.Response) -> Any:
    if resp.status_code in {401, 403}:
        raise RuntimeError("API requires authorization. Add WORLDCUP26_TOKEN in Streamlit secrets or switch to fallback/demo data.")
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=60, show_spinner=False)
def fetch_api(path: str, api_base: str, token: str = "") -> Any:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{api_base.rstrip('/')}/{path.lstrip('/')}"
    resp = requests.get(url, headers=headers, timeout=15)
    return response_or_none(resp)


@st.cache_data(ttl=3600, show_spinner=False)
def load_fallback() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    with open(DATA_DIR / "fallback_matches.json", "r", encoding="utf-8") as f:
        matches = json.load(f)
    with open(DATA_DIR / "fallback_groups.json", "r", encoding="utf-8") as f:
        groups = json.load(f)
    with open(DATA_DIR / "fallback_stadiums.json", "r", encoding="utf-8") as f:
        stadiums = json.load(f)

    teams_rows = []
    for grp in groups:
        for team in grp["teams"]:
            teams_rows.append(
                {
                    "team_id": team.get("team_id"),
                    "team": team.get("team"),
                    "code": team.get("code", ""),
                    "group": grp.get("group"),
                    "flag": team.get("flag", ""),
                }
            )
    return (
        normalize_matches(matches),
        pd.DataFrame(teams_rows).drop_duplicates("team"),
        normalize_groups(groups, pd.DataFrame(teams_rows)),
        pd.DataFrame(stadiums),
        "Demo fallback snapshot",
    )


def normalize_teams(raw: Any) -> pd.DataFrame:
    rows = []
    for item in unwrap(raw, ["teams", "data", "response", "team"]):
        rows.append(
            {
                "team_id": clean_text(item.get("id") or item.get("team_id") or item.get("_id")),
                "team": clean_text(item.get("name_en") or item.get("name") or item.get("team") or item.get("team_name"), "Unknown"),
                "code": clean_text(item.get("fifa_code") or item.get("code") or item.get("short_name")),
                "group": clean_text(item.get("groups") or item.get("group")),
                "flag": clean_text(item.get("flag") or item.get("logo")),
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset=["team_id", "team"], keep="first")


def normalize_stadiums(raw: Any) -> pd.DataFrame:
    rows = []
    for item in unwrap(raw, ["stadiums", "venues", "data", "response", "stadium"]):
        rows.append(
            {
                "stadium_id": clean_text(item.get("id") or item.get("stadium_id") or item.get("_id")),
                "stadium": clean_text(item.get("name_en") or item.get("name") or item.get("fifa_name"), "Unknown"),
                "city": clean_text(item.get("city_en") or item.get("city")),
                "country": clean_text(item.get("country_en") or item.get("country")),
                "capacity": to_int(item.get("capacity"), None),
            }
        )
    return pd.DataFrame(rows)


def normalize_matches(raw: Any) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for item in unwrap(raw, ["games", "matches", "fixtures", "data", "response", "game"]):
        home_score = to_int(item.get("home_score") or item.get("homeScore") or item.get("home_goals"), None)
        away_score = to_int(item.get("away_score") or item.get("awayScore") or item.get("away_goals"), None)
        status = normalize_status(item)
        if status == "Scheduled":
            # Avoid showing 0-0 for future fixtures unless API explicitly reports a score.
            if str(item.get("home_score", "")).lower() in {"", "0", "none", "null"}:
                home_score = None
            if str(item.get("away_score", "")).lower() in {"", "0", "none", "null"}:
                away_score = None
        stage = normalize_stage(item)
        match_dt = parse_dt(item.get("local_date") or item.get("utcDate") or item.get("date") or item.get("kickoff"))
        rows.append(
            {
                "match_id": clean_text(item.get("id") or item.get("match_id") or item.get("fixture_id") or item.get("_id")),
                "date_time": match_dt,
                "kickoff": format_dt(item.get("local_date") or item.get("utcDate") or item.get("date") or item.get("kickoff")),
                "home_team_id": clean_text(item.get("home_team_id") or item.get("homeTeamId")),
                "away_team_id": clean_text(item.get("away_team_id") or item.get("awayTeamId")),
                "home_team": clean_text(item.get("home_team_name_en") or item.get("home_team") or item.get("homeTeam") or item.get("home_team_label"), "TBD"),
                "away_team": clean_text(item.get("away_team_name_en") or item.get("away_team") or item.get("awayTeam") or item.get("away_team_label"), "TBD"),
                "home_score": home_score,
                "away_score": away_score,
                "home_scorers": clean_text(item.get("home_scorers")),
                "away_scorers": clean_text(item.get("away_scorers")),
                "group": clean_text(item.get("group")),
                "matchday": clean_text(item.get("matchday")),
                "stadium_id": clean_text(item.get("stadium_id") or item.get("venue_id")),
                "stage": stage,
                "stage_label": stage_name(stage),
                "status": status,
                "elapsed": clean_text(item.get("time_elapsed") or item.get("elapsed") or item.get("minute")),
                "raw": item,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["total_goals"] = df[["home_score", "away_score"]].sum(axis=1, min_count=1)
        df["score"] = df.apply(
            lambda r: "TBD" if pd.isna(r.get("home_score")) or pd.isna(r.get("away_score")) else f"{int(r['home_score'])}-{int(r['away_score'])}",
            axis=1,
        )
        df["winner"] = df.apply(match_winner, axis=1)
        df["stage_rank"] = df["stage"].apply(lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else 99)
        df = df.sort_values(by=["date_time", "stage_rank", "match_id"], na_position="last")
    return df


def match_winner(row: pd.Series) -> str:
    if row.get("status") != "Finished":
        return ""
    h, a = row.get("home_score"), row.get("away_score")
    if pd.isna(h) or pd.isna(a):
        return ""
    if h > a:
        return row.get("home_team", "")
    if a > h:
        return row.get("away_team", "")
    # Penalty winner is not consistently exposed by the free API, so draw is safest here.
    return "Draw / penalties"


def normalize_groups(raw: Any, teams_df: pd.DataFrame) -> pd.DataFrame:
    team_lookup = {}
    if not teams_df.empty:
        for _, row in teams_df.iterrows():
            if clean_text(row.get("team_id")):
                team_lookup[clean_text(row.get("team_id"))] = row.to_dict()
            team_lookup[clean_text(row.get("team"))] = row.to_dict()

    rows = []
    groups = unwrap(raw, ["groups", "data", "response", "tables", "standings"])
    for group_obj in groups:
        group_letter = clean_text(group_obj.get("group") or group_obj.get("name") or group_obj.get("group_name"))
        group_letter = group_letter.replace("Group ", "").strip()
        team_items = group_obj.get("teams") or group_obj.get("standings") or group_obj.get("table") or []
        if isinstance(team_items, dict):
            team_items = list(team_items.values())
        for idx, team_obj in enumerate(team_items, start=1):
            if not isinstance(team_obj, dict):
                continue
            team_id = clean_text(team_obj.get("team_id") or team_obj.get("id") or team_obj.get("teamId"))
            lookup = team_lookup.get(team_id, {})
            team_name = clean_text(
                team_obj.get("team")
                or team_obj.get("team_name")
                or team_obj.get("name")
                or lookup.get("team"),
                f"Team {team_id}" if team_id else "Unknown",
            )
            pts = to_int(team_obj.get("pts") or team_obj.get("points"), 0)
            gf = to_int(team_obj.get("gf") or team_obj.get("goals_for") or team_obj.get("goalsFor"), 0)
            ga = to_int(team_obj.get("ga") or team_obj.get("goals_against") or team_obj.get("goalsAgainst"), 0)
            rows.append(
                {
                    "group": clean_text(team_obj.get("group") or lookup.get("group") or group_letter),
                    "rank": to_int(team_obj.get("rank") or team_obj.get("position"), idx),
                    "team_id": team_id,
                    "team": team_name,
                    "code": clean_text(team_obj.get("code") or lookup.get("code")),
                    "P": to_int(team_obj.get("played") or team_obj.get("p") or team_obj.get("mp"), None),
                    "W": to_int(team_obj.get("win") or team_obj.get("w"), None),
                    "D": to_int(team_obj.get("draw") or team_obj.get("d"), None),
                    "L": to_int(team_obj.get("lose") or team_obj.get("loss") or team_obj.get("l"), None),
                    "GF": gf,
                    "GA": ga,
                    "GD": gf - ga if gf is not None and ga is not None else None,
                    "Pts": pts,
                    "source": "api_group_table",
                }
            )
    return pd.DataFrame(rows)


def calculate_standings_from_matches(matches_df: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    if matches_df.empty:
        return pd.DataFrame()
    group_matches = matches_df[(matches_df["stage"] == "group") & (matches_df["status"] == "Finished")].copy()
    if group_matches.empty:
        return pd.DataFrame()

    team_group = {}
    if not teams_df.empty:
        team_group = dict(zip(teams_df["team"], teams_df["group"]))

    records: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def ensure(team: str, grp: str) -> Dict[str, Any]:
        key = (grp, team)
        if key not in records:
            records[key] = {"group": grp, "team": team, "P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0, "Pts": 0}
        return records[key]

    for _, m in group_matches.iterrows():
        if pd.isna(m["home_score"]) or pd.isna(m["away_score"]):
            continue
        grp = clean_text(m.get("group"))
        if grp not in GROUPS:
            grp = clean_text(team_group.get(m["home_team"]) or team_group.get(m["away_team"]))
        h = ensure(m["home_team"], grp)
        a = ensure(m["away_team"], grp)
        hs, as_ = int(m["home_score"]), int(m["away_score"])
        h["P"] += 1; a["P"] += 1
        h["GF"] += hs; h["GA"] += as_
        a["GF"] += as_; a["GA"] += hs
        if hs > as_:
            h["W"] += 1; h["Pts"] += 3; a["L"] += 1
        elif as_ > hs:
            a["W"] += 1; a["Pts"] += 3; h["L"] += 1
        else:
            h["D"] += 1; a["D"] += 1; h["Pts"] += 1; a["Pts"] += 1

    table = pd.DataFrame(records.values())
    if table.empty:
        return table
    table["GD"] = table["GF"] - table["GA"]
    table = table.sort_values(["group", "Pts", "GD", "GF"], ascending=[True, False, False, False])
    table["rank"] = table.groupby("group").cumcount() + 1
    table["source"] = "calculated_from_matches"
    return table


@st.cache_data(ttl=60, show_spinner=False)
def load_live_data(api_base: str, token: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    errors = []
    try:
        matches_raw = fetch_api("/get/games", api_base, token)
        teams_raw = fetch_api("/get/teams", api_base, token)
        groups_raw = fetch_api("/get/groups", api_base, token)
        stadiums_raw = fetch_api("/get/stadiums", api_base, token)
        teams = normalize_teams(teams_raw)
        matches = normalize_matches(matches_raw)
        groups = normalize_groups(groups_raw, teams)
        stadiums = normalize_stadiums(stadiums_raw)
        return matches, teams, groups, stadiums, "Live API"
    except Exception as exc:
        errors.append(str(exc))
        matches, teams, groups, stadiums, source = load_fallback()
        st.warning("Live API could not be loaded, so the app is using the demo fallback snapshot. Details: " + "; ".join(errors))
        return matches, teams, groups, stadiums, source


def enrich_matches(matches: pd.DataFrame, stadiums: pd.DataFrame) -> pd.DataFrame:
    if matches.empty:
        return matches
    df = matches.copy()
    if not stadiums.empty and "stadium_id" in df.columns:
        df = df.merge(stadiums, how="left", on="stadium_id")
        df["venue"] = df.apply(lambda r: clean_text(r.get("stadium"), "") + (f" — {clean_text(r.get('city'))}" if clean_text(r.get("city")) else ""), axis=1)
    else:
        df["venue"] = ""
    return df


def scoreline_label(row: pd.Series) -> str:
    if pd.isna(row.get("home_score")) or pd.isna(row.get("away_score")):
        return "TBD"
    return f"{int(row['home_score'])}-{int(row['away_score'])}"


def status_badge(status: str) -> str:
    cls = "live" if status == "Live" else "finished" if status == "Finished" else "scheduled"
    return f"<span class='tag {cls}'>{status}</span>"


def render_match_card(row: pd.Series, compact: bool = False) -> None:
    score = scoreline_label(row)
    status = status_badge(row.get("status", "Scheduled"))
    minute = live_minute(row)
    elapsed_html = f"<span class='tag live'>⏱ {minute}</span>" if minute else ""
    venue = clean_text(row.get("venue"))
    winner = clean_text(row.get("winner"))
    winner_line = f"<div class='subtle'>Winner: <b>{winner}</b></div>" if winner and winner != "Draw / penalties" else ""
    home = clean_text(row.get("home_team", "TBD"), "TBD")
    away = clean_text(row.get("away_team", "TBD"), "TBD")
    st.markdown(
        f"""
        <div class="match-card">
          <div>{status}{elapsed_html}<span class="tag">{row.get('stage_label','')}</span></div>
          <div class="wc-match-line">
            <div class="wc-team-name">{team_chip(home)}</div>
            <div class="wc-score">{score}</div>
            <div class="wc-team-name" style="text-align:right; justify-content:flex-end; display:flex;">{team_chip(away)}</div>
          </div>
          <div class="subtle">{row.get('kickoff','TBD')}{' • ' + venue if venue else ''}</div>
          {winner_line if not compact else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def explain_current_stage(matches_df: pd.DataFrame) -> str:
    if matches_df.empty:
        return "No match data loaded yet."
    live = matches_df[matches_df["status"] == "Live"]
    if not live.empty:
        stages = ", ".join(live["stage_label"].dropna().unique())
        return f"Live now: {len(live)} match(es), currently in {stages}."
    scheduled = matches_df[matches_df["status"] == "Scheduled"].sort_values("date_time", na_position="last")
    finished = matches_df[matches_df["status"] == "Finished"]
    if not scheduled.empty:
        return f"Next up: {scheduled.iloc[0]['home_team']} vs {scheduled.iloc[0]['away_team']} in the {scheduled.iloc[0]['stage_label']}."
    if not finished.empty:
        return "Tournament data shows all loaded matches as completed."
    return "Fixtures are loaded, but no live or completed status is available."


def get_top_team_metric(matches_df: pd.DataFrame) -> Tuple[str, str]:
    if matches_df.empty:
        return "—", "No data"
    finished = matches_df[matches_df["status"] == "Finished"]
    if finished.empty:
        return "—", "No finished matches yet"
    attack = []
    for _, r in finished.iterrows():
        if not pd.isna(r.get("home_score")):
            attack.append({"team": r["home_team"], "goals": int(r["home_score"])})
        if not pd.isna(r.get("away_score")):
            attack.append({"team": r["away_team"], "goals": int(r["away_score"])})
    if not attack:
        return "—", "No goals yet"
    team_goals = pd.DataFrame(attack).groupby("team", as_index=False)["goals"].sum().sort_values("goals", ascending=False)
    first = team_goals.iloc[0]
    return str(first["team"]), f"{int(first['goals'])} goals"


def filter_matches(df: pd.DataFrame, team: str = "All", stage: str = "All", status: str = "All", text: str = "") -> pd.DataFrame:
    out = df.copy()
    if team != "All":
        out = out[(out["home_team"] == team) | (out["away_team"] == team)]
    if stage != "All":
        out = out[out["stage_label"] == stage]
    if status != "All":
        out = out[out["status"] == status]
    if text:
        pattern = re.escape(text.strip())
        out = out[out["home_team"].str.contains(pattern, case=False, na=False) | out["away_team"].str.contains(pattern, case=False, na=False) | out["stage_label"].str.contains(pattern, case=False, na=False)]
    return out


def render_standings(standings_df: pd.DataFrame, teams_df: pd.DataFrame) -> None:
    if standings_df.empty:
        st.info("Standings are not available yet. Once group-stage matches or API group tables are loaded, they will appear here.")
        return
    # Add teams that have no calculated matches yet, when team list has group info.
    if not teams_df.empty and all(c in teams_df.columns for c in ["team", "group"]):
        existing = set(zip(standings_df.get("group", []), standings_df.get("team", [])))
        add_rows = []
        for _, t in teams_df.dropna(subset=["group"]).iterrows():
            key = (t.get("group"), t.get("team"))
            if key not in existing and clean_text(t.get("group")) in GROUPS:
                add_rows.append({"group": t.get("group"), "rank": None, "team": t.get("team"), "P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0, "Pts": 0, "source": "team_list"})
        if add_rows:
            standings_df = pd.concat([standings_df, pd.DataFrame(add_rows)], ignore_index=True)

    group_tabs = st.tabs([f"Group {g}" for g in GROUPS])
    for tab, g in zip(group_tabs, GROUPS):
        with tab:
            gdf = standings_df[standings_df["group"].astype(str).str.upper() == g].copy()
            if gdf.empty:
                st.info(f"No data for Group {g} yet.")
                continue
            for col in ["rank", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]:
                if col not in gdf.columns:
                    gdf[col] = 0
            gdf = gdf.sort_values(["Pts", "GD", "GF"], ascending=[False, False, False], na_position="last")
            gdf["Rank"] = range(1, len(gdf) + 1)
            view = gdf[["Rank", "team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]].rename(columns={"team": "Team"})
            st.dataframe(view, use_container_width=True, hide_index=True)
            st.caption("Pts = points. Teams get 3 points for a win, 1 for a draw, 0 for a loss. GD = goals scored minus goals conceded.")


def render_team_route(team: str, matches_df: pd.DataFrame) -> None:
    tdf = filter_matches(matches_df, team=team)
    if tdf.empty:
        st.info("No matches found for this team.")
        return
    st.write(f"#### {team} route")
    for _, row in tdf.iterrows():
        render_match_card(row, compact=True)


def extract_scorers(matches_df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, m in matches_df.iterrows():
        for side in ["home", "away"]:
            team = m.get(f"{side}_team")
            scorers = clean_text(m.get(f"{side}_scorers"))
            if not scorers:
                continue
            # Accept formats like "Messi 23', Alvarez 44'" or simple comma-separated names.
            pieces = re.split(r",|;|\|", scorers)
            for p in pieces:
                name = re.sub(r"\([^)]*\)|\d+['’]?(\+\d+)?", "", p).strip(" -•")
                if name and name.lower() not in {"null", "none", "own goal"}:
                    records.append({"player": name, "team": team, "goals": 1})
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).groupby(["player", "team"], as_index=False)["goals"].sum().sort_values("goals", ascending=False)


def render_live_score_card(row: pd.Series) -> None:
    home = clean_text(row.get("home_team", "TBD"), "TBD")
    away = clean_text(row.get("away_team", "TBD"), "TBD")
    score = scoreline_label(row)
    minute = live_minute(row) or ("FT" if row.get("status") == "Finished" else clean_text(row.get("kickoff", "TBD")))
    progress = timeline_percent(row) if row.get("status") == "Live" else (100 if row.get("status") == "Finished" else 0)
    home_pct = max(0, min(100, progress if row.get("status") == "Live" else 50))
    away_pct = 100 - home_pct if row.get("status") == "Live" else 50
    live_dot = '<span class="wc-live-dot"></span>' if row.get("status") == "Live" else ""
    st.markdown(
        f'''
        <div class="wc-live-card">
          <div>{live_dot}{status_badge(row.get('status', 'Scheduled'))}<span class="tag">{esc(row.get('stage_label',''))}</span><span class="tag">⏱ {esc(minute)}</span></div>
          <div class="wc-live-teams">
            <div class="wc-live-team"><div class="wc-team-name">{team_chip(home)}</div><span class="wc-team-hero-code">{team_code(home)}</span></div>
            <div class="wc-live-score">{esc(score)}</div>
            <div class="wc-live-team"><div class="wc-team-name">{team_chip(away)}</div><span class="wc-team-hero-code">{team_code(away)}</span></div>
          </div>
          <div class="subtle" style="text-align:center;margin-top:8px;">{esc(row.get('kickoff','TBD'))}{' • ' + esc(clean_text(row.get('venue'))) if clean_text(row.get('venue')) else ''}</div>
          <div class="wc-timeline"><div class="wc-timeline-fill" style="width:{progress}%;"></div></div>
          <div class="wc-win-row"><span class="wc-win-home">{home_pct}% {esc(home)}</span><span class="wc-win-away">{esc(away)} {away_pct}%</span></div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

def bracket_card_html(row: pd.Series) -> str:
    home = clean_text(row.get("home_team", "TBD"), "TBD")
    away = clean_text(row.get("away_team", "TBD"), "TBD")
    hs = "-" if pd.isna(row.get("home_score")) else str(int(row.get("home_score")))
    aw = "-" if pd.isna(row.get("away_score")) else str(int(row.get("away_score")))
    winner = clean_text(row.get("winner"))
    home_cls = " wc-bracket-winner" if winner == home else ""
    away_cls = " wc-bracket-winner" if winner == away else ""
    return f'''
      <div class="wc-bracket-card">
        <div style="margin-bottom:5px;">{status_badge(row.get('status', 'Scheduled'))}</div>
        <div class="wc-bracket-team{home_cls}"><span>{team_chip(home)}</span><span class="wc-bracket-score">{hs}</span></div>
        <div class="wc-bracket-team{away_cls}"><span>{team_chip(away)}</span><span class="wc-bracket-score">{aw}</span></div>
        <div class="subtle" style="font-size:.76rem;margin-top:6px;">{row.get('kickoff','TBD')}</div>
      </div>
    '''


def render_bracket_wall(knockout: pd.DataFrame) -> None:
    if knockout.empty:
        st.info("Knockout data is not loaded yet.")
        return
    cols_html = []
    for stage_code in [s for s in STAGE_ORDER if s != "group"]:
        sdf = knockout[knockout["stage"] == stage_code].sort_values("date_time", na_position="last")
        if sdf.empty:
            continue
        cards = "".join(bracket_card_html(row) for _, row in sdf.iterrows())
        cols_html.append(f'''<div class="wc-bracket-col"><div class="wc-bracket-title">{STAGE_LABELS.get(stage_code, stage_code)}</div>{cards}</div>''')
    st.markdown(f'''<div class="wc-bracket-grid">{''.join(cols_html)}</div>''', unsafe_allow_html=True)


def render_dashboard(matches_df: pd.DataFrame, standings_df: pd.DataFrame, source: str) -> None:
    if matches_df.empty:
        st.error("No match data loaded.")
        return

    total_matches = len(matches_df)
    finished = matches_df[matches_df["status"] == "Finished"]
    live = matches_df[matches_df["status"] == "Live"]
    scheduled = matches_df[matches_df["status"] == "Scheduled"]
    total_goals = int(finished["total_goals"].dropna().sum()) if not finished.empty else 0
    avg_goals = total_goals / len(finished) if len(finished) else 0
    top_team, top_value = get_top_team_metric(matches_df)

    render_hero(matches_df, source)
    st.caption(f"Data source: {source} • Last refreshed: {datetime.now().strftime('%I:%M:%S %p')} • Auto-refresh: 60 seconds")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_stat_card("🏟️", total_matches, "Matches loaded")
    with c2:
        render_stat_card("✅", len(finished), "Finished")
    with c3:
        render_stat_card("🔴", len(live), "Live now")
    with c4:
        render_stat_card("⚽", total_goals, f"Goals • {avg_goals:.2f}/match")
    with c5:
        render_stat_card("🔥", top_team, f"Top attack • {top_value}")

    st.progress(min(1.0, len(finished) / max(1, total_matches)), text=f"Tournament progress: {len(finished)} of {total_matches} loaded matches completed")

    st.markdown("### At a glance")
    col_a, col_b = st.columns([1.15, 0.85])
    with col_a:
        st.markdown(f"<div class='explain'><b>Plain-English summary:</b> {explain_current_stage(matches_df)} The winner of each knockout match advances; in the group stage teams advance by points and goal difference.</div>", unsafe_allow_html=True)
        st.write("#### Live / next matches")
        shortlist = pd.concat([live, scheduled]).sort_values("date_time", na_position="last").head(5)
        if shortlist.empty:
            st.info("No live or upcoming matches in the loaded data.")
        for _, row in shortlist.iterrows():
            render_live_score_card(row)
    with col_b:
        st.write("#### Stage status")
        stage_counts = matches_df.groupby(["stage_label", "status"]).size().reset_index(name="matches")
        fig = px.bar(stage_counts, x="stage_label", y="matches", color="status", title="Matches by stage/status", color_discrete_map={"Scheduled":"#38bdf8", "Finished":"#22c55e", "Live":"#ef4444"})
        fig.update_layout(height=360, xaxis_title="Stage", yaxis_title="Matches", legend_title="Status")
        st.plotly_chart(fig, use_container_width=True)

        if not standings_df.empty:
            best_thirds = standings_df[standings_df.get("rank", 0) == 3].sort_values(["Pts", "GD", "GF"], ascending=[False, False, False]).head(8)
            if not best_thirds.empty:
                st.write("#### Best 3rd-place race")
                st.dataframe(best_thirds[["group", "team", "Pts", "GD", "GF"]].rename(columns={"group": "Group", "team": "Team"}), use_container_width=True, hide_index=True)


def render_matches_tab(matches_df: pd.DataFrame) -> None:
    st.header("Matches, scores & fixtures")
    teams = sorted(set(matches_df["home_team"].dropna()) | set(matches_df["away_team"].dropna()))
    stages = [s for s in matches_df["stage_label"].dropna().unique()]
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
    with c1:
        team = st.selectbox("Team", ["All"] + teams)
    with c2:
        stage = st.selectbox("Stage", ["All"] + sorted(stages, key=lambda x: list(STAGE_LABELS.values()).index(x) if x in STAGE_LABELS.values() else 99))
    with c3:
        status = st.selectbox("Status", ["All", "Live", "Scheduled", "Finished"])
    with c4:
        text = st.text_input("Search", placeholder="e.g. Argentina, Final, Brazil")
    filtered = filter_matches(matches_df, team, stage, status, text)
    st.caption(f"Showing {len(filtered)} of {len(matches_df)} matches")
    view_cols = ["kickoff", "stage_label", "status", "home_team", "score", "away_team", "winner", "venue"]
    available = [c for c in view_cols if c in filtered.columns]
    st.dataframe(filtered[available].rename(columns={"kickoff": "Kickoff", "stage_label": "Stage", "status": "Status", "home_team": "Home", "away_team": "Away", "score": "Score", "winner": "Winner", "venue": "Venue"}), use_container_width=True, hide_index=True)

    st.write("#### Match cards")
    for _, row in filtered.head(20).iterrows():
        render_match_card(row)
    if len(filtered) > 20:
        st.caption("Showing first 20 cards. Use the filters above to narrow the list.")


def render_knockout_tab(matches_df: pd.DataFrame) -> None:
    st.header("Knockout bracket explorer")
    st.markdown("Every match is sudden-death: win and advance, lose and go home. If tied after extra time, penalties decide the winner.")
    knockout = matches_df[matches_df["stage"] != "group"].copy()
    if knockout.empty:
        st.info("Knockout data is not loaded yet.")
        return
    st.write("#### Road to the final")
    render_bracket_wall(knockout)
    st.write("#### Round-by-round details")
    tabs = st.tabs([STAGE_LABELS[s] for s in STAGE_ORDER if s != "group" and s in set(knockout["stage"])])
    for tab, stage_code in zip(tabs, [s for s in STAGE_ORDER if s != "group" and s in set(knockout["stage"])]):
        with tab:
            sdf = knockout[knockout["stage"] == stage_code].sort_values("date_time", na_position="last")
            cols = st.columns(2)
            for idx, (_, row) in enumerate(sdf.iterrows()):
                with cols[idx % 2]:
                    render_match_card(row)


def render_teams_tab(matches_df: pd.DataFrame, teams_df: pd.DataFrame, standings_df: pd.DataFrame) -> None:
    st.header("Teams explorer")
    all_teams = sorted(set(teams_df["team"].dropna()) if not teams_df.empty else (set(matches_df["home_team"]) | set(matches_df["away_team"])))
    if not all_teams:
        st.info("No teams loaded.")
        return
    favorite = st.selectbox("Choose a team", all_teams, index=0)

    team_rows = teams_df[teams_df["team"] == favorite] if not teams_df.empty else pd.DataFrame()
    group = clean_text(team_rows.iloc[0].get("group") if not team_rows.empty else "")
    code = clean_text(team_rows.iloc[0].get("code") if not team_rows.empty else "")
    st.subheader(f"{team_flag(favorite)} {favorite} ({team_code(favorite)})")
    if group:
        st.caption(f"Group {group}")

    tmatches = filter_matches(matches_df, team=favorite)
    finished = tmatches[tmatches["status"] == "Finished"]
    wins = int((finished["winner"] == favorite).sum()) if not finished.empty else 0
    goals_for = 0
    goals_against = 0
    for _, r in finished.iterrows():
        if r["home_team"] == favorite:
            goals_for += int(r["home_score"]) if not pd.isna(r["home_score"]) else 0
            goals_against += int(r["away_score"]) if not pd.isna(r["away_score"]) else 0
        elif r["away_team"] == favorite:
            goals_for += int(r["away_score"]) if not pd.isna(r["away_score"]) else 0
            goals_against += int(r["home_score"]) if not pd.isna(r["home_score"]) else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Matches", len(tmatches))
    c2.metric("Wins", wins)
    c3.metric("Goals for", goals_for)
    c4.metric("Goal diff", goals_for - goals_against)

    if group and not standings_df.empty:
        st.write(f"#### Group {group} table")
        gdf = standings_df[standings_df["group"].astype(str).str.upper() == group.upper()].copy()
        if not gdf.empty:
            gdf = gdf.sort_values(["Pts", "GD", "GF"], ascending=[False, False, False], na_position="last")
            gdf["Rank"] = range(1, len(gdf) + 1)
            st.dataframe(gdf[["Rank", "team", "Pts", "GD", "GF", "GA"]].rename(columns={"team": "Team"}), use_container_width=True, hide_index=True)
    render_team_route(favorite, matches_df)


def render_insights_tab(matches_df: pd.DataFrame) -> None:
    st.header("Stats & insights")
    finished = matches_df[matches_df["status"] == "Finished"].copy()
    if finished.empty:
        st.info("Insights will populate once matches are finished.")
        return

    c1, c2, c3 = st.columns(3)
    total_goals = int(finished["total_goals"].dropna().sum())
    over15 = (finished["total_goals"] > 1.5).mean() * 100
    btts = ((finished["home_score"] > 0) & (finished["away_score"] > 0)).mean() * 100
    c1.metric("Goals per match", f"{total_goals / len(finished):.2f}")
    c2.metric("Over 1.5 goals", f"{over15:.0f}%")
    c3.metric("Both teams scored", f"{btts:.0f}%")

    stage_goals = finished.groupby("stage_label", as_index=False).agg(matches=("match_id", "count"), goals=("total_goals", "sum"))
    stage_goals["goals_per_match"] = stage_goals["goals"] / stage_goals["matches"]
    fig = px.bar(stage_goals, x="stage_label", y="goals_per_match", title="Goals per match by stage")
    fig.update_layout(xaxis_title="Stage", yaxis_title="Goals per match", height=380)
    st.plotly_chart(fig, use_container_width=True)

    attack_records = []
    for _, r in finished.iterrows():
        attack_records.append({"team": r["home_team"], "GF": int(r["home_score"]), "GA": int(r["away_score"])})
        attack_records.append({"team": r["away_team"], "GF": int(r["away_score"]), "GA": int(r["home_score"])})
    attack = pd.DataFrame(attack_records).groupby("team", as_index=False).sum()
    attack["GD"] = attack["GF"] - attack["GA"]
    attack = attack.sort_values(["GF", "GD"], ascending=[False, False]).head(12)
    fig2 = px.bar(attack, x="team", y="GF", title="Top scoring teams")
    fig2.update_layout(xaxis_title="Team", yaxis_title="Goals", height=420)
    st.plotly_chart(fig2, use_container_width=True)

    scorelines = finished.assign(scoreline=finished.apply(scoreline_label, axis=1)).groupby("scoreline", as_index=False).size().sort_values("size", ascending=False).head(10)
    fig3 = px.pie(scorelines, values="size", names="scoreline", title="Most common scorelines")
    fig3.update_layout(height=420)
    st.plotly_chart(fig3, use_container_width=True)

    scorers = extract_scorers(matches_df)
    if not scorers.empty:
        st.write("#### Top scorers parsed from available scorer text")
        st.dataframe(scorers.head(20), use_container_width=True, hide_index=True)
    else:
        st.caption("Top-scorer parsing needs scorer/event data from the API. The app will show it when the endpoint includes scorer strings.")


def render_fan_guide() -> None:
    st.header("Simple guide for non-football fans")
    st.markdown(
        """
        **How the World Cup works:**

        1. **Group stage:** teams are split into groups. A win = 3 points, draw = 1, loss = 0.
        2. **Tiebreaker:** if teams have the same points, goal difference usually matters first. Goal difference = goals scored minus goals conceded.
        3. **Knockout stage:** one match decides it. Winner advances. Loser is out.
        4. **Extra time and penalties:** if a knockout match is tied after 90 minutes, it can go to extra time, then penalties.
        5. **What to watch:** live matches, standings movement, who has already qualified, and each team's route to the final.

        **Dashboard reading tips:**

        - Start with **Dashboard** for the current situation.
        - Use **Matches** to check scores and upcoming games.
        - Use **Standings** to understand who is leading each group.
        - Use **Knockout** to see the road to the final.
        - Use **Insights** when you want fan-level stats like goal trends and best attacks.
        """
    )


def render_deploy_notes(api_base: str, source: str) -> None:
    st.header("Deployment & data notes")
    st.write("This app is designed for Streamlit Community Cloud, which hosts public apps from a GitHub repo.")
    st.code(
        """# Local test
pip install -r requirements.txt
streamlit run app.py

# Streamlit Cloud deployment
# 1) Push these files to GitHub
# 2) Go to share.streamlit.io
# 3) Pick repo, branch, app.py
# 4) Deploy
""",
        language="bash",
    )
    st.write("Current API base:", api_base)
    st.write("Current loaded source:", source)
    st.markdown(
        """
        **Optional secrets** for Streamlit Cloud:

        ```toml
        WORLDCUP26_BASE_URL = "https://worldcup26.ir"
        WORLDCUP26_TOKEN = ""  # only needed if your chosen API endpoint requires auth
        ```
        """
    )


def main() -> None:
    st.sidebar.title("⚽ Controls")
    auto_refresh = st.sidebar.toggle("Auto-refresh live view", value=True, help="Reloads the app every 60 seconds during live viewing.")
    if auto_refresh:
        components.html("<script>setTimeout(() => window.parent.location.reload(), 60000)</script>", height=0)
    last_refresh = datetime.now().strftime("%I:%M:%S %p")
    st.sidebar.caption(f"Last refreshed: {last_refresh}")
    api_base = secret("WORLDCUP26_BASE_URL", DEFAULT_API_BASE)
    token = secret("WORLDCUP26_TOKEN", "")
    source_mode = st.sidebar.radio("Data mode", ["Live API", "Demo fallback"], help="Use fallback only for offline demos or when API rate limits/auth blocks access.")
    if st.sidebar.button("Refresh now"):
        st.cache_data.clear()
        st.rerun()

    if source_mode == "Live API":
        matches, teams, groups, stadiums, source = load_live_data(api_base, token)
    else:
        matches, teams, groups, stadiums, source = load_fallback()

    matches = enrich_matches(matches, stadiums)
    global TEAM_FLAG_MAP
    TEAM_FLAG_MAP = build_flag_map(teams)
    calc_table = calculate_standings_from_matches(matches, teams)
    standings = calc_table if not calc_table.empty else groups

    all_teams = sorted(set(matches["home_team"].dropna()) | set(matches["away_team"].dropna())) if not matches.empty else []
    if all_teams:
        favorite = st.sidebar.selectbox("Favorite team quick filter", ["None"] + all_teams)
        if favorite != "None":
            st.sidebar.write("Next/route")
            fdf = filter_matches(matches, team=favorite).sort_values("date_time", na_position="last")
            for _, row in fdf.head(3).iterrows():
                st.sidebar.caption(f"{row['kickoff']} — {row['home_team']} {row['score']} {row['away_team']}")

    st.sidebar.caption("Live games auto-refresh every 60 seconds when enabled.")

    tab_dashboard, tab_matches, tab_standings, tab_knockout, tab_teams, tab_insights, tab_guide, tab_deploy = st.tabs(
        ["Dashboard", "Matches", "Standings", "Knockout", "Teams", "Insights", "New Fan Guide", "Deploy"]
    )
    with tab_dashboard:
        render_dashboard(matches, standings, source)
    with tab_matches:
        render_matches_tab(matches)
    with tab_standings:
        st.header("Group standings")
        st.markdown("Top teams advance from each group; third-place teams can also qualify depending on the tournament format and table ranking.")
        render_standings(standings, teams)
    with tab_knockout:
        render_knockout_tab(matches)
    with tab_teams:
        render_teams_tab(matches, teams, standings)
    with tab_insights:
        render_insights_tab(matches)
    with tab_guide:
        render_fan_guide()
    with tab_deploy:
        render_deploy_notes(api_base, source)


if __name__ == "__main__":
    main()
