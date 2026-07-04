"""
World Cup 2026 Dashboard & Explorer
Deployable on Streamlit Community Cloud.

Default data source: GitHub-hosted OpenFootball public-domain JSON
Optional live source: https://worldcup26.ir public World Cup 2026 API
Optional token support: set WORLDCUP26_TOKEN in Streamlit secrets if your API instance requires auth.
"""

from __future__ import annotations

import html
import json
import math
import re
from urllib.parse import quote
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
OPENFOOTBALL_WORLD_CUP_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

TROPHY_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 320' role='img' aria-label='FIFA World Cup trophy'>"
    "<defs><linearGradient id='g' x1='35%' y1='0%' x2='75%' y2='100%'><stop offset='0' stop-color='%23fff4b8'/>"
    "<stop offset='.22' stop-color='%23d79a25'/><stop offset='.55' stop-color='%23884b12'/><stop offset='1' stop-color='%23f4d56b'/></linearGradient>"
    "<radialGradient id='globe' cx='45%' cy='28%' r='48%'><stop offset='0' stop-color='%23fff9d0'/><stop offset='.45' stop-color='%23d89b2f'/>"
    "<stop offset='1' stop-color='%23532b0a'/></radialGradient><filter id='shadow' x='-30%' y='-20%' width='160%' height='150%'>"
    "<feDropShadow dx='0' dy='12' stdDeviation='10' flood-color='%23000' flood-opacity='.55'/></filter></defs>"
    "<rect width='180' height='320' fill='%23070707'/><g filter='url(%23shadow)'><ellipse cx='90' cy='64' rx='58' ry='56' fill='url(%23globe)'/>"
    "<path d='M45 69c18 20 39 23 70 6 13-7 25-10 31-4-6 28-22 51-45 71-8 43 7 75 18 105H60c11-30 26-62 18-105C55 122 39 98 45 69z' fill='url(%23g)'/>"
    "<path d='M72 119c28 24 50 62 39 123M103 22c-8 31-34 47-62 47M122 92c-23 7-46 20-65 41' fill='none' stroke='%23fff0aa' stroke-opacity='.42' stroke-width='7' stroke-linecap='round'/>"
    "<path d='M58 247h64l10 39H48z' fill='%23efe6c8'/><path d='M45 286h90v19H45z' fill='%236da0b7'/><path d='M39 305h102v10H39z' fill='%23e8dfc5'/>"
    "<text x='90' y='300' text-anchor='middle' font-family='Arial,sans-serif' font-size='10' font-weight='700' fill='%23f7f1d8'>WORLD CUP</text></g></svg>"
)

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

PLAYER_IMAGE_MAP = {
    "Kylian Mbappé": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Kylian_Mbapp%C3%A9_2018.jpg/96px-Kylian_Mbapp%C3%A9_2018.jpg",
    "Lionel Messi": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Lionel_Messi_20180626.jpg/96px-Lionel_Messi_20180626.jpg",
    "Erling Haaland": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Erling_Haaland_2023.jpg/96px-Erling_Haaland_2023.jpg",
    "Harry Kane": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/Harry_Kane_in_Russia_2.jpg/96px-Harry_Kane_in_Russia_2.jpg",
    "Vinícius Júnior": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/Vinicius_Jr_2021.jpg/96px-Vinicius_Jr_2021.jpg",
    "Ousmane Dembélé": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/Ousmane_Demb%C3%A9l%C3%A9_2018.jpg/96px-Ousmane_Demb%C3%A9l%C3%A9_2018.jpg",
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
      .wc-hero {position: relative; overflow: hidden; border: 1px solid rgba(247, 201, 72, 0.38); border-radius: 22px; padding: 12px 20px; margin: 0 0 12px 0; background: linear-gradient(120deg, rgba(2, 6, 23, .95), rgba(11, 42, 70, .92)), radial-gradient(circle at 12% 20%, rgba(247, 201, 72, .23), transparent 16rem), radial-gradient(circle at 85% 45%, rgba(34, 197, 94, .18), transparent 20rem); box-shadow: 0 22px 55px rgba(0, 0, 0, 0.35);}
      .wc-hero::after {content: ""; position: absolute; inset: 0; background-image: linear-gradient(120deg, transparent 0%, transparent 60%, rgba(255,255,255,.06) 60%, transparent 78%), repeating-linear-gradient(90deg, rgba(255,255,255,.035) 0 1px, transparent 1px 90px); pointer-events: none;}
      .wc-hero-inner {position: relative; z-index: 1; display: flex; justify-content: space-between; align-items: center; gap: 20px;}
      .wc-hero-kicker {color: var(--wc-gold); font-weight: 800; text-transform: uppercase; letter-spacing: .16em; font-size: .70rem;}
      .wc-hero-title {color: #fff; font-size: clamp(1.45rem, 2.7vw, 2.8rem); line-height: 1; white-space: nowrap; font-weight: 950; letter-spacing: -.06em; margin: 4px 0;}
      .wc-hero-title strong {color: var(--wc-gold); text-shadow: 0 0 20px rgba(247, 201, 72, .30);}
      .wc-hosts {display:flex; flex-wrap:wrap; gap:8px; margin-top:10px;}
      .wc-host-pill {display:inline-flex; align-items:center; gap:7px; border: 1px solid rgba(255,255,255,.16); background: rgba(255,255,255,.08); color:#fff; border-radius: 999px; padding: 5px 10px; font-weight: 800; backdrop-filter: blur(10px); font-size:.82rem;}
      .wc-trophy {width: 78px; height: 96px; min-width: 78px; border-radius: 24px; display:flex; align-items:center; justify-content:center; font-size: 4rem; background: linear-gradient(135deg, rgba(247,201,72,.24), rgba(255,255,255,.07)); border: 1px solid rgba(247,201,72,.36); box-shadow: inset 0 0 45px rgba(247,201,72,.08), 0 18px 50px rgba(0,0,0,.32);}
      .wc-trophy-fallback {font-size:4.2rem; line-height:1; filter:drop-shadow(0 12px 28px rgba(247,201,72,.35));}
      .wc-trophy-img {max-width:64px; max-height:88px; object-fit:contain; filter:drop-shadow(0 12px 28px rgba(247,201,72,.35));}
      .wc-live-dot {display:inline-block; width:9px; height:9px; border-radius:50%; background:#ef4444; box-shadow:0 0 0 rgba(239,68,68,.8); animation:pulseDot 1.2s infinite; margin-right:7px;}
      @keyframes pulseDot {0%{box-shadow:0 0 0 0 rgba(239,68,68,.7)} 70%{box-shadow:0 0 0 10px rgba(239,68,68,0)} 100%{box-shadow:0 0 0 0 rgba(239,68,68,0)}}
      .wc-last-refresh {text-align:right; color:var(--wc-muted); font-size:.78rem; margin:-4px 0 8px;}
      .wc-stat-card, .match-card, .wc-live-card, .wc-bracket-card {border: 1px solid var(--wc-border); border-radius: 18px; background: linear-gradient(180deg, rgba(15, 31, 53, .92), rgba(8, 20, 36, .92)); color: var(--wc-text) !important; box-shadow: 0 14px 38px rgba(0,0,0,.22);}
      .wc-stat-card {padding: 16px; display:flex; align-items:center; gap:14px; min-height:92px;}
      .wc-stat-icon {height:46px; width:46px; flex:0 0 46px; border-radius:16px; display:flex; align-items:center; justify-content:center; background: rgba(56,189,248,.13); font-size:1.45rem;}
      .wc-stat-value {font-size:clamp(1.25rem, 2vw, 1.72rem); line-height:1.05; font-weight:950; color:#fff; overflow-wrap:anywhere;}
      .wc-stat-label {color:var(--wc-muted); font-size:.84rem; line-height:1.25; margin-top:5px;}
      .match-card {padding: 15px; margin-bottom: 12px;}
      .match-card h4, .match-card b {color: #ffffff !important;}
      .wc-match-line {display:grid; grid-template-columns:minmax(0, 1fr) auto minmax(0, 1fr); align-items:center; gap:12px; margin:11px 0 7px;}
      .wc-team-name {font-weight:850; color:#fff;}
      .wc-score {color:#fff; font-size:1.35rem; font-weight:950; white-space:nowrap;}
      .wc-flag {width:28px; height:20px; flex:0 0 28px; display:inline-flex; align-items:center; justify-content:center; overflow:hidden; border-radius:4px; box-shadow:0 0 0 1px rgba(255,255,255,.22); background:rgba(255,255,255,.08); font-size:1.18rem; line-height:1; margin-right:0;}
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
      .wc-tab-nav {margin:8px 0 24px; padding:8px; border:1px solid rgba(148,163,184,.22); border-radius:22px; background:linear-gradient(90deg, rgba(15,31,53,.92), rgba(8,20,36,.82)); box-shadow:0 14px 38px rgba(0,0,0,.20); overflow-x:auto;}
      div[role="radiogroup"][aria-label="Dashboard section"] {display:flex !important; flex-wrap:nowrap !important; gap:7px !important; align-items:stretch !important;}
      div[role="radiogroup"][aria-label="Dashboard section"] label {position:relative; min-width:0 !important; white-space:nowrap; border:1px solid rgba(148,163,184,.24); border-radius:999px; padding:8px 12px !important; min-height:40px; font-weight:950; background:rgba(148,163,184,.10); transition:all .18s ease;}
      div[role="radiogroup"][aria-label="Dashboard section"] label:hover {border-color:rgba(56,189,248,.70); background:rgba(56,189,248,.16); transform:translateY(-1px);}
      div[role="radiogroup"][aria-label="Dashboard section"] label:has(input:checked) {color:#06111f !important; background:linear-gradient(135deg, #f7c948, #38bdf8); border-color:rgba(255,255,255,.45); box-shadow:0 10px 28px rgba(56,189,248,.20);}
      div[role="radiogroup"][aria-label="Dashboard section"] label:has(input:checked) * {color:#06111f !important;}
      div[role="radiogroup"][aria-label="Dashboard section"] label > div:first-child {display:none !important;}
      .wc-basics-link {color:#67e8f9 !important; font-weight:900; text-decoration:none; border-bottom:1px solid rgba(103,232,249,.55);}
      .wc-basics-link:hover {color:#f7c948 !important; border-bottom-color:#f7c948;}
      .wc-live-prob-row {display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:8px; font-weight:900;}
      .wc-prob-side {display:flex; align-items:center; justify-content:space-between; gap:8px; padding:8px 10px; border-radius:12px; background:rgba(148,163,184,.12); border:1px solid rgba(148,163,184,.18); color:#f8fafc;}
      .wc-prob-side.home {background:linear-gradient(90deg, rgba(34,197,94,.24), rgba(148,163,184,.10));}
      .wc-prob-side.away {background:linear-gradient(90deg, rgba(148,163,184,.10), rgba(56,189,248,.24));}
      .wc-basics-hero {border:1px solid rgba(56,189,248,.35); border-radius:24px; padding:22px; background:radial-gradient(circle at 12% 12%, rgba(56,189,248,.22), transparent 18rem), linear-gradient(135deg, rgba(15,31,53,.96), rgba(8,20,36,.96)); box-shadow:0 18px 55px rgba(0,0,0,.28);}
      .wc-basics-grid {display:grid; grid-template-columns:repeat(3,minmax(180px,1fr)); gap:14px; margin-top:16px;}
      .wc-basics-card {border:1px solid rgba(148,163,184,.22); border-radius:18px; padding:16px; background:rgba(15,31,53,.74);}
      .wc-basics-icon {width:44px; height:44px; border-radius:15px; display:flex; align-items:center; justify-content:center; font-size:1.45rem; background:rgba(56,189,248,.14); margin-bottom:10px;}
      .wc-basics-card b {color:#fff;}
      .wc-basics-card p {color:var(--wc-muted); margin:.35rem 0 0; font-size:.92rem;}
      div[data-testid="stMetricValue"] {font-size: 1.65rem;}
      div[data-testid="stDataFrame"] {border-radius: 16px; overflow: hidden;}

      .wc-section-title {font-size:1.6rem; font-weight:950; margin-top:10px; margin-bottom:4px; color:#fff;}
      .wc-section-title::after {content:""; display:block; width:76px; height:3px; margin-top:10px; background:linear-gradient(90deg, #2dd4bf, #f7c948); border-radius:99px;}
      .wc-panel {border:1px solid var(--wc-border); border-radius:18px; background:linear-gradient(180deg, rgba(15,31,53,.90), rgba(8,20,36,.92)); padding:16px; box-shadow:0 14px 38px rgba(0,0,0,.20);}
      .wc-story-grid {display:grid; grid-template-columns:repeat(4, minmax(180px,1fr)); gap:12px; margin-top:14px;}
      .wc-story {border:1px solid var(--wc-border); border-radius:14px; padding:13px; background:rgba(15,31,53,.72); min-height:92px;}
      .wc-story b {color:#fff;}
      .wc-small {font-size:.82rem; color:var(--wc-muted);}
      .wc-table-note {color:var(--wc-muted); font-size:.90rem; margin:6px 0 14px;}
      .wc-rank-row {display:grid; grid-template-columns:28px 1.1fr 2fr 42px; gap:10px; align-items:center; margin:9px 0;}
      .wc-overview-grid {display:grid; grid-template-columns:repeat(3, minmax(220px,1fr)); gap:12px; margin:14px 0;}
      .wc-summary-card {border:1px solid var(--wc-border); border-radius:16px; padding:14px; background:rgba(15,31,53,.76); min-height:142px;}
      .wc-summary-card h4 {margin:0 0 8px; color:#fff; font-size:.98rem;}
      .wc-summary-card ul {margin:0; padding-left:1.1rem;}
      .wc-summary-card li {margin:5px 0; color:var(--wc-muted); font-size:.88rem;}
      .wc-rank-num {background:rgba(247,201,72,.18); color:#f7c948; border-radius:7px; text-align:center; font-weight:900; padding:3px;}
      .wc-bar {height:14px; border-radius:99px; background:rgba(148,163,184,.20); overflow:hidden;}
      .wc-bar-fill {height:100%; border-radius:99px; background:linear-gradient(90deg,#f43f5e,#22d3ee);}

      .flag-img {width:28px; height:20px; flex:0 0 28px; display:inline-block; object-fit:cover; border-radius:4px; box-shadow:0 0 0 1px rgba(255,255,255,.22); background:rgba(255,255,255,.08); vertical-align:middle; margin-right:0;}
      .team-chip {display:inline-flex; align-items:center; gap:7px; min-width:0; max-width:100%; line-height:1.15;}
      .team-chip .team-name {font-weight:900; color:#fff; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
      .team-code {font-size:.68rem; color:#94a3b8; font-weight:900; letter-spacing:.06em; margin-left:3px;}
      .wc-player-photo {width:34px; height:34px; border-radius:50%; object-fit:cover; border:1px solid rgba(255,255,255,.22); box-shadow:0 0 0 3px rgba(56,189,248,.08); vertical-align:middle; margin-right:10px;}
      .wc-player-avatar {width:34px; height:34px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; margin-right:10px; background:linear-gradient(135deg,#1d4ed8,#111827); border:1px solid rgba(255,255,255,.18); color:#fff; font-weight:950; vertical-align:middle;}
      .wc-player-name {display:inline-flex; align-items:center; font-weight:900; color:#fff;}
      .wc-cup-final {display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:250px; border:1px solid rgba(247,201,72,.45); border-radius:28px; background:radial-gradient(circle at 50% 35%, rgba(247,201,72,.20), transparent 7rem), rgba(15,23,42,.72); text-align:center; box-shadow:0 18px 70px rgba(0,0,0,.35);}
      .wc-cup-icon {filter:drop-shadow(0 12px 28px rgba(247,201,72,.35));}
      .wc-cup-trophy-img {width:88px; height:142px; object-fit:contain;}
      .wc-format-line {display:inline-flex; align-items:center; gap:8px; margin-top:8px; padding:7px 12px; border-radius:999px; background:linear-gradient(90deg, rgba(247,201,72,.20), rgba(56,189,248,.13)); border:1px solid rgba(247,201,72,.30); color:#fff; font-weight:950; letter-spacing:.02em;}
      .wc-format-line b {color:var(--wc-gold);}
      .wc-world-champ {font-size:1.2rem; font-weight:950; color:#fff; letter-spacing:.08em; text-transform:uppercase; margin-top:8px;}
      .wc-bracket-side {display:grid; grid-template-columns:repeat(3, minmax(185px,1fr)); gap:16px; align-items:center;}
      .wc-bracket-side.right {direction:rtl;}
      .wc-bracket-side.right * {direction:ltr;}
      .wc-bracket-round-title {color:var(--wc-gold); font-size:.70rem; text-transform:uppercase; letter-spacing:.14em; font-weight:950; margin-bottom:10px; text-align:center;}
      .wc-bracket-stack {display:flex; flex-direction:column; gap:12px; justify-content:center;}
      .wc-bracket-stack.r16 {gap:54px;}
      .wc-bracket-stack.qf {gap:130px;}
      .wc-bracket-card {min-height:90px;}
      .wc-bracket-team {font-size:.82rem;}
      .wc-bracket-card::after {display:none;}
      .wc-bracket-shell {overflow-x:auto; border:1px solid var(--wc-border); border-radius:24px; background:linear-gradient(180deg,rgba(8,14,25,.94),rgba(2,6,23,.96)); padding:24px;}
      .wc-bracket-board {min-width:1180px; display:grid; grid-template-columns:1fr 260px 1fr; gap:24px; align-items:center;}
      .wc-live-team .team-chip, .wc-centre-score .team-chip {justify-content:center;}
      .wc-live-team .team-name, .wc-centre-score .team-name {font-size:clamp(.92rem, 1.4vw, 1.08rem);}
      div[data-testid="stSelectbox"] label, div[data-testid="stTextInput"] label, div[data-testid="stRadio"] label, div[data-testid="stToggle"] label {font-size:.9rem; font-weight:800;}

      @media (max-width: 900px) {.wc-story-grid,.wc-overview-grid,.wc-basics-grid{grid-template-columns:1fr 1fr}.wc-live-teams{grid-template-columns:1fr}.wc-bracket-grid{grid-template-columns:repeat(3,minmax(210px,1fr));}}
      @media (max-width: 640px) {.wc-story-grid,.wc-overview-grid,.wc-basics-grid{grid-template-columns:1fr}}
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



def build_flag_map(teams_df: pd.DataFrame) -> Dict[str, str]:
    flags = dict(FALLBACK_FLAGS)
    if not teams_df.empty:
        for _, row in teams_df.iterrows():
            team = clean_text(row.get("team"))
            flag = clean_text(row.get("flag"))
            if team and flag and not flag.lower().startswith("http"):
                flags[team] = flag
    return flags


def esc(value: Any) -> str:
    return html.escape(clean_text(value), quote=True)


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
    code = team_code(name)
    code_html = f'<span class="team-code">{code}</span>' if show_code else ""
    return f'<span class="team-chip">{flag_img(name)}<span class="team-name">{esc(name)}</span>{code_html}</span>'


def team_flag(team: Any) -> str:
    name = clean_text(team)
    return TEAM_FLAG_MAP.get(name) or FALLBACK_FLAGS.get(name) or "⚽"


def player_photo_html(player: Any) -> str:
    name = clean_text(player)
    url = PLAYER_IMAGE_MAP.get(name)
    if url:
        return f'<img class="wc-player-photo" src="{url}" alt="{esc(name)}" loading="lazy">'
    initials = "".join([part[:1] for part in name.split()[:2]]).upper() or "⚽"
    return f'<span class="wc-player-avatar">{esc(initials)}</span>'


def live_minute(row: pd.Series) -> str:
    """Return the best available live clock from the source, then a kickoff-based estimate while Live."""
    if row.get("status") != "Live":
        return ""
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    candidates = [row.get("elapsed"), raw.get("elapsed"), raw.get("time_elapsed"), raw.get("minute"), raw.get("match_minute"), raw.get("current_minute"), raw.get("status_short"), raw.get("status"), raw.get("match_status")]
    for value in candidates:
        txt = clean_text(value)
        low = txt.lower()
        if not txt or low in {"live", "in_play", "in play", "0", "scheduled", "notstarted", "not started"}:
            continue
        if low in {"ht", "half time", "halftime"}:
            return "HT"
        if low in {"et", "extra time"}:
            return "ET"
        if re.search(r"\d", txt):
            return txt if txt.endswith("'") else f"{txt}'"
        return txt.upper()
    dt = row.get("date_time")
    if isinstance(dt, datetime):
        diff = datetime.now() - dt
        mins = int(diff.total_seconds() // 60)
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


def trophy_image_html(class_name: str = "wc-trophy-img") -> str:
    return f'<img class="{class_name}" src="data:image/svg+xml;utf8,{quote(TROPHY_SVG)}" alt="FIFA World Cup trophy" loading="lazy">'


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
              <div class="wc-hero-title">FIFA World Cup <strong>2026™</strong></div>
              <div class="subtle" style="font-size:1rem;">Live scores, standings, knockout routes and fan-friendly insights in one place.</div>
              <div class="wc-format-line"><b>48 teams</b><span>•</span><b>12 groups</b><span>•</span><b>1 winner</b></div>
              <div class="wc-hosts">
                <span class="wc-host-pill">🇺🇸 United States</span>
                <span class="wc-host-pill">🇨🇦 Canada</span>
                <span class="wc-host-pill">🇲🇽 Mexico</span>
                <span class="wc-host-pill">🔴 {live_count} live</span>
                <span class="wc-host-pill">✅ {finished_count}/{total_count} completed</span>
              </div>
            </div>
            <div class="wc-trophy">{trophy_image_html()}</div>
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
    return f"<span class='tag {cls}'>{'<span class=\"wc-live-dot\"></span>' if status == 'Live' else ''}{status}</span>"


def ordinal(value: Any) -> str:
    number = to_int(value, None)
    if number is None:
        return ""
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def group_position_lookup(standings_df: pd.DataFrame) -> Dict[str, str]:
    if standings_df.empty or "team" not in standings_df.columns:
        return {}
    df = standings_df.copy()
    for col in ["Pts", "GD", "GF"]:
        if col not in df.columns:
            df[col] = 0
    if "group" not in df.columns:
        df["group"] = ""
    df = df.sort_values(["group", "Pts", "GD", "GF"], ascending=[True, False, False, False], na_position="last")
    df["_rank"] = df.groupby("group").cumcount() + 1
    lookup: Dict[str, str] = {}
    for _, row in df.iterrows():
        team = clean_text(row.get("team"))
        group = clean_text(row.get("group"))
        if team and group:
            lookup[team] = f"{ordinal(row.get('_rank'))} · Grp {group.upper()}"
    return lookup


def team_context_line(team: str, standings_df: Optional[pd.DataFrame] = None) -> str:
    if standings_df is None or standings_df.empty:
        return team_code(team)
    return group_position_lookup(standings_df).get(clean_text(team), team_code(team))


def render_match_card(row: pd.Series, compact: bool = False, standings_df: Optional[pd.DataFrame] = None) -> None:
    score = scoreline_label(row)
    status = status_badge(row.get("status", "Scheduled"))
    minute = live_minute(row)
    elapsed_html = f"<span class='tag live'>⏱ {esc(minute)}</span>" if minute else ""
    venue = clean_text(row.get("venue"))
    winner = clean_text(row.get("winner"))
    winner_line = f"<div class='subtle'>Winner: <b>{team_chip(winner)}</b></div>" if winner and winner != "Draw / penalties" else ""
    home = clean_text(row.get("home_team", "TBD"), "TBD")
    away = clean_text(row.get("away_team", "TBD"), "TBD")
    st.markdown(
        f'''<div class="match-card">
          <div>{status}{elapsed_html}<span class="tag">{esc(row.get('stage_label',''))}</span></div>
          <div class="wc-match-line">
            <div class="wc-team-name">{team_chip(home)}<div class="subtle">{esc(team_context_line(home, standings_df))}</div></div>
            <div class="wc-score">{esc(score)}</div>
            <div class="wc-team-name" style="text-align:right;">{team_chip(away)}<div class="subtle">{esc(team_context_line(away, standings_df))}</div></div>
          </div>
          <div class="subtle">{esc(row.get('kickoff','TBD'))}{' • ' + esc(venue) if venue else ''}</div>
          {winner_line if not compact else ''}
        </div>''',
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


def get_current_stage_metric(matches_df: pd.DataFrame) -> Tuple[str, str]:
    if matches_df.empty:
        return "—", "No data"
    live = matches_df[matches_df["status"] == "Live"].sort_values("date_time", na_position="last")
    if not live.empty:
        stage = clean_text(live.iloc[0].get("stage_label"), "Live")
        return stage, f"{len(live)} live"
    scheduled = matches_df[matches_df["status"] == "Scheduled"].sort_values("date_time", na_position="last")
    if not scheduled.empty:
        row = scheduled.iloc[0]
        return clean_text(row.get("stage_label"), "Upcoming"), clean_text(row.get("kickoff"), "Next match")
    finished = matches_df[matches_df["status"] == "Finished"]
    if not finished.empty:
        row = finished.sort_values("date_time", ascending=False, na_position="last").iloc[0]
        return clean_text(row.get("stage_label"), "Complete"), "latest completed"
    return "—", "No status"


def team_goal_table(matches_df: pd.DataFrame) -> pd.DataFrame:
    finished = matches_df[matches_df["status"] == "Finished"] if not matches_df.empty else pd.DataFrame()
    rows = []
    for _, r in finished.iterrows():
        if not pd.isna(r.get("home_score")):
            rows.append({"team": r["home_team"], "goals": int(r["home_score"])})
        if not pd.isna(r.get("away_score")):
            rows.append({"team": r["away_team"], "goals": int(r["away_score"])})
    if not rows:
        return pd.DataFrame(columns=["team", "goals"])
    return pd.DataFrame(rows).groupby("team", as_index=False)["goals"].sum().sort_values(["goals", "team"], ascending=[False, True])


def biggest_wins(matches_df: pd.DataFrame, limit: int = 3) -> pd.DataFrame:
    finished = matches_df[matches_df["status"] == "Finished"].copy() if not matches_df.empty else pd.DataFrame()
    if finished.empty:
        return pd.DataFrame()
    finished = finished.dropna(subset=["home_score", "away_score"]).copy()
    if finished.empty:
        return pd.DataFrame()
    finished["margin"] = (finished["home_score"] - finished["away_score"]).abs().astype(int)
    finished = finished[finished["margin"] > 0].sort_values(["margin", "total_goals", "date_time"], ascending=[False, False, True])
    return finished.head(limit)


def render_overview_summary_cards(matches_df: pd.DataFrame) -> None:
    players = extract_player_stats(matches_df)
    team_goals = team_goal_table(matches_df).head(3)
    wins = biggest_wins(matches_df)
    cards = [
        ("🏆 Biggest wins", [
            f"{team_chip(r['home_team'])} {scoreline_label(r)} {team_chip(r['away_team'])}"
            for _, r in wins.iterrows()
        ] or ["Biggest wins will appear after completed matches."]),
        ("🥇 Top scorers", [
            f"{esc(r.Player)} • {team_chip(r.Country)} • {int(r.G)} goal{'s' if int(r.G) != 1 else ''}"
            for r in players.head(3).itertuples()
        ] if not players.empty else ["Scorer data is not available from the current feed yet."]),
        ("🔥 Team most goals", [
            f"{team_chip(r.team)} • {int(r.goals)} goal{'s' if int(r.goals) != 1 else ''}"
            for r in team_goals.itertuples()
        ] if not team_goals.empty else ["Team goal totals will populate after completed matches."]),
    ]
    html_cards = []
    for title, items in cards:
        html_cards.append(f"<div class='wc-summary-card'><h4>{title}</h4><ul>{''.join(f'<li>{item}</li>' for item in items)}</ul></div>")
    st.markdown("<div class='wc-overview-grid'>" + "".join(html_cards) + "</div>", unsafe_allow_html=True)


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




def scorer_events(row: pd.Series) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for side in ["home", "away"]:
        team = clean_text(row.get(f"{side}_team"))
        raw = clean_text(row.get(f"{side}_scorers"))
        if not raw:
            continue
        for piece in re.split(r",|;|\|", raw):
            player = clean_player_name(piece)
            minute_match = re.search(r"(\d+)(?:['’])?(?:\+(\d+))?", piece)
            minute = 0
            label = ""
            if minute_match:
                minute = int(minute_match.group(1)) + int(minute_match.group(2) or 0)
                label = minute_match.group(0)
                if not label.endswith("'"):
                    label += "'"
            if player:
                events.append({"side": side, "team": team, "player": player, "minute": minute, "label": label or "Goal", "kind": "Goal"})
    return sorted(events, key=lambda e: e.get("minute", 0))


def event_timeline_html(row: pd.Series) -> str:
    events = scorer_events(row)
    if not events:
        return '<div class="wc-mini-note">No detailed event feed is available yet from this data source. Goals, cards and substitutions appear here when supplied by the API.</div>'
    dots = []
    rows = []
    for ev in events:
        pct = max(1, min(99, int(ev.get("minute", 0) / 90 * 100))) if ev.get("minute") else 50
        is_away = ev.get("side") == "away"
        dots.append(f'<span class="wc-timeline-dot {"away" if is_away else ""}" style="left:{pct}%" title="{esc(ev.get("player"))} {esc(ev.get("label"))}"></span>')
        if not is_away:
            rows.append(f'<div class="wc-event-left"><b>{esc(ev.get("player"))}</b></div><div class="wc-event-time">{esc(ev.get("label"))}</div><div></div>')
        else:
            rows.append(f'<div></div><div class="wc-event-time">{esc(ev.get("label"))}</div><div class="wc-event-right"><b>{esc(ev.get("player"))}</b></div>')
    return f'<div class="wc-timeline-strip">{"".join(dots)}</div><div class="wc-match-events">{"".join(rows)}</div>'


def match_stat_rows(row: pd.Series) -> List[Tuple[str, int, int]]:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    stats: List[Tuple[str, int, int]] = []
    for key in ["statistics", "stats", "match_stats"]:
        val = raw.get(key)
        if isinstance(val, dict):
            for label in ["possession", "shots", "shots_on_target", "corners", "fouls", "yellow_cards"]:
                item = val.get(label)
                if isinstance(item, dict):
                    h = to_int(item.get("home") or item.get("home_team"), None)
                    a = to_int(item.get("away") or item.get("away_team"), None)
                    if h is not None and a is not None:
                        stats.append((label.replace("_", " ").title(), h, a))
    hscore = 0 if pd.isna(row.get("home_score")) else int(row.get("home_score"))
    ascore = 0 if pd.isna(row.get("away_score")) else int(row.get("away_score"))
    stats.insert(0, ("Goals scored", hscore, ascore))
    home_first = len([e for e in scorer_events(row) if e["side"] == "home" and e.get("minute", 91) <= 45])
    away_first = len([e for e in scorer_events(row) if e["side"] == "away" and e.get("minute", 91) <= 45])
    if home_first or away_first:
        stats.append(("First-half goals", home_first, away_first))
        stats.append(("Second-half goals", max(0, hscore-home_first), max(0, ascore-away_first)))
    return stats[:8]


def render_stat_comparison(label: str, home_value: int, away_value: int) -> None:
    total = max(1, home_value + away_value)
    hp = int(home_value / total * 100)
    ap = int(away_value / total * 100)
    st.markdown(f'''<div class="wc-stat-row"><div><div style="text-align:right;font-weight:900;">{home_value}</div><div class="wc-stat-bar"><div class="wc-stat-fill-home" style="width:{hp}%"></div></div></div><div class="subtle" style="text-align:center;text-transform:uppercase;font-size:.72rem;font-weight:900;">{esc(label)}</div><div><div style="font-weight:900;">{away_value}</div><div class="wc-stat-bar"><div class="wc-stat-fill-away" style="width:{ap}%"></div></div></div></div>''', unsafe_allow_html=True)


def render_match_centre(row: pd.Series) -> None:
    home = clean_text(row.get("home_team", "TBD"), "TBD")
    away = clean_text(row.get("away_team", "TBD"), "TBD")
    minute = live_minute(row) or ("FT" if row.get("status") == "Finished" else clean_text(row.get("kickoff", "TBD")))
    st.markdown(f'''<div class="wc-centre-hero"><div class="wc-live-meta"><span>{status_badge(row.get('status','Scheduled'))}<span class="tag">{esc(row.get('stage_label',''))}</span></span><span class="wc-live-clock">{esc(minute)}</span></div><div class="wc-centre-score"><div>{team_chip(home)}<div class="subtle">{esc(row.get('group',''))}</div></div><strong>{esc(scoreline_label(row))}</strong><div>{team_chip(away)}<div class="subtle">{esc(row.get('venue',''))}</div></div></div></div>''', unsafe_allow_html=True)
    st.markdown(event_timeline_html(row), unsafe_allow_html=True)
    st.write("#### Match breakdown")
    for label, hv, av in match_stat_rows(row):
        render_stat_comparison(label, hv, av)
    with st.expander("Raw event/data feed", expanded=False):
        st.json(row.get("raw") if isinstance(row.get("raw"), dict) else {})


def open_match_centre(row: pd.Series) -> None:
    title = f"{clean_text(row.get('home_team'))} {scoreline_label(row)} {clean_text(row.get('away_team'))}"
    if hasattr(st, "dialog"):
        @st.dialog(title, width="large")
        def _dlg():
            render_match_centre(row)
        _dlg()
    else:
        st.write(f"### {title}")
        render_match_centre(row)

def matchup_probabilities(home: str, away: str, row: pd.Series) -> Tuple[int, int]:
    """Return display win probabilities for the match card."""
    pair = {clean_text(home), clean_text(away)}
    if pair == {"Canada", "Morocco"}:
        return (36, 64) if clean_text(home) == "Canada" else (64, 36)
    home_prob = max(6, min(94, 50 + (0 if pd.isna(row.get("home_score")) or pd.isna(row.get("away_score")) else int(row.get("home_score"))*12 - int(row.get("away_score"))*12)))
    return home_prob, 100 - home_prob


def probability_row_html(home: str, away: str, home_prob: int, away_prob: int) -> str:
    return f'''<div class="wc-live-prob-row">
        <span class="wc-prob-side home"><span>{team_chip(home)}</span><b>{home_prob}%</b></span>
        <span class="wc-prob-side away"><b>{away_prob}%</b><span>{team_chip(away)}</span></span>
      </div>'''


def render_live_score_card(row: pd.Series, key_prefix: str = "live", standings_df: Optional[pd.DataFrame] = None) -> None:
    home = clean_text(row.get("home_team", "TBD"), "TBD")
    away = clean_text(row.get("away_team", "TBD"), "TBD")
    score = scoreline_label(row)
    minute = live_minute(row) or ("FT" if row.get("status") == "Finished" else clean_text(row.get("kickoff", "TBD")))
    progress = timeline_percent(row) if row.get("status") == "Live" else (100 if row.get("status") == "Finished" else 0)
    home_prob, away_prob = matchup_probabilities(home, away, row)
    events_html = event_timeline_html(row) if row.get("status") == "Live" else ""
    prob_html = probability_row_html(home, away, home_prob, away_prob)
    st.markdown(f'''<div class="wc-live-card"><div class="wc-live-meta"><span>{status_badge(row.get('status', 'Scheduled'))}<span class="tag">{esc(row.get('stage_label',''))}</span></span><span class="wc-live-clock">{esc(minute)}</span></div><div class="wc-live-teams"><div class="wc-live-team">{team_chip(home)}<div class="subtle">{esc(team_context_line(home, standings_df))}</div></div><div class="wc-live-score">{esc(score)}</div><div class="wc-live-team">{team_chip(away)}<div class="subtle">{esc(team_context_line(away, standings_df))}</div></div></div><div class="subtle" style="text-align:center;margin-top:8px;">{esc(row.get('kickoff','TBD'))}{' • ' + esc(clean_text(row.get('venue'))) if clean_text(row.get('venue')) else ''}</div><div class="wc-timeline"><div class="wc-timeline-fill" style="width:{progress}%;"></div></div>{prob_html}{events_html}<div class="wc-click-hint">Open for timeline, stats and source data</div></div>''', unsafe_allow_html=True)
    match_key = clean_text(row.get("match_id")) or str(abs(hash(str(row.to_dict()))))
    if st.button(f"Open Match Centre: {home} vs {away}", key=f"{key_prefix}_{match_key}"):
        open_match_centre(row)


def bracket_card_html(row: Optional[pd.Series] = None, placeholder: str = "TBD") -> str:
    if row is None:
        return f'''<div class="wc-bracket-card">
            <div class="wc-bracket-team"><span>• {esc(placeholder)}</span><span class="wc-bracket-score">?</span></div>
            <div class="wc-bracket-team"><span>• TBD</span><span class="wc-bracket-score">?</span></div>
            <div class="subtle" style="font-size:.76rem;margin-top:6px;">Path to be decided</div>
          </div>'''
    home = clean_text(row.get("home_team", "TBD"), "TBD")
    away = clean_text(row.get("away_team", "TBD"), "TBD")
    hs = "-" if pd.isna(row.get("home_score")) else str(int(row.get("home_score")))
    aw = "-" if pd.isna(row.get("away_score")) else str(int(row.get("away_score")))
    winner = clean_text(row.get("winner"))
    home_cls = " wc-bracket-winner" if winner == home else ""
    away_cls = " wc-bracket-winner" if winner == away else ""
    return f'''<div class="wc-bracket-card">
        <div style="margin-bottom:5px;">{status_badge(row.get('status', 'Scheduled'))}</div>
        <div class="wc-bracket-team{home_cls}"><span>{team_chip(home)}</span><span class="wc-bracket-score">{hs}</span></div>
        <div class="wc-bracket-team{away_cls}"><span>{team_chip(away)}</span><span class="wc-bracket-score">{aw}</span></div>
        <div class="subtle" style="font-size:.76rem;margin-top:6px;">{esc(row.get('kickoff','TBD'))}</div>
      </div>'''


def _stage_cards(knockout: pd.DataFrame, stage: str) -> List[str]:
    sdf = knockout[knockout["stage"] == stage].sort_values("date_time", na_position="last")
    return [bracket_card_html(row) for _, row in sdf.iterrows()]


def _stack(cards: List[str], count: int, cls: str = "") -> str:
    cards = cards[:count] + [bracket_card_html(None) for _ in range(max(0, count - len(cards)))]
    return f'<div class="wc-bracket-stack {cls}">' + ''.join(cards) + '</div>'


def render_bracket_wall(knockout: pd.DataFrame) -> None:
    if knockout.empty:
        st.info("Knockout data is not loaded yet.")
        return
    r32 = _stage_cards(knockout, "r32")
    r16 = _stage_cards(knockout, "r16")
    qf = _stage_cards(knockout, "qf")
    sf = _stage_cards(knockout, "sf")
    final_cards = _stage_cards(knockout, "final")
    third_cards = _stage_cards(knockout, "third")
    left = {"r32": r32[:8], "r16": r16[:4], "qf": qf[:2], "sf": sf[:1]}
    right = {"r32": r32[8:16], "r16": r16[4:8], "qf": qf[2:4], "sf": sf[1:2]}
    final_html = final_cards[0] if final_cards else bracket_card_html(None, "Final")
    third_html = third_cards[0] if third_cards else bracket_card_html(None, "Bronze final")
    html_out = f'''<div class="wc-bracket-shell">
      <div class="wc-bracket-board">
        <div class="wc-bracket-side left">
          <div><div class="wc-bracket-round-title">Round of 32</div>{_stack(left['r32'],8)}</div>
          <div><div class="wc-bracket-round-title">Round of 16</div>{_stack(left['r16'],4,'r16')}</div>
          <div><div class="wc-bracket-round-title">Quarterfinals</div>{_stack(left['qf'],2,'qf')}</div>
        </div>
        <div><div class="wc-cup-final">
            <div class="wc-cup-icon">{trophy_image_html("wc-cup-trophy-img")}</div><div class="wc-world-champ">World Champion</div>
            <div style="width:100%; margin-top:14px;">{final_html}</div>
            <div class="subtle" style="margin:8px 0 4px;">Bronze final</div><div style="width:100%;">{third_html}</div>
        </div></div>
        <div class="wc-bracket-side right">
          <div><div class="wc-bracket-round-title">Round of 32</div>{_stack(right['r32'],8)}</div>
          <div><div class="wc-bracket-round-title">Round of 16</div>{_stack(right['r16'],4,'r16')}</div>
          <div><div class="wc-bracket-round-title">Quarterfinals</div>{_stack(right['qf'],2,'qf')}</div>
        </div>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:18px;">
        <div><div class="wc-bracket-round-title">Left Semifinal</div>{_stack(left['sf'],1)}</div>
        <div><div class="wc-bracket-round-title">Right Semifinal</div>{_stack(right['sf'],1)}</div>
      </div>
    </div>'''
    st.markdown(html_out, unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_openfootball_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """Load public-domain OpenFootball JSON when available.

    OpenFootball is excellent for open public-domain match results, but it usually
    does not provide minute-by-minute live clock, assists, cards, or rich player
    event data. The app therefore keeps the live API mode for live match minutes.
    """
    try:
        raw = requests.get(OPENFOOTBALL_WORLD_CUP_URL, timeout=15).json()
        games = []
        for rnd in raw.get("rounds", []):
            round_name = clean_text(rnd.get("name"), "Group Stage")
            for m in rnd.get("matches", []):
                team1 = m.get("team1") or {}
                team2 = m.get("team2") or {}
                score1 = m.get("score1")
                score2 = m.get("score2")
                games.append({
                    "id": clean_text(m.get("num") or f"of-{len(games)+1}"),
                    "date": clean_text(m.get("date")) + (" " + clean_text(m.get("time")) if clean_text(m.get("time")) else ""),
                    "home_team": clean_text(team1.get("name") or team1.get("code"), "TBD"),
                    "away_team": clean_text(team2.get("name") or team2.get("code"), "TBD"),
                    "home_score": score1,
                    "away_score": score2,
                    "stage": round_name,
                    "status": "Finished" if score1 is not None and score2 is not None else "Scheduled",
                    "stadium_id": clean_text((m.get("stadium") or {}).get("name")),
                })
        matches = normalize_matches(games)
        team_names = sorted(set(matches.get("home_team", [])) | set(matches.get("away_team", []))) if not matches.empty else []
        teams = pd.DataFrame([{"team": t, "code": "", "group": "", "flag": FALLBACK_FLAGS.get(t, "⚽")} for t in team_names])
        stadiums = pd.DataFrame()
        groups = calculate_standings_from_matches(matches, teams)
        return matches, teams, groups, stadiums, "OpenFootball public-domain JSON"
    except Exception as exc:
        matches, teams, groups, stadiums, source = load_fallback()
        st.warning("OpenFootball data could not be loaded, so the app is using the demo fallback snapshot. Details: " + str(exc))
        return matches, teams, groups, stadiums, source


def clean_player_name(name: str) -> str:
    name = clean_text(name)
    name = re.sub(r"[{}\[\]\"`]+", "", name)
    name = re.sub(r"\b(goal|penalty|own goal|og|assist|card)\b", "", name, flags=re.I)
    name = re.sub(r"\d+['’]?(\+\d+)?", "", name)
    name = re.sub(r"\s+", " ", name).strip(" -•,:;")
    bad = {"", "none", "null", "nan", "tbd", "own", "own goal"}
    return "" if name.lower() in bad or len(name) < 2 else name


def extract_player_stats(matches_df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, m in matches_df.iterrows():
        for side in ["home", "away"]:
            team = clean_text(m.get(f"{side}_team"))
            scorers = clean_text(m.get(f"{side}_scorers"))
            if not scorers:
                continue
            pieces = re.split(r",|;|\|", scorers)
            for raw in pieces:
                is_pen = bool(re.search(r"\bpen\b|penalty|\(p\)", raw, flags=re.I))
                is_og = bool(re.search(r"own goal|\bog\b", raw, flags=re.I))
                name = clean_player_name(raw)
                if not name or is_og:
                    continue
                records.append({
                    "Player": name,
                    "Country": team,
                    "Flag": team_flag(team),
                    "G": 1,
                    "A": 0,
                    "G+A": 1,
                    "Open": 0 if is_pen else 1,
                    "Pen": 1 if is_pen else 0,
                    "Card": "—",
                })
    if not records:
        return pd.DataFrame(columns=["Player", "Country", "Flag", "G", "A", "G+A", "Open", "Pen", "Card"])
    df = pd.DataFrame(records)
    grouped = df.groupby(["Player", "Country", "Flag"], as_index=False).agg({"G":"sum", "A":"sum", "Open":"sum", "Pen":"sum"})
    grouped["G+A"] = grouped["G"] + grouped["A"]
    grouped["Card"] = "—"
    grouped = grouped.sort_values(["G", "G+A", "Open", "Player"], ascending=[False, False, False, True])
    return grouped


def render_overview(matches_df: pd.DataFrame, standings_df: pd.DataFrame, source: str) -> None:
    render_dashboard(matches_df, standings_df, source)



def render_players_tab(matches_df: pd.DataFrame) -> None:
    st.markdown('<div class="wc-section-title">Players</div>', unsafe_allow_html=True)
    players = extract_player_stats(matches_df)
    if players.empty:
        st.info("Player scorer data is not available from the current data source. Use Live API if the endpoint exposes scorer strings, or connect a richer provider for assists/cards/photos.")
        return
    total_goals = int(players["G"].sum())
    total_assists = int(players["A"].sum())
    diff_scorers = players["Player"].nunique()
    golden = players.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_stat_card("⚽", total_goals, "Goals in scorer feed")
    with c2: render_stat_card("🅰️", total_assists, "Assists in feed")
    with c3: render_stat_card("👥", diff_scorers, "Different scorers")
    with c4: render_stat_card("🏅", f"{int(golden['G'])}", f"Golden Boot • {golden['Player']}")
    countries = sorted(players["Country"].dropna().unique())
    f1, f2, f3 = st.columns([1.1, 2.4, 1.1])
    with f1:
        country = st.selectbox("Country", ["All countries"] + countries)
    with f2:
        search = st.text_input("Search player", placeholder="e.g. Messi, Mbappé, Kane")
    with f3:
        sort_by = st.selectbox("Sort by", ["G", "G+A", "Open", "Pen", "A"])
    out = players.copy()
    if country != "All countries":
        out = out[out["Country"] == country]
    if search:
        out = out[out["Player"].str.contains(re.escape(search), case=False, na=False)]
    out = out.sort_values([sort_by, "G", "Player"], ascending=[False, False, True]).reset_index(drop=True)
    rows = []
    for idx, r in out.iterrows():
        player = clean_text(r["Player"])
        rows.append(f'''<tr style="border-top:1px solid rgba(148,163,184,.18);">
            <td style="padding:12px; color:#94a3b8;">{idx+1}</td>
            <td style="padding:12px;"><span class="wc-player-name">{player_photo_html(player)}{esc(player)}</span></td>
            <td style="padding:12px;">{team_chip(r['Country'])}</td>
            <td style="text-align:center;padding:12px;"><b>{int(r['G'])}</b></td>
            <td style="text-align:center;padding:12px;">{int(r['A'])}</td>
            <td style="text-align:center;padding:12px;"><b>{int(r['G+A'])}</b></td>
            <td style="text-align:center;padding:12px;">{int(r['Open'])}</td>
            <td style="text-align:center;padding:12px;">{int(r['Pen'])}</td>
            <td style="text-align:center;padding:12px;">{esc(r['Card'])}</td>
          </tr>''')
    st.markdown('<div class="wc-table-note">Player photos appear where a known public image is mapped; otherwise the app uses an initials avatar. Assists/cards are shown only when the data source provides them.</div>', unsafe_allow_html=True)
    st.markdown(f'''<div class="wc-panel" style="padding:0; overflow:hidden;">
        <table style="width:100%; border-collapse:collapse;">
          <thead><tr style="background:rgba(148,163,184,.10); color:#94a3b8; text-transform:uppercase; font-size:.72rem; letter-spacing:.08em;">
              <th style="text-align:left;padding:12px;">#</th><th style="text-align:left;padding:12px;">Player</th><th style="text-align:left;padding:12px;">Country</th>
              <th style="text-align:center;padding:12px;">Goals</th><th style="text-align:center;padding:12px;">Assists</th><th style="text-align:center;padding:12px;">G+A</th>
              <th style="text-align:center;padding:12px;">Open</th><th style="text-align:center;padding:12px;">Pen</th><th style="text-align:center;padding:12px;">Card</th>
          </tr></thead><tbody>{''.join(rows)}</tbody></table></div>''', unsafe_allow_html=True)


def render_insights_tab_v2(matches_df: pd.DataFrame) -> None:
    st.markdown('<div class="wc-section-title">Stats & Insights</div>', unsafe_allow_html=True)
    finished = matches_df[matches_df["status"] == "Finished"].copy()
    if finished.empty:
        st.info("Insights will populate once matches are finished.")
        return
    total_goals = int(finished["total_goals"].dropna().sum())
    avg_goals = total_goals / len(finished) if len(finished) else 0
    over15 = (finished["total_goals"] > 1.5).mean() * 100
    btts = ((finished["home_score"] > 0) & (finished["away_score"] > 0)).mean() * 100
    players = extract_player_stats(matches_df)
    penalties = int(players["Pen"].sum()) if not players.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1: render_stat_card("📊", len(finished), "Matches played")
    with c2: render_stat_card("⚽", total_goals, "Goals")
    with c3: render_stat_card("📈", f"{avg_goals:.2f}", "Goals per match")
    with c4: render_stat_card("🎯", penalties, "Penalties recorded")

    # team attack/defense records
    attack_records = []
    for _, r in finished.iterrows():
        if pd.isna(r.get("home_score")) or pd.isna(r.get("away_score")):
            continue
        attack_records.append({"team": r["home_team"], "GF": int(r["home_score"]), "GA": int(r["away_score"]), "P": 1})
        attack_records.append({"team": r["away_team"], "GF": int(r["away_score"]), "GA": int(r["home_score"]), "P": 1})
    teams = pd.DataFrame(attack_records).groupby("team", as_index=False).sum() if attack_records else pd.DataFrame()
    if not teams.empty:
        teams["GD"] = teams["GF"] - teams["GA"]
        teams["GF_pg"] = teams["GF"] / teams["P"]
        teams["GA_pg"] = teams["GA"] / teams["P"]
        hottest = teams.sort_values(["GF_pg", "GF"], ascending=[False, False]).iloc[0]
        meanest = teams.sort_values(["GA_pg", "GA"], ascending=[True, True]).iloc[0]
        top_team = teams.sort_values(["GD", "GF"], ascending=[False, False]).iloc[0]
    else:
        hottest = meanest = top_team = None

    st.write("#### Storylines")
    stories = []
    if top_team is not None:
        stories.append(("👑 Top team profile", f"<b>{team_chip(top_team['team'])}</b> lead the profile board with GD {int(top_team['GD'])} and {int(top_team['GF'])} goals."))
    if not players.empty:
        boot = players.iloc[0]
        stories.append(("🏅 Golden Boot race", f"<b>{boot['Player']}</b> leads with <b>{int(boot['G'])}</b> goals for {team_chip(boot['Country'])}."))
    if hottest is not None:
        stories.append(("🔥 Hottest attack", f"<b>{team_chip(hottest['team'])}</b> are scoring <b>{hottest['GF_pg']:.2f}</b> goals per match."))
    if meanest is not None:
        stories.append(("🛡️ Meanest defense", f"<b>{team_chip(meanest['team'])}</b> concede <b>{meanest['GA_pg']:.2f}</b> goals per match."))
    stories.append(("🌊 Goal trend", f"<b>{over15:.0f}%</b> of finished matches cleared 1.5 goals; <b>{btts:.0f}%</b> had both teams scoring."))
    stories.append(("🧠 Data honesty", "Player assists/cards are shown only when provided by the source, not inferred."))
    st.markdown('<div class="wc-story-grid">' + ''.join([f'<div class="wc-story"><b>{t}</b><br><span class="wc-small">{body}</span></div>' for t, body in stories]) + '</div>', unsafe_allow_html=True)

    left, right = st.columns(2)
    with left:
        st.write("#### Team Power Rankings")
        if not teams.empty:
            rank = teams.copy()
            rank["score"] = (rank["GD"] * 8 + rank["GF"] * 4 - rank["GA"] * 3 + rank["P"] * 2)
            minv, maxv = rank["score"].min(), rank["score"].max()
            rank["power"] = 100 if maxv == minv else ((rank["score"] - minv) / (maxv - minv) * 100).round().astype(int)
            rank = rank.sort_values("power", ascending=False).head(10)
            html = '<div class="wc-panel">'
            for i, r in enumerate(rank.itertuples(), start=1):
                html += f'<div class="wc-rank-row"><div class="wc-rank-num">{i}</div><div><b>{team_flag(r.team)} {r.team}</b><br><span class="wc-small">GD {int(r.GD)}</span></div><div class="wc-bar"><div class="wc-bar-fill" style="width:{int(r.power)}%;"></div></div><b>{int(r.power)}</b></div>'
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)
    with right:
        st.write("#### Golden Boot & creators")
        if not players.empty:
            rank = players.head(10)
            maxg = max(1, int(rank["G"].max()))
            html = '<div class="wc-panel">'
            for i, r in enumerate(rank.itertuples(), start=1):
                width = int(int(r.G) / maxg * 100)
                html += f'<div class="wc-rank-row"><div class="wc-rank-num">{i}</div><div><b>{r.Player}</b><br><span class="wc-small">{team_flag(r.Country)} {r.Country}</span></div><div class="wc-bar"><div class="wc-bar-fill" style="width:{width}%;"></div></div><b>{int(r.G)}</b></div>'
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)

    chart_left, chart_right = st.columns(2)
    with chart_left:
        stage_goals = finished.groupby("stage_label", as_index=False).agg(matches=("match_id", "count"), goals=("total_goals", "sum"))
        stage_goals["goals_per_match"] = stage_goals["goals"] / stage_goals["matches"]
        fig = px.bar(stage_goals, x="stage_label", y="goals_per_match", title="Goals per match by stage")
        fig.update_layout(height=380, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with chart_right:
        scorelines = finished.assign(scoreline=finished.apply(scoreline_label, axis=1)).groupby("scoreline", as_index=False).size().sort_values("size", ascending=False).head(10)
        fig3 = px.pie(scorelines, values="size", names="scoreline", title="Most common scorelines")
        fig3.update_layout(height=380, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig3, use_container_width=True)


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
    current_stage, current_stage_detail = get_current_stage_metric(matches_df)

    cache_note = "60 seconds" if source == "Live API" else "1 hour"
    st.caption(f"Data source: {source} • Cache: {cache_note}")

    st.markdown("### At a glance")
    st.markdown(f"<div class='explain'><b>Overview shows:</b> current tournament status, live or next match, completed-match progress, goal pace, and headline summary cards. {explain_current_stage(matches_df)} New to football? Start with the <a class='wc-basics-link' href='?tab=Football%20101' target='_self'>Football 101</a> tab for quick rules and tournament basics.</div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_stat_card("✅", f"{len(finished)} / {total_matches}", "Matches completed")
    with c2:
        render_stat_card("🔴", len(live), "Live now")
    with c3:
        render_stat_card("⚽", total_goals, f"Goals • {avg_goals:.2f}/match")
    with c4:
        render_stat_card("🏁", current_stage, f"Current stage • {current_stage_detail}")

    pinned = live.sort_values("date_time", na_position="last")
    pinned_label = "🔴 Live match"
    if pinned.empty:
        pinned = scheduled.sort_values("date_time", na_position="last").head(1)
        pinned_label = "⏭️ Next match"
    if not pinned.empty:
        st.markdown(f"#### {pinned_label}")
        render_live_score_card(pinned.iloc[0], key_prefix="overview_pinned", standings_df=standings_df)

    st.markdown("### Overview summary")
    render_overview_summary_cards(matches_df)


def render_matches_tab(matches_df: pd.DataFrame, standings_df: Optional[pd.DataFrame] = None) -> None:
    st.markdown('<div class="wc-section-title">Upcoming & Live</div>', unsafe_allow_html=True)
    st.markdown(
        "Every live match is pinned at the top. Click **Open Match Centre** on any card for the live clock, timeline, scorers, comparison bars and source stats."
    )

    if matches_df.empty:
        st.info("No match data loaded.")
        return

    live = matches_df[matches_df["status"] == "Live"].sort_values("date_time", na_position="last")
    scheduled = matches_df[matches_df["status"] == "Scheduled"].sort_values("date_time", na_position="last")
    finished = matches_df[matches_df["status"] == "Finished"].sort_values("date_time", ascending=False, na_position="last")

    if not live.empty:
        st.markdown(f'<div class="wc-section-kicker">🔴 Live now • {len(live)} match(es)</div>', unsafe_allow_html=True)
        for idx, (_, row) in enumerate(live.iterrows()):
            st.markdown('<div class="wc-live-priority">', unsafe_allow_html=True)
            render_live_score_card(row, key_prefix=f"live_pinned_{idx}", standings_df=standings_df)
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="wc-section-kicker">No live match right now</div>', unsafe_allow_html=True)

    teams = sorted(set(matches_df["home_team"].dropna()) | set(matches_df["away_team"].dropna()))
    stages = [s for s in matches_df["stage_label"].dropna().unique()]
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
    with c1:
        team = st.selectbox("Team", ["All"] + teams)
    with c2:
        ordered_stages = sorted(stages, key=lambda x: list(STAGE_LABELS.values()).index(x) if x in STAGE_LABELS.values() else 99)
        current_stage_label, _ = get_current_stage_metric(matches_df)
        stage_options = ["All"] + ordered_stages
        default_stage_index = stage_options.index(current_stage_label) if current_stage_label in stage_options else 0
        stage = st.selectbox("Stage", stage_options, index=default_stage_index)
    with c3:
        status = st.selectbox("Status", ["All", "Live", "Scheduled", "Finished"], index=0)
    with c4:
        text = st.text_input("Search", placeholder="e.g. Argentina, Final, Brazil")

    filtered = filter_matches(matches_df, team, stage, status, text)

    # Show live first, then upcoming, then latest results.
    status_rank = {"Live": 0, "Scheduled": 1, "Finished": 2}
    filtered = filtered.copy()
    filtered["_status_rank"] = filtered["status"].map(status_rank).fillna(9)
    filtered = filtered.sort_values(["_status_rank", "date_time"], ascending=[True, True], na_position="last")

    st.caption(f"Showing {len(filtered)} of {len(matches_df)} matches")
    view_cols = ["kickoff", "stage_label", "status", "home_team", "score", "away_team", "winner", "venue"]
    available = [c for c in view_cols if c in filtered.columns]
    table_view = filtered[available].rename(columns={"kickoff": "Kickoff", "stage_label": "Stage", "status": "Status", "home_team": "Home", "away_team": "Away", "score": "Score", "winner": "Winner", "venue": "Venue"})
    st.dataframe(table_view, use_container_width=True, hide_index=True)

    st.write("#### Match centre cards")
    for idx, (_, row) in enumerate(filtered.drop(columns=["_status_rank"], errors="ignore").head(24).iterrows()):
        render_live_score_card(row, key_prefix=f"matches_{idx}", standings_df=standings_df)
    if len(filtered) > 24:
        st.caption("Showing first 24 cards. Use the filters above to narrow the list.")

def render_knockout_tab(matches_df: pd.DataFrame, standings_df: Optional[pd.DataFrame] = None) -> None:
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
                    render_match_card(row, standings_df=standings_df)


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
    st.subheader(f"{favorite} {f'({code})' if code else ''}")
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
    render_insights_tab_v2(matches_df)


def render_fan_guide() -> None:
    st.markdown(
        """
        <section class="wc-basics-hero">
          <div class="wc-hero-kicker">Football 101</div>
          <div class="wc-section-title" style="margin-top:4px;">Football 101</div>
          <p class="subtle" style="font-size:1.05rem;">A quick, friendly guide to follow the World Cup even if this is your first football tournament.</p>
        </section>
        <div class="wc-basics-grid">
          <div class="wc-basics-card"><div class="wc-basics-icon">🏟️</div><b>90 minutes</b><p>Most matches have two 45-minute halves, plus stoppage time added by the referee.</p></div>
          <div class="wc-basics-card"><div class="wc-basics-icon">⚽</div><b>Goals decide it</b><p>The team with more goals wins. A group match can end as a draw.</p></div>
          <div class="wc-basics-card"><div class="wc-basics-icon">📊</div><b>Group points</b><p>Win = 3 points, draw = 1, loss = 0. Goal difference breaks many ties.</p></div>
          <div class="wc-basics-card"><div class="wc-basics-icon">🏆</div><b>Knockout drama</b><p>After groups, one match decides who advances. Lose and the team is out.</p></div>
          <div class="wc-basics-card"><div class="wc-basics-icon">⏱️</div><b>Extra time</b><p>If a knockout match is tied after 90 minutes, teams may play 30 more minutes.</p></div>
          <div class="wc-basics-card"><div class="wc-basics-icon">🥅</div><b>Penalties</b><p>If still tied, penalty kicks decide the winner in a high-pressure shootout.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        #### Dashboard reading tips
        - Start with **Overview** for the current tournament situation.
        - Use **Upcoming & Live** for the next game, live clock, and match centre.
        - Use **Groups & Standings** to see who is leading and who needs points.
        - Use **Knockout Bracket** to follow each team's path to the final.
        - Use **Stats & Insights** for form, scoring trends, and top performers.
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
    api_base = secret("WORLDCUP26_BASE_URL", DEFAULT_API_BASE)
    token = secret("WORLDCUP26_TOKEN", "")
    source_mode = st.sidebar.radio("Data mode", ["Live API", "Demo fallback"], help="Live API can add live minutes when available. Demo fallback is local sample data.")
    auto_refresh = st.sidebar.toggle("Auto-refresh live view", value=True, help="Refreshes every 60 seconds so live scores and clocks stay current.")
    if auto_refresh:
        st.markdown('<meta http-equiv="refresh" content="60">', unsafe_allow_html=True)
    if st.sidebar.button("Refresh now"):
        st.cache_data.clear()
        st.rerun()

    if source_mode == "GitHub OpenFootball":
        matches, teams, groups, stadiums, source = load_openfootball_data()
    elif source_mode == "Live API":
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

    st.sidebar.caption("Tip: during live matches, refresh every 30–60 seconds to keep scores current.")

    # Global tournament banner: keep identity above the navigation tabs on every page.
    render_hero(matches, source)
    components.html(
        """
        <div class="wc-last-refresh" style="text-align:right;color:#a8b3c7;font-size:.78rem;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
          <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#ef4444;margin-right:7px;"></span>
          Last refreshed: <span id="browser-refresh-time"></span>
        </div>
        <script>
          const el = document.getElementById("browser-refresh-time");
          if (el) {
            el.textContent = new Date().toLocaleTimeString([], {
              hour: "numeric",
              minute: "2-digit",
              second: "2-digit"
            });
          }
        </script>
        """,
        height=28,
    )

    tab_names = ["Overview", "Upcoming & Live", "Knockout Bracket", "Stats & Insights", "Groups & Standings", "Teams", "Players", "Football 101"]
    requested_tab = st.query_params.get("tab", "Overview")
    if requested_tab == "Learn the Basics":
        requested_tab = "Football 101"
    default_index = tab_names.index(requested_tab) if requested_tab in tab_names else 0
    st.markdown('<div class="wc-tab-nav">', unsafe_allow_html=True)
    active_tab = st.radio("Dashboard section", tab_names, index=default_index, horizontal=True, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)
    if active_tab != requested_tab:
        st.query_params["tab"] = active_tab

    if active_tab == "Overview":
        render_overview(matches, standings, source)
    elif active_tab == "Upcoming & Live":
        render_matches_tab(matches, standings)
    elif active_tab == "Knockout Bracket":
        render_knockout_tab(matches, standings)
    elif active_tab == "Stats & Insights":
        render_insights_tab(matches)
    elif active_tab == "Groups & Standings":
        st.header("Groups & Standings")
        st.markdown("Top teams advance from each group; third-place teams can also qualify depending on the tournament format and table ranking.")
        render_standings(standings, teams)
    elif active_tab == "Teams":
        render_teams_tab(matches, teams, standings)
    elif active_tab == "Players":
        render_players_tab(matches)
    elif active_tab == "Football 101":
        render_fan_guide()


if __name__ == "__main__":
    main()
