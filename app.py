"""
World Cup 2026 Dashboard & Explorer
Interactive Streamlit components edition.

Default data source: https://worldcup26.ir public World Cup 2026 API
Optional experimental source: GitHub-hosted OpenFootball JSON with ESPN/TheSportsDB enrichment
Optional token support: set WORLDCUP26_TOKEN in Streamlit secrets if your API instance requires auth.
"""

from __future__ import annotations

import html
import json
import logging
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
logger = logging.getLogger(__name__)
DATA_DIR = APP_DIR / "data"
DEFAULT_API_BASE = "https://worldcup26.ir"
OPENFOOTBALL_WORLD_CUP_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary"
THESPORTSDB_API_BASE = "https://www.thesportsdb.com/api/v1/json/3"
THESPORTSDB_LEAGUE_ID = "4429"
THESPORTSDB_SEASON = "2026"
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
API_FOOTBALL_WORLD_CUP_LEAGUE = "1"
API_FOOTBALL_SEASON = "2026"

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


TEAM_PROFILE_MAP = {
    "Argentina": {"coach": "Lionel Scaloni", "captain": "Lionel Messi", "ranking": 1, "form": "Elite tournament pedigree"},
    "France": {"coach": "Didier Deschamps", "captain": "Kylian Mbappé", "ranking": 2, "form": "Explosive transition attack"},
    "Spain": {"coach": "Luis de la Fuente", "captain": "Álvaro Morata", "ranking": 3, "form": "High-possession control"},
    "England": {"coach": "Thomas Tuchel", "captain": "Harry Kane", "ranking": 4, "form": "Deep squad, set-piece threat"},
    "Brazil": {"coach": "Carlo Ancelotti", "captain": "Marquinhos", "ranking": 5, "form": "Creative wide forwards"},
    "Portugal": {"coach": "Roberto Martínez", "captain": "Cristiano Ronaldo", "ranking": 6, "form": "Clinical final-third quality"},
    "Netherlands": {"coach": "Ronald Koeman", "captain": "Virgil van Dijk", "ranking": 7, "form": "Balanced defensive spine"},
    "Belgium": {"coach": "Rudi Garcia", "captain": "Kevin De Bruyne", "ranking": 8, "form": "Chance creation hub"},
    "Germany": {"coach": "Julian Nagelsmann", "captain": "Joshua Kimmich", "ranking": 9, "form": "Aggressive midfield pressure"},
    "United States": {"coach": "Mauricio Pochettino", "captain": "Christian Pulisic", "ranking": 10, "form": "Host-nation energy"},
    "Mexico": {"coach": "Javier Aguirre", "captain": "Edson Álvarez", "ranking": 15, "form": "Home-continent intensity"},
    "Canada": {"coach": "Jesse Marsch", "captain": "Alphonso Davies", "ranking": 30, "form": "Fast direct runners"},
}

GOALKEEPER_MAP = {
    "Argentina": "Emiliano Martínez",
    "Australia": "Mathew Ryan",
    "Belgium": "Thibaut Courtois",
    "Brazil": "Alisson Becker",
    "Canada": "Dayne St. Clair",
    "Colombia": "Camilo Vargas",
    "England": "Jordan Pickford",
    "France": "Mike Maignan",
    "Germany": "Manuel Neuer",
    "Mexico": "Guillermo Ochoa",
    "Morocco": "Yassine Bounou",
    "Netherlands": "Bart Verbruggen",
    "Norway": "Ørjan Nyland",
    "Portugal": "Diogo Costa",
    "Spain": "Unai Simón",
    "Sweden": "Robin Olsen",
    "Switzerland": "Yann Sommer",
    "United States": "Matt Turner",
    "USA": "Matt Turner",
}

PLAYER_PROFILE_MAP = {
    "Kylian Mbappé": {"club": "Real Madrid", "position": "Forward", "age": 27},
    "Lionel Messi": {"club": "Inter Miami", "position": "Forward", "age": 39},
    "Erling Haaland": {"club": "Manchester City", "position": "Forward", "age": 25},
    "Harry Kane": {"club": "Bayern Munich", "position": "Forward", "age": 32},
    "Vinícius Júnior": {"club": "Real Madrid", "position": "Forward", "age": 25},
    "Ousmane Dembélé": {"club": "Paris Saint-Germain", "position": "Forward", "age": 29},
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
      .block-container {padding-top: 0.35rem !important;}
      [data-testid="stAppViewContainer"] .main .block-container {max-width: 100%;}
      [data-testid="stSidebar"] {background: linear-gradient(180deg, #07111f 0%, #0b1728 100%) !important; border-right: 1px solid var(--wc-border);}
      h1, h2, h3, h4, h5, h6, p, span, label, div {color: inherit;}
      .main-title {font-size: 2.4rem; font-weight: 900; margin-bottom: 0.2rem; color: var(--wc-text); letter-spacing: -0.04em;}
      .subtle {color: var(--wc-muted) !important; font-size: 0.95rem;}
      .wc-hero {position: relative; overflow: hidden; border: 1px solid rgba(247, 201, 72, 0.38); border-radius: 22px; padding: 12px 20px; margin: -0.2rem 0 10px 0; background: linear-gradient(120deg, rgba(2, 6, 23, .95), rgba(11, 42, 70, .92)), radial-gradient(circle at 12% 20%, rgba(247, 201, 72, .23), transparent 16rem), radial-gradient(circle at 85% 45%, rgba(34, 197, 94, .18), transparent 20rem); box-shadow: 0 22px 55px rgba(0, 0, 0, 0.35);}
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
      .wc-stat-card {padding: 16px; display:flex; align-items:center; gap:14px; min-height:104px; height:104px; box-sizing:border-box;}
      .wc-stat-icon {height:46px; width:46px; flex:0 0 46px; border-radius:16px; display:flex; align-items:center; justify-content:center; background: rgba(56,189,248,.13); font-size:1.45rem;}
      .wc-stat-value {font-size:clamp(1.25rem, 2vw, 1.72rem); line-height:1.05; font-weight:950; color:#fff; overflow-wrap:anywhere;}
      .wc-stat-card > div:last-child {min-width:0;}
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
      div[role="radiogroup"][aria-label="Dashboard section"], div[role="radiogroup"][aria-label="Dashboard section selector"] {display:flex !important; flex-wrap:nowrap !important; gap:7px !important; align-items:stretch !important;}
      div[role="radiogroup"][aria-label="Dashboard section"] label, div[role="radiogroup"][aria-label="Dashboard section selector"] label {position:relative; min-width:0 !important; white-space:nowrap; border:1px solid rgba(148,163,184,.24); border-radius:999px; padding:8px 12px !important; min-height:40px; font-weight:950; background:rgba(148,163,184,.10); transition:all .18s ease;}
      div[role="radiogroup"][aria-label="Dashboard section"] label:hover, div[role="radiogroup"][aria-label="Dashboard section selector"] label:hover {border-color:rgba(56,189,248,.70); background:rgba(56,189,248,.16); transform:translateY(-1px);}
      div[role="radiogroup"][aria-label="Dashboard section"] label:has(input:checked), div[role="radiogroup"][aria-label="Dashboard section selector"] label:has(input:checked) {color:#06111f !important; background:linear-gradient(135deg, #f7c948, #38bdf8); border-color:rgba(255,255,255,.45); box-shadow:0 10px 28px rgba(56,189,248,.20);}
      div[role="radiogroup"][aria-label="Dashboard section"] label:has(input:checked) *, div[role="radiogroup"][aria-label="Dashboard section selector"] label:has(input:checked) * {color:#06111f !important;}
      div[role="radiogroup"][aria-label="Dashboard section"] label > div:first-child, div[role="radiogroup"][aria-label="Dashboard section selector"] label > div:first-child {display:none !important;}
      .wc-basics-link, .wc-entity-link {color:inherit !important; font-weight:inherit; text-decoration:none;}
      .wc-basics-link {color:#67e8f9 !important; font-weight:900; border-bottom:1px solid rgba(103,232,249,.55);}
      .wc-entity-link:hover, .wc-basics-link:hover {color:#f7c948 !important; border-bottom:1px solid #f7c948;}
      .wc-overview-grid .wc-entity-link:hover {border-bottom:0;}
      div.stButton > button[kind="secondary"] {border-radius:999px;}
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
      .wc-overview-grid {display:grid; grid-template-columns:repeat(3, minmax(280px,1fr)); gap:16px; margin:16px 0; align-items:stretch;}
      .wc-summary-card {border:1px solid rgba(71,100,145,.9); border-radius:18px; padding:16px 18px; background:linear-gradient(180deg, rgba(25,39,62,.94), rgba(17,29,48,.94)); min-height:330px; height:100%; box-sizing:border-box; box-shadow:0 18px 42px rgba(0,0,0,.24);}
      .wc-summary-card h4 {margin:0 0 14px; color:#cbd5e1; font-size:.78rem; text-transform:uppercase; letter-spacing:.12em; font-weight:950;}
      .wc-summary-card h4::before {content:""; display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:10px; vertical-align:1px; background:linear-gradient(135deg,#f472b6,#38bdf8); box-shadow:0 0 14px rgba(244,114,182,.45);}
      .wc-summary-list {display:flex; flex-direction:column; gap:2px;}
      .wc-summary-row {display:grid; grid-template-columns:54px minmax(0,1fr) auto; gap:12px; align-items:center; min-height:44px; color:var(--wc-muted); font-size:.86rem; border-top:1px solid rgba(100,116,139,.26); padding:4px 0;}
      .wc-summary-row:first-child {border-top:0;}
      .wc-summary-main {display:flex; align-items:center; justify-content:flex-start; gap:8px; min-width:0; overflow:hidden;}
      .wc-summary-main .team-chip {vertical-align:middle;}
      .wc-summary-name, .wc-summary-country {font-weight:900; color:#fff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
      .wc-summary-name:hover, .wc-summary-country:hover, .wc-overview-grid .wc-entity-link:hover .team-name {color:var(--wc-green) !important;}
      .wc-summary-meta {color:var(--wc-muted); white-space:nowrap; font-size:.78rem;}
      .wc-summary-stage {color:#cbd5e1; font-size:.72rem; white-space:normal; line-height:1.1; font-weight:900;}
      .wc-summary-score {justify-self:end; text-align:right; font-weight:950; color:#fff; white-space:nowrap;}
      .wc-summary-goal {font-size:1.15rem; color:#fde68a;}
      .wc-rank-num {background:rgba(247,201,72,.18); color:#f7c948; border-radius:7px; text-align:center; font-weight:900; padding:3px;}
      .wc-bar {height:14px; border-radius:99px; background:rgba(148,163,184,.20); overflow:hidden;}
      .wc-bar-fill {height:100%; border-radius:99px; background:linear-gradient(90deg,#f43f5e,#22d3ee);}

      .flag-img {width:28px; height:20px; flex:0 0 28px; display:inline-block; object-fit:cover; border-radius:4px; box-shadow:0 0 0 1px rgba(255,255,255,.22); background:rgba(255,255,255,.08); vertical-align:middle; margin-right:0;}
      .team-chip {display:inline-flex; align-items:center; gap:7px; min-width:0; max-width:100%; line-height:1.15; vertical-align:middle;}
      .team-chip .team-name {font-weight:900; color:#fff; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
      .team-code {font-size:.68rem; color:#94a3b8; font-weight:900; letter-spacing:.06em; margin-left:3px;}
      .wc-player-photo {width:34px; height:34px; border-radius:50%; object-fit:cover; border:1px solid rgba(255,255,255,.22); box-shadow:0 0 0 3px rgba(56,189,248,.08); vertical-align:middle; margin-right:10px;}
      .wc-player-avatar {width:34px; height:34px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; margin-right:10px; background:linear-gradient(135deg,#1d4ed8,#111827); border:1px solid rgba(255,255,255,.18); color:#fff; font-weight:950; vertical-align:middle;}
      .wc-player-name {display:inline-flex; align-items:center; font-weight:900; color:#fff;}
      .wc-cup-final {display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:250px; border:1px solid rgba(247,201,72,.45); border-radius:28px; background:radial-gradient(circle at 50% 35%, rgba(247,201,72,.20), transparent 7rem), rgba(15,23,42,.72); text-align:center; box-shadow:0 18px 70px rgba(0,0,0,.35); animation:championGlow 2.4s ease-in-out infinite;}
      .wc-cup-icon {filter:drop-shadow(0 12px 28px rgba(247,201,72,.35));}
      .wc-cup-trophy-img {width:88px; height:142px; object-fit:contain;}
      .wc-format-line {display:inline-flex; align-items:center; gap:8px; margin-top:8px; padding:7px 12px; border-radius:999px; background:linear-gradient(90deg, rgba(247,201,72,.20), rgba(56,189,248,.13)); border:1px solid rgba(247,201,72,.30); color:#fff; font-weight:950; letter-spacing:.02em;}
      .wc-format-line b {color:var(--wc-gold);}
      .wc-world-champ {font-size:1.2rem; font-weight:950; color:#fff; letter-spacing:.08em; text-transform:uppercase; margin-top:8px;}
      .wc-bracket-side {display:grid; grid-template-columns:repeat(3, minmax(185px,1fr)); gap:16px; align-items:center;}
      .wc-bracket-side.right {direction:ltr;}
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


      @keyframes riseIn {from{opacity:0; transform:translateY(10px)} to{opacity:1; transform:translateY(0)}}
      @keyframes championGlow {0%,100%{box-shadow:0 18px 70px rgba(0,0,0,.35), 0 0 0 rgba(247,201,72,0); border-color:rgba(247,201,72,.45)} 50%{box-shadow:0 18px 70px rgba(0,0,0,.35), 0 0 26px rgba(247,201,72,.42); border-color:rgba(247,201,72,.88)}}
      .match-card,.wc-live-card,.wc-stat-card,.wc-summary-card,.wc-story,.wc-team-profile,.wc-player-card {animation:riseIn .36s ease both; transition:transform .2s ease, border-color .2s ease, box-shadow .2s ease;}
      .match-card:hover,.wc-live-card:hover,.wc-summary-card:hover,.wc-player-card:hover {transform:translateY(-2px); border-color:rgba(247,201,72,.46); box-shadow:0 18px 50px rgba(0,0,0,.30);}
      .wc-live-meta{display:flex;justify-content:space-between;align-items:center;gap:12px}.wc-live-clock{font-weight:950;color:#f7c948;border:1px solid rgba(247,201,72,.32);border-radius:999px;padding:5px 10px;background:rgba(247,201,72,.10)}
      .wc-centre-hero{border:1px solid rgba(247,201,72,.38);border-radius:24px;padding:18px;background:radial-gradient(circle at 50% 0,rgba(247,201,72,.16),transparent 18rem),rgba(8,20,36,.94)}.wc-centre-score{display:grid;grid-template-columns:1fr auto 1fr;gap:18px;align-items:center;text-align:center;margin-top:14px}.wc-centre-score strong{font-size:clamp(2rem,6vw,4rem);color:#fff}.wc-click-hint,.wc-mini-note{margin-top:10px;color:#a8b3c7;font-size:.84rem;text-align:center}
      .wc-overview-spacer{height:18px;}
      .wc-inline-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:-4px 0 12px;}
      .wc-timeline-strip{height:18px;margin:18px 8px 10px;position:relative;border-radius:999px;background:linear-gradient(90deg,rgba(34,197,94,.25),rgba(247,201,72,.25),rgba(56,189,248,.25))}.wc-timeline-dot{position:absolute;top:50%;width:13px;height:13px;transform:translate(-50%,-50%);border-radius:50%;background:#22c55e;border:2px solid #fff;box-shadow:0 0 18px rgba(34,197,94,.5)}.wc-timeline-dot.away{background:#38bdf8}.wc-match-events{display:grid;grid-template-columns:1fr 54px 1fr;gap:8px;align-items:center}.wc-event-left{text-align:right}.wc-event-right{text-align:left}.wc-event-time{text-align:center;color:#f7c948;font-weight:950}
      .wc-stat-row{display:grid;grid-template-columns:1fr 150px 1fr;gap:12px;align-items:center;margin:10px 0}.wc-stat-bar{height:9px;border-radius:999px;background:rgba(148,163,184,.18);overflow:hidden}.wc-stat-fill-home,.wc-stat-fill-away{height:100%;border-radius:999px}.wc-stat-fill-home{margin-left:auto;background:linear-gradient(90deg,#22c55e,#f7c948)}.wc-stat-fill-away{background:linear-gradient(90deg,#38bdf8,#818cf8)}
      .wc-refresh-pill{display:inline-flex;align-items:center;gap:8px;border:1px solid rgba(56,189,248,.28);border-radius:999px;padding:5px 10px;background:rgba(56,189,248,.10);font-weight:800;color:#dff6ff}.wc-bracket-board{position:relative}.wc-bracket-board::before{display:none}.wc-bracket-card::before{content:"";position:absolute;top:50%;height:2px;width:14px;background:rgba(247,201,72,.82);z-index:0}.wc-bracket-card::after{content:"";display:block;position:absolute;top:16px;bottom:16px;width:2px;background:rgba(247,201,72,.54);z-index:0}.wc-bracket-side.left .wc-bracket-card::before{right:-14px}.wc-bracket-side.left .wc-bracket-card::after{right:-15px}.wc-bracket-side.right .wc-bracket-card::before{left:-14px}.wc-bracket-side.right .wc-bracket-card::after{left:-15px}.wc-bracket-side.left>div:last-child .wc-bracket-card::before,.wc-bracket-side.left>div:last-child .wc-bracket-card::after,.wc-bracket-side.right>div:first-child .wc-bracket-card::before,.wc-bracket-side.right>div:first-child .wc-bracket-card::after{display:block}.wc-route-legend{text-align:center;color:#a8b3c7;margin-top:10px;font-size:.86rem}.wc-team-profile{border:1px solid var(--wc-border);border-radius:24px;padding:18px;background:linear-gradient(135deg,rgba(15,31,53,.94),rgba(8,20,36,.94));}.wc-team-hero{display:flex;gap:14px;align-items:center}.wc-team-flag-xl{font-size:3rem}.wc-form-badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.wc-form-badge{height:28px;min-width:28px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;font-weight:950;background:rgba(148,163,184,.18)}.wc-form-badge.win{background:rgba(34,197,94,.22);color:#bbf7d0}.wc-form-badge.loss{background:rgba(239,68,68,.18);color:#fecaca}.wc-form-badge.draw{background:rgba(247,201,72,.18);color:#fde68a}.wc-player-grid{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:12px}.wc-player-card{border:1px solid var(--wc-border);border-radius:18px;padding:14px;background:rgba(15,31,53,.82)}.wc-player-card-top{display:flex;gap:12px;align-items:center}.wc-player-card .wc-player-photo,.wc-player-card .wc-player-avatar{width:54px;height:54px;font-size:1rem}.wc-player-meta{color:#a8b3c7;font-size:.84rem;margin-top:4px}.wc-player-statline{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}.wc-player-stat{border-radius:12px;background:rgba(148,163,184,.12);padding:8px;text-align:center}.wc-player-stat b{display:block;color:#fff;font-size:1.1rem}
      @media (max-width: 900px) {.wc-stat-row{grid-template-columns:1fr}.wc-centre-score{grid-template-columns:1fr}.wc-player-grid{grid-template-columns:1fr 1fr}.wc-bracket-board{grid-template-columns:1fr;min-width:760px}.wc-bracket-board::before{display:none}}
      @media (max-width: 640px) {.wc-player-grid{grid-template-columns:1fr}.wc-hero-inner{align-items:flex-start}.wc-trophy{display:none}}

      @media (max-width: 1100px) {.wc-overview-grid{grid-template-columns:1fr 1fr}}
      @media (max-width: 900px) {.wc-story-grid,.wc-basics-grid{grid-template-columns:1fr 1fr}.wc-live-teams{grid-template-columns:1fr}.wc-bracket-grid{grid-template-columns:repeat(3,minmax(210px,1fr));}}
      @media (max-width: 640px) {.wc-story-grid,.wc-overview-grid,.wc-basics-grid{grid-template-columns:1fr}}
      .wc-bracket-shell.compact {padding:14px;}
      .wc-bracket-shell.compact .wc-bracket-board {min-width:1080px; grid-template-columns:1fr 220px 1fr; gap:14px;}
      .wc-bracket-shell.compact .wc-bracket-side {grid-template-columns:repeat(4, minmax(132px, 1fr)); gap:10px;}
      .wc-bracket-shell.compact .wc-bracket-card {min-height:62px; padding:7px; border-radius:12px; font-size:.72rem;}
      .wc-bracket-shell.compact .wc-bracket-team {font-size:.68rem; margin:2px 0;}
      .wc-bracket-shell.compact .wc-bracket-score {font-size:.78rem;}
      .wc-bracket-shell.compact .wc-bracket-round-title {font-size:.62rem; margin-bottom:6px;}
      .wc-bracket-shell.compact .wc-bracket-stack {gap:7px;}
      .wc-bracket-shell.compact .wc-bracket-stack.r16 {gap:23px;}
      .wc-bracket-shell.compact .wc-bracket-stack.qf {gap:58px;}
      .wc-bracket-shell.compact .wc-bracket-stack.sf {gap:138px;}
      .wc-bracket-shell.compact .wc-cup-final {padding:12px; min-height:280px;}
      .wc-bracket-shell.compact .wc-cup-icon {font-size:2.1rem;}
      .wc-bracket-shell.compact .team-code {display:none;}
      .wc-bracket-shell.compact .wc-flag {width:19px;height:14px;font-size:.8rem;}
      .wc-route-chip{display:inline-flex;align-items:center;gap:6px;border:1px solid rgba(247,201,72,.32);background:rgba(247,201,72,.10);border-radius:999px;padding:4px 9px;margin:3px;color:#fde68a;font-size:.75rem;font-weight:900}

      .wc-section-kicker{color:#a8b3c7;font-weight:900;text-transform:uppercase;letter-spacing:.10em;font-size:.78rem;margin:10px 0;}
      .wc-team-filter-row{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 14px;}.wc-team-filter-pill{border:1px solid rgba(148,163,184,.46);border-radius:999px;padding:6px 12px;background:rgba(15,31,53,.78);color:#cbd5e1;font-weight:900;font-size:.83rem;text-decoration:none;}.wc-team-filter-pill.active{border-color:#2dd4bf;background:rgba(45,212,191,.16);color:#fff;box-shadow:0 0 18px rgba(45,212,191,.16);}
      .wc-team-card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;margin-top:8px;}.wc-team-card{display:block;text-decoration:none;border:1px solid rgba(71,100,145,.95);border-radius:12px;padding:14px;background:radial-gradient(circle at 88% 86%,rgba(56,189,248,.13),transparent 4rem),linear-gradient(135deg,rgba(25,39,62,.96),rgba(15,27,45,.96));min-height:116px;color:#f8fafc;box-shadow:0 14px 32px rgba(0,0,0,.22);transition:transform .18s ease,border-color .18s ease;}.wc-team-card:hover{transform:translateY(-2px);border-color:rgba(45,212,191,.70);}.wc-team-card-top{display:flex;align-items:center;gap:8px;min-width:0;}.wc-team-card-flag .flag-img,.wc-team-card-flag .wc-flag{width:48px;height:32px;font-size:1.7rem;border-radius:4px;}.wc-team-card-name{font-weight:950;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}.wc-team-card-group{margin-left:56px;color:#a8b3c7;font-size:.78rem;font-weight:800;}.wc-team-card-bottom{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:16px;}.wc-team-status{border:1px solid rgba(34,197,94,.42);background:rgba(34,197,94,.13);color:#bbf7d0;border-radius:999px;padding:4px 9px;font-size:.70rem;font-weight:950;}.wc-team-status.eliminated{border-color:rgba(244,63,94,.55);background:rgba(244,63,94,.16);color:#fecdd3;}.wc-team-form{display:flex;gap:4px;}.wc-mini-form{width:20px;height:20px;border-radius:6px;display:inline-flex;align-items:center;justify-content:center;font-size:.68rem;font-weight:950;background:#94a3b8;color:#06111f}.wc-mini-form.win{background:#22c55e}.wc-mini-form.loss{background:#fb7185}.wc-mini-form.draw{background:#cbd5e1;}
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




PLAYER_FIELD_KEYS = {"minute", "team", "type", "player", "assist", "event", "source", "goal"}
KNOWN_INITIALS = {"JR", "SR", "Jr", "Sr"}


def valid_player_name(value: Any, teams: Optional[Iterable[Any]] = None) -> bool:
    name = clean_text(value)
    if not name:
        return False
    lower = name.lower()
    if lower in PLAYER_FIELD_KEYS or lower in {"none", "null", "nan", "tbd", "own", "own goal", "goal", "event"}:
        return False
    if any(ch in name for ch in ['{', '}', ':', '[', ']']):
        return False
    if re.fullmatch(r"[\W_\d]+", name):
        return False
    if len(name) < 3 and name not in KNOWN_INITIALS:
        return False
    team_names = set(FALLBACK_FLAGS) | set(TEAM_CODE_MAP) | set(TEAM_ISO2_MAP)
    if teams:
        team_names |= {clean_text(t) for t in teams if clean_text(t)}
    team_keys = {team_match_key(t) for t in team_names if clean_text(t)}
    if team_match_key(name) in team_keys:
        return False
    return True


def valid_scorer_string(value: Any, teams: Optional[Iterable[Any]] = None) -> bool:
    text = clean_text(value)
    if not text:
        return False
    names = [clean_player_name(piece, teams=teams) for piece in re.split(r",|;|\|", text)]
    valid_names = [name for name in names if name]
    return bool(valid_names) and all(valid_player_name(name, teams=teams) for name in valid_names)


def player_name_from_event(item: Dict[str, Any], teams: Optional[Iterable[Any]] = None) -> str:
    for key in ["player", "player_name", "strPlayer", "athlete", "scorer", "goal_scorer", "name"]:
        val = item.get(key)
        if isinstance(val, dict):
            val = val.get("displayName") or val.get("name")
        candidate = clean_player_name(val, teams=teams)
        if valid_player_name(candidate, teams=teams):
            return candidate
    for key in ["strTimelineDetail", "detail", "text", "description"]:
        candidate = clean_player_name(item.get(key), teams=teams)
        if valid_player_name(candidate, teams=teams):
            return candidate
    logger.info("Skipping event with unknown/untrusted player shape: %s", item)
    return ""

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



def app_link(tab: str, **params: Any) -> str:
    query = {"tab": tab, **{k: v for k, v in params.items() if clean_text(v)}}
    return "?" + "&".join(f"{quote(str(k))}={quote(clean_text(v))}" for k, v in query.items())

def team_link(team: Any, label_html: str) -> str:
    name = clean_text(team, "TBD")
    if name == "TBD":
        return label_html
    return f'<a class="wc-entity-link" href="{app_link("Teams", team=name)}" target="_self">{label_html}</a>'

def player_link(player: Any, label_html: str) -> str:
    name = clean_text(player)
    if not name:
        return label_html
    return f'<a class="wc-entity-link" href="{app_link("Players", player=name)}" target="_self">{label_html}</a>'

def team_chip(team: Any, show_code: bool = True) -> str:
    name = clean_text(team, "TBD")
    code = team_code(name)
    code_html = f'<span class="team-code">{code}</span>' if show_code else ""
    return team_link(name, f'<span class="team-chip">{flag_img(name)}<span class="team-name">{esc(name)}</span>{code_html}</span>')


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


def client_live_clock_html(row: pd.Series, fallback: str) -> str:
    """Render a browser-updated live clock when kickoff time is available."""
    if row.get("status") != "Live" or not isinstance(row.get("date_time"), datetime):
        return esc(fallback)
    kickoff_ms = int(row.get("date_time").timestamp() * 1000)
    return f'<span class="wc-js-clock" data-kickoff="{kickoff_ms}">{esc(fallback)}</span>'


def inject_live_clock_script() -> None:
    components.html(
        """
        <script>
          const doc = window.parent.document;
          function tickClocks() {
            doc.querySelectorAll('.wc-js-clock[data-kickoff]').forEach((el) => {
              const start = Number(el.dataset.kickoff);
              if (!start) return;
              const total = Math.max(0, Math.floor((Date.now() - start) / 1000));
              const mins = Math.floor(total / 60);
              el.textContent = `${Math.max(1, mins)}'`;
            });
          }
          tickClocks();
          setInterval(tickClocks, 1000);
          setTimeout(() => window.parent.location.reload(), 30000);
        </script>
        """,
        height=0,
    )


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


FIFA_2026_EMBLEM_URL = "https://commons.wikimedia.org/wiki/Special:Redirect/file/2026_FIFA_World_Cup_emblem.svg"

def trophy_image_html(class_name: str = "wc-trophy-img") -> str:
    return f'<img class="{class_name}" src="{FIFA_2026_EMBLEM_URL}" alt="FIFA World Cup 2026 emblem" loading="lazy">'


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
    raw = raw.replace("matchday", "group").replace("group stage", "group")
    raw = raw.replace("round_of_32", "r32").replace("round of 32", "r32")
    raw = raw.replace("round_of_16", "r16").replace("round of 16", "r16")
    raw = raw.replace("quarterfinal", "qf").replace("quarter-final", "qf").replace("quarter finals", "qf")
    raw = raw.replace("semifinal", "sf").replace("semi-final", "sf")
    raw = raw.replace("3rd", "third").replace("third place playoff", "third")
    if raw.startswith("group") or raw.startswith("first stage"):
        return "group"
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


@st.cache_data(ttl=30, show_spinner=False)
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
    def first_present(item: Dict[str, Any], keys: Iterable[str]) -> Any:
        for key in keys:
            if key in item and item.get(key) is not None:
                return item.get(key)
        return None

    rows: List[Dict[str, Any]] = []
    for item in unwrap(raw, ["games", "matches", "fixtures", "data", "response", "game"]):
        home_score = to_int(first_present(item, ["home_score", "homeScore", "home_goals"]), None)
        away_score = to_int(first_present(item, ["away_score", "awayScore", "away_goals"]), None)
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


@st.cache_data(ttl=30, show_spinner=False)
def load_live_data(api_base: str, token: str, fallback_to_demo: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
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
        if not fallback_to_demo:
            raise RuntimeError("; ".join(errors)) from exc
        matches, teams, groups, stadiums, source = load_fallback()
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


def biggest_wins(matches_df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    finished = matches_df[matches_df["status"] == "Finished"].copy() if not matches_df.empty else pd.DataFrame()
    if finished.empty:
        return pd.DataFrame()
    finished = finished.dropna(subset=["home_score", "away_score"]).copy()
    if finished.empty:
        return pd.DataFrame()
    finished["winner_score"] = finished[["home_score", "away_score"]].max(axis=1).astype(int)
    finished["margin"] = (finished["home_score"] - finished["away_score"]).abs().astype(int)
    finished = finished[(finished["margin"] > 0) & (finished["winner_score"] >= 5)]
    return finished.sort_values(["winner_score", "margin", "date_time"], ascending=[False, False, True]).head(limit)


def overview_row(main_html: str, score_html: str = "", meta_html: str = "") -> str:
    meta = f"<div class='wc-summary-stage'>{meta_html}</div>" if meta_html else "<div class='wc-summary-stage'></div>"
    score = f"<span class='wc-summary-score'>{score_html}</span>" if score_html else ""
    return f"<div class='wc-summary-row'>{meta}<div class='wc-summary-main'>{main_html}</div>{score}</div>"


def clean_sheet_table(matches_df: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    finished = matches_df[matches_df["status"] == "Finished"].dropna(subset=["home_score", "away_score"]).copy() if not matches_df.empty else pd.DataFrame()
    records = []
    for _, r in finished.iterrows():
        if int(r["away_score"]) == 0:
            team = clean_text(r["home_team"])
            records.append({"team": team, "keeper": GOALKEEPER_MAP.get(team, "Starting keeper"), "clean_sheets": 1})
        if int(r["home_score"]) == 0:
            team = clean_text(r["away_team"])
            records.append({"team": team, "keeper": GOALKEEPER_MAP.get(team, "Starting keeper"), "clean_sheets": 1})
    if not records:
        return pd.DataFrame(columns=["team", "keeper", "clean_sheets"])
    return (pd.DataFrame(records)
        .groupby(["team", "keeper"], as_index=False)["clean_sheets"].sum()
        .sort_values(["clean_sheets", "team"], ascending=[False, True])
        .head(limit))


def render_overview_summary_cards(matches_df: pd.DataFrame) -> None:
    players = extract_player_stats(matches_df)
    top_scorers = players[players["G"] > 0].head(8) if not players.empty else pd.DataFrame()
    top_assists = players[players["A"] > 0].sort_values(["A", "G+A", "Player"], ascending=[False, False, True]).head(8) if not players.empty else pd.DataFrame()
    clean_sheets = clean_sheet_table(matches_df, limit=8)
    big_wins = biggest_wins(matches_df, limit=6)
    upcoming = matches_df[matches_df["status"] == "Scheduled"].sort_values("date_time", na_position="last").head(7) if not matches_df.empty else pd.DataFrame()
    latest = matches_df[matches_df["status"] == "Finished"].sort_values("date_time", ascending=False, na_position="last").head(7) if not matches_df.empty else pd.DataFrame()

    def match_row(r: Any, value_html: str) -> str:
        return overview_row(
            f"{team_chip(r.home_team)} <span class='wc-summary-meta'>vs</span> {team_chip(r.away_team)}",
            value_html,
            esc(r.stage_label),
        )

    cards = [
        ("🏟️ Latest Results", [match_row(r, scoreline_label(pd.Series(r._asdict()))) for r in latest.itertuples()] if not latest.empty else [overview_row("Latest results will appear after completed matches.")]),
        ("🗓️ Upcoming Matches", [match_row(r, esc(r.kickoff)) for r in upcoming.itertuples()] if not upcoming.empty else [overview_row("No upcoming matches are currently loaded.")]),
        ("🔥 Biggest Wins", [match_row(r, scoreline_label(pd.Series(r._asdict()))) for r in big_wins.itertuples()] if not big_wins.empty else [overview_row("Wins by at least five goals will appear here.")]),
        ("🏅 Top Scorers", [
            overview_row(
                f"<span class='wc-summary-name'>{player_link(r.Player, esc(r.Player))}</span> {team_chip(r.Country)}",
                f"<span class='wc-summary-goal'>{int(r.G)}</span>",
                f"#{i}",
            )
            for i, r in enumerate(top_scorers.itertuples(), start=1)
        ] if not top_scorers.empty else [overview_row("Goal scorers will appear here once the feed reports them.")]),
        ("🅰️ Top Assists", [
            overview_row(
                f"<span class='wc-summary-name'>{player_link(r.Player, esc(r.Player))}</span> {team_chip(r.Country)}",
                f"<span class='wc-summary-goal'>{int(r.A)}</span>",
                f"#{i}",
            )
            for i, r in enumerate(top_assists.itertuples(), start=1)
        ] if not top_assists.empty else [overview_row("Assist leaders will appear when the match feed supplies assist data.")]),
        ("🥅 Most Clean Sheets", [
            overview_row(
                f"<span class='wc-summary-name'>{esc(r.keeper)}</span> {team_chip(r.team)}",
                f"{int(r.clean_sheets)} CS",
                f"#{i}",
            )
            for i, r in enumerate(clean_sheets.itertuples(), start=1)
        ] if not clean_sheets.empty else [overview_row("Clean sheets will appear after shutouts are recorded.")]),
    ]
    html_cards = []
    for title, items in cards:
        html_cards.append(f"<div class='wc-summary-card'><h4>{title}</h4><div class='wc-summary-list'>{''.join(items)}</div></div>")
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



def team_top_player(team: str) -> str:
    profile = TEAM_PROFILE_MAP.get(clean_text(team), {})
    return clean_text(profile.get("captain") or profile.get("top_player"), "To be confirmed")


def _json_for_components(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False).replace("</", "<\\/")


def component_payload(matches_df: pd.DataFrame, teams_df: pd.DataFrame, standings_df: pd.DataFrame) -> Dict[str, Any]:
    teams = sorted(set(teams_df["team"].dropna()) if not teams_df.empty and "team" in teams_df.columns else (set(matches_df.get("home_team", [])) | set(matches_df.get("away_team", []))))
    stand_lookup = group_position_lookup(standings_df)
    payload_teams = []
    for team in teams:
        team = clean_text(team)
        if not team or team == "TBD":
            continue
        trow = teams_df[teams_df["team"] == team].head(1) if not teams_df.empty and "team" in teams_df.columns else pd.DataFrame()
        tmatches = filter_matches(matches_df, team=team) if not matches_df.empty else pd.DataFrame()
        stats = team_worldcup_stats(team, matches_df, standings_df)
        profile = team_profile(team, tmatches)
        next_label = "No scheduled match"
        if not stats["next"].empty:
            nr = stats["next"].iloc[0]
            next_label = f"{clean_text(nr.get('home_team'))} vs {clean_text(nr.get('away_team'))} • {clean_text(nr.get('kickoff'))}"
        payload_teams.append({"team": team, "code": team_code(team), "flag": team_flag(team), "group": clean_text(trow.iloc[0].get("group") if not trow.empty else ""), "coach": profile["coach"], "captain": profile["captain"], "ranking": profile["ranking"], "topPlayer": team_top_player(team), "style": profile["style"], "form": profile["form"], "matches": int(stats["matches"]), "played": int(stats["played"]), "record": f"{stats['wins']}-{stats['draws']}-{stats['losses']}", "goals": f"{stats['gf']}:{stats['ga']}", "gd": int(stats["gd"]), "next": next_label, "standing": stand_lookup.get(team, team_code(team)), "route": [f"{clean_text(r.get('kickoff'))} — {clean_text(r.get('home_team'))} {scoreline_label(r)} {clean_text(r.get('away_team'))}" for _, r in tmatches.head(6).iterrows()]})
    payload_matches = []
    for _, r in matches_df.iterrows():
        home = clean_text(r.get("home_team", "TBD"), "TBD"); away = clean_text(r.get("away_team", "TBD"), "TBD")
        hp, ap = matchup_probabilities(home, away, r)
        goals = scorer_events(r)
        payload_matches.append({"id": clean_text(r.get("match_id")) or str(len(payload_matches)), "home": home, "away": away, "homeFlag": team_flag(home), "awayFlag": team_flag(away), "score": scoreline_label(r), "status": clean_text(r.get("status")), "stage": clean_text(r.get("stage_label")), "stageCode": clean_text(r.get("stage")), "kickoff": clean_text(r.get("kickoff")), "venue": clean_text(r.get("venue")), "kickoffMs": int(r.get("date_time").timestamp()*1000) if isinstance(r.get("date_time"), datetime) else None, "minute": live_minute(r), "prob": [hp, ap], "scorers": [f"{e.get('label')} {e.get('player')} ({e.get('team')})" for e in goals], "assists": [name for x in event_list_from_raw(r, ["events", "goals", "assists"]) if (name := clean_player_name(x.get("assist") or x.get("assist_name"), teams=[r.get("home_team"), r.get("away_team")]))], "cards": cards_from_raw(r), "subs": substitutions_from_raw(r), "stats": [{"label": lab, "home": hv, "away": av} for lab, hv, av in match_stat_rows(r)]})
    payload_standings = []
    if not standings_df.empty:
        sdf = standings_df.copy()
        for col in ["group", "team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]:
            if col not in sdf.columns: sdf[col] = 0
        for g, gdf in sdf.groupby(sdf["group"].astype(str).str.upper()):
            if not g: continue
            gdf = gdf.sort_values(["Pts", "GD", "GF"], ascending=[False, False, False], na_position="last")
            for rank, (_, row) in enumerate(gdf.iterrows(), 1):
                payload_standings.append({"group": g, "rank": rank, "team": clean_text(row.get("team")), "flag": team_flag(row.get("team")), "code": team_code(row.get("team")), "P": to_int(row.get("P"),0), "W": to_int(row.get("W"),0), "D": to_int(row.get("D"),0), "L": to_int(row.get("L"),0), "GF": to_int(row.get("GF"),0), "GA": to_int(row.get("GA"),0), "GD": to_int(row.get("GD"),0), "Pts": to_int(row.get("Pts"),0)})
    return {"teams": payload_teams, "matches": payload_matches, "standings": payload_standings}


def interactive_component_html(payload: Dict[str, Any], mode: str) -> str:
    data = _json_for_components(payload)
    return f"""
<div id='wc-app'></div>
<style>
:root{{--bg:#06111f;--panel:#0b1728;--panel2:#0f1f35;--muted:#a8b3c7;--line:rgba(148,163,184,.24);--gold:#f7c948;--cyan:#38bdf8;--green:#22c55e;--red:#ef4444}}
*{{box-sizing:border-box}} body{{margin:0;background:#06111f;color:#f8fafc;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif}}
.copy{{color:var(--muted);margin:0 0 14px;font-size:.96rem;line-height:1.45}} .section-title{{font-size:1.55rem;font-weight:950;letter-spacing:-.03em;margin:0 0 6px;color:#fff}} .section-title:after{{content:"";display:block;width:76px;height:3px;margin-top:10px;background:linear-gradient(90deg,#2dd4bf,#f7c948);border-radius:99px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:14px}} .card,.panel{{border:1px solid var(--line);border-radius:20px;background:linear-gradient(180deg,rgba(15,31,53,.96),rgba(8,20,36,.96));padding:15px;box-shadow:0 14px 34px rgba(0,0,0,.25)}}
.card{{cursor:pointer;transition:transform .18s,border-color .18s,background .18s}} .card:hover{{transform:translateY(-2px);border-color:#f7c948;background:linear-gradient(180deg,rgba(20,42,72,.98),rgba(9,24,43,.98))}}
.team-card{{min-height:178px;display:flex;flex-direction:column;gap:12px;position:relative;overflow:hidden}} .team-card:after{{content:"";position:absolute;right:-38px;top:-38px;width:120px;height:120px;border-radius:999px;background:rgba(56,189,248,.08)}}
.team-top{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;position:relative;z-index:1}} .flag{{font-size:2.25rem;line-height:1}} .team-name{{font-weight:950;font-size:1.13rem;color:#fff;line-height:1.15}} .code{{display:inline-flex;align-items:center;justify-content:center;border:1px solid rgba(247,201,72,.38);background:rgba(247,201,72,.12);color:#fde68a;border-radius:999px;padding:4px 9px;font-weight:950;font-size:.75rem;letter-spacing:.08em;white-space:nowrap}}
.muted{{color:var(--muted);font-size:.86rem}} .team-meta{{display:flex;flex-wrap:wrap;gap:6px;position:relative;z-index:1}} .tag{{display:inline-flex;gap:6px;align-items:center;border:1px solid rgba(148,163,184,.25);border-radius:999px;padding:4px 9px;margin:2px 2px 2px 0;font-weight:850;font-size:.76rem;background:rgba(148,163,184,.11)}}
.live{{color:#fecaca;background:rgba(239,68,68,.16);border-color:rgba(239,68,68,.4)}} .dot{{width:9px;height:9px;border-radius:99px;background:#ef4444;animation:blink 1s infinite;box-shadow:0 0 16px #ef4444}} @keyframes blink{{50%{{opacity:.2}}}} .clock{{color:#f7c948;font-weight:950}}
table{{width:100%;border-collapse:collapse;overflow:hidden}} th,td{{padding:10px;border-top:1px solid rgba(148,163,184,.18);text-align:left}} th{{font-size:.76rem;text-transform:uppercase;letter-spacing:.08em;color:#a8b3c7}} tr[data-team]{{cursor:pointer}} tr[data-team]:hover{{background:rgba(56,189,248,.12)}} .standing-team{{display:flex;align-items:center;gap:9px;font-weight:900;color:#fff}} .standing-flag{{font-size:1.3rem;min-width:1.6rem;text-align:center}}
.score{{font-size:2.2rem;font-weight:950;text-align:center}} .matchline{{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center}} .team{{font-weight:900;font-size:1.05rem}}
.modal{{position:fixed;inset:0;background:rgba(2,6,23,.78);display:none;align-items:center;justify-content:center;z-index:99;padding:18px}} .modal.open{{display:flex}} .modal-card{{max-width:920px;width:100%;max-height:88vh;overflow:auto;border:1px solid rgba(247,201,72,.4);border-radius:24px;background:#081424;padding:20px;box-shadow:0 28px 90px rgba(0,0,0,.48)}} .close{{float:right;border:0;border-radius:999px;padding:8px 12px;cursor:pointer;font-weight:850}} .stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}} .stat{{border-radius:12px;background:rgba(148,163,184,.12);padding:9px;text-align:center}} .bar{{height:8px;background:rgba(148,163,184,.18);border-radius:99px;overflow:hidden}} .fill{{height:100%;background:linear-gradient(90deg,#22c55e,#f7c948)}} .centre{{display:none;margin-top:12px}} .centre.open{{display:block}} .event{{display:grid;grid-template-columns:1fr 70px 1fr;gap:8px;margin:4px 0}}
@media(max-width:700px){{.stats{{grid-template-columns:repeat(2,1fr)}} .matchline{{grid-template-columns:1fr; text-align:center}}}}
</style>
<script>
const DATA={data}; const MODE={json.dumps(mode)}; const root=document.getElementById('wc-app');
const esc=s=>(s??'').toString().replace(/[&<>\"']/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[m]));
function mmss(m){{ if(m.status!=='Live') return esc(m.minute||m.kickoff); if(!m.kickoffMs) return esc(m.minute||'LIVE'); const min=Math.floor(Math.max(0,Date.now()-m.kickoffMs)/60000); return `${{Math.max(1,min)}}'`; }}
function closeModal(){{document.querySelector('.modal').classList.remove('open')}}
function teamModal(name){{const t=DATA.teams.find(x=>x.team===name); if(!t)return; document.querySelector('.modal-card').innerHTML=`<button class='close' onclick='closeModal()'>Close</button><h2>${{esc(t.flag)}} ${{esc(t.team)}} <span class='code'>${{esc(t.code)}}</span></h2><p class='muted'>${{esc(t.standing)}} • Group ${{esc(t.group||'—')}}</p><div class='stats'><div class='stat'><b>${{esc(t.record)}}</b><br>W-D-L</div><div class='stat'><b>${{esc(t.goals)}}</b><br>Goals</div><div class='stat'><b>${{esc(t.gd)}}</b><br>GD</div><div class='stat'><b>${{esc(t.ranking)}}</b><br>Ranking</div></div><h3>Profile</h3><p>Coach: <b>${{esc(t.coach)}}</b> • Captain: <b>${{esc(t.captain)}}</b> • Top player: <b>${{esc(t.topPlayer)}}</b></p><p>${{esc(t.style)}}</p><p>Form: ${{(t.form||[]).map(x=>`<span class='tag'>${{esc(x)}}</span>`).join('')}}</p><h3>Next match</h3><p>${{esc(t.next)}}</p><h3>Matches</h3><ul>${{(t.route||[]).map(x=>`<li>${{esc(x)}}</li>`).join('')||'<li>No matches loaded</li>'}}</ul>`; document.querySelector('.modal').classList.add('open');}}
function centre(m){{return `<h3>Match Centre</h3><div class='stats'><div class='stat'><b>${{m.prob[0]}}%</b><br>${{esc(m.home)}} win</div><div class='stat'><b>${{m.prob[1]}}%</b><br>${{esc(m.away)}} win</div><div class='stat'><b class='clock' data-clock='${{esc(m.id)}}'>${{mmss(m)}}</b><br>Clock</div><div class='stat'><b>${{esc(m.score)}}</b><br>Score</div></div><h4>Timeline / scorers</h4>${{m.scorers.map(x=>`<div class='event'><span></span><b>⚽</b><span>${{esc(x)}}</span></div>`).join('')||'<p class="muted">No scorer timeline available.</p>'}}<h4>Assists</h4><p>${{m.assists.map(esc).join(', ')||'Not available'}}</p><h4>Cards</h4><p>${{m.cards.map(c=>`${{esc(c.minute)}} ${{esc(c.player)}} (${{esc(c.team)}}) ${{esc(c.card)}}`).join('<br>')||'Not available'}}</p><h4>Substitutions</h4><p>${{m.subs.map(s=>`${{esc(s.minute)}} ${{esc(s.in)}} for ${{esc(s.out)}} (${{esc(s.team)}})`).join('<br>')||'Not available'}}</p><h4>Match stats</h4>${{m.stats.map(s=>`<div><div class='muted'>${{esc(s.label)}}: <b>${{s.home}}</b> - <b>${{s.away}}</b></div><div class='bar'><div class='fill' style='width:${{Math.round(100*s.home/Math.max(1,s.home+s.away))}}%'></div></div></div>`).join('')}}`;}}
function matchCard(m){{return `<div class='card match' data-id='${{esc(m.id)}}'><div><span class='tag ${{m.status==='Live'?'live':''}}'>${{m.status==='Live'?'<span class="dot"></span>':''}}${{esc(m.status)}}</span><span class='tag'>${{esc(m.stage)}}</span><span class='tag clock' data-clock='${{esc(m.id)}}'>${{mmss(m)}}</span></div><div class='matchline'><div class='team'>${{esc(m.homeFlag)}} ${{esc(m.home)}}</div><div class='score'>${{esc(m.score)}}</div><div class='team' style='text-align:right'>${{esc(m.away)}} ${{esc(m.awayFlag)}}</div></div><div class='muted' style='text-align:center'>${{esc(m.kickoff)}}${{m.venue?' • '+esc(m.venue):''}}</div><div class='centre' id='centre-${{esc(m.id)}}'>${{centre(m)}}</div></div>`}}
function teamCard(t){{return `<div class='card team-card' data-team='${{esc(t.team)}}'><div class='team-top'><div><div class='flag'>${{esc(t.flag)}}</div><div class='team-name'>${{esc(t.team)}}</div></div><span class='code'>${{esc(t.code)}}</span></div><div class='muted'>${{esc(t.standing)}}${{t.group?' • Group '+esc(t.group):''}}</div><div class='team-meta'><span class='tag'>Coach ${{esc(t.coach)}}</span><span class='tag'>${{esc(t.record)}} W-D-L</span><span class='tag'>GD ${{esc(t.gd)}}</span></div></div>`}}
function render(){{let html='<div class="modal"><div class="modal-card"></div></div>'; if(MODE==='teams') html+=`<h2 class='section-title'>Teams</h2><p class='copy'>Click any team for a full profile: every match, goals for & against, current form, scorers, and how far they got.</p><div class='grid'>${{DATA.teams.map(teamCard).join('')}}</div>`; else if(MODE==='standings') html+=`<p class='copy'>All 12 groups. Every row includes the flag, team name and 3-character FIFA code — click a team to open the same profile.</p>`+[...new Set(DATA.standings.map(x=>x.group))].map(g=>`<div class='panel'><h3>Group ${{esc(g)}}</h3><table><thead><tr><th>#</th><th>Team</th><th>Code</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GD</th><th>Pts</th></tr></thead><tbody>${{DATA.standings.filter(x=>x.group===g).map(r=>`<tr data-team='${{esc(r.team)}}'><td>${{r.rank}}</td><td><span class='standing-team'><span class='standing-flag'>${{esc(r.flag)}}</span><span>${{esc(r.team)}}</span></span></td><td><span class='code'>${{esc(r.code)}}</span></td><td>${{r.P}}</td><td>${{r.W}}</td><td>${{r.D}}</td><td>${{r.L}}</td><td>${{r.GD}}</td><td><b>${{r.Pts}}</b></td></tr>`).join('')}}</tbody></table></div><br>`).join(''); else html+=`<div class='muted' style='text-align:right;margin-bottom:8px'>Last refreshed: <span id='last-refreshed'></span> • auto refreshes every 30s</div><div class='grid'>${{DATA.matches.filter(m=>MODE==='knockout'?m.stageCode!=='group':true).map(matchCard).join('')}}</div>`; root.innerHTML=html; const refreshed=document.getElementById('last-refreshed'); if(refreshed) refreshed.textContent=new Date().toLocaleTimeString([],{{hour:'numeric',minute:'2-digit',second:'2-digit'}}); document.querySelectorAll('[data-team]').forEach(e=>e.onclick=()=>teamModal(e.dataset.team)); document.querySelectorAll('.match').forEach(e=>e.onclick=()=>e.querySelector('.centre').classList.toggle('open'));}}
render(); setInterval(()=>{{DATA.matches.forEach(m=>document.querySelectorAll(`[data-clock="${{CSS.escape(m.id)}}"]`).forEach(e=>e.textContent=mmss(m)));}},1000); setTimeout(()=>window.parent.location.reload(),30000);
</script>"""

def render_interactive_component(payload: Dict[str, Any], mode: str, height: int = 760) -> None:
    components.html(interactive_component_html(payload, mode), height=height, scrolling=True)

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


def team_profile(team: str, tmatches: pd.DataFrame) -> Dict[str, Any]:
    profile = TEAM_PROFILE_MAP.get(clean_text(team), {})
    finished = tmatches[tmatches["status"] == "Finished"].sort_values("date_time", ascending=False, na_position="last") if not tmatches.empty else pd.DataFrame()
    form = []
    for _, r in finished.head(5).iterrows():
        winner = clean_text(r.get("winner"))
        form.append("W" if winner == team else "D" if winner == "Draw / penalties" else "L")
    return {
        "coach": profile.get("coach", "To be confirmed"),
        "captain": profile.get("captain", "To be confirmed"),
        "ranking": profile.get("ranking", "—"),
        "style": profile.get("form", "Tournament profile will sharpen as results arrive"),
        "form": form or ["—", "—", "—", "—", "—"],
    }


def render_team_profile_card(team: str, tmatches: pd.DataFrame, group: str, code: str) -> None:
    profile = team_profile(team, tmatches)
    badges = "".join(
        f'<span class="wc-form-badge {"win" if x == "W" else "loss" if x == "L" else "draw" if x == "D" else ""}">{esc(x)}</span>'
        for x in profile["form"]
    )
    st.markdown(
        f'''<div class="wc-team-profile"><div class="wc-team-hero"><div class="wc-team-flag-xl">{team_flag(team)}</div><div>
          <div class="wc-hero-kicker">{esc("Group " + group if group else "Team profile")}</div>
          <div class="wc-section-title" style="margin:0;">{team_chip(team)} {f'<span class="team-code">{esc(code)}</span>' if code else ''}</div>
          <div class="subtle">Coach: <b>{esc(profile['coach'])}</b> • Captain: <b>{esc(profile['captain'])}</b> • FIFA ranking: <b>{esc(profile['ranking'])}</b></div>
          <div class="subtle">Identity: {esc(profile['style'])}</div>
          <div class="wc-form-badges"><span class="subtle" style="align-self:center;">Recent form</span>{badges}</div>
        </div></div></div>''',
        unsafe_allow_html=True,
    )


def extract_scorers(matches_df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, m in matches_df.iterrows():
        match_teams = [m.get("home_team"), m.get("away_team")]
        for side in ["home", "away"]:
            team = m.get(f"{side}_team")
            scorers = clean_text(m.get(f"{side}_scorers"))
            if not scorers:
                continue
            # Accept formats like "Messi 23', Alvarez 44'" or simple comma-separated names.
            pieces = re.split(r",|;|\|", scorers)
            for p in pieces:
                name = clean_player_name(p, teams=[team, *match_teams])
                if name:
                    records.append({"player": name, "team": team, "goals": 1})
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).groupby(["player", "team"], as_index=False)["goals"].sum().sort_values("goals", ascending=False)




def scorer_events(row: pd.Series) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    home_key = team_match_key(row.get("home_team")); away_key = team_match_key(row.get("away_team"))

    # Prefer structured live/provider event feeds over fallback scorer-string parsing.
    for item in event_list_from_raw(row, ["events", "timeline", "goals"]):
        typ = clean_text(item.get("type") or item.get("event") or item.get("strTimeline") or item.get("strEvent"))
        if not re.search(r"goal|scor", typ, flags=re.I):
            continue
        team = canonical_team_name(item.get("team") or item.get("team_name") or item.get("strTeam") or item.get("strHomeTeam"))
        player = player_name_from_event(item, teams=[row.get("home_team"), row.get("away_team")])
        minute = to_int(item.get("minute") or item.get("time") or item.get("intTime") or item.get("intTimeline"), 0) or 0
        if team and team_match_key(team) == away_key:
            side = "away"
        elif team and team_match_key(team) == home_key:
            side = "home"
        else:
            logger.info("Skipping goal event with unknown team shape: %s", item)
            continue
        if player:
            events.append({"side": side, "team": team or clean_text(row.get(f"{side}_team")), "player": player, "minute": minute, "label": f"{minute}'" if minute else "Goal", "kind": "Goal"})

    if events:
        return sorted(events, key=lambda e: e.get("minute", 0))

    for side in ["home", "away"]:
        team = clean_text(row.get(f"{side}_team"))
        raw = clean_text(row.get(f"{side}_scorers"))
        if raw:
            for piece in re.split(r",|;|\|", raw):
                player = clean_player_name(piece, teams=[row.get("home_team"), row.get("away_team")])
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
    wanted = [
        ("possession", "Possession"),
        ("shots", "Shots"),
        ("shots_on_target", "Shots on target"),
        ("corners", "Corners"),
        ("fouls", "Fouls"),
        ("offside", "Offside"),
        ("yellow_cards", "Yellow cards"),
        ("red_cards", "Red cards"),
    ]
    found: Dict[str, Tuple[int, int]] = {}
    for key in ["statistics", "stats", "match_stats"]:
        val = raw.get(key)
        if isinstance(val, dict):
            normalized = {re.sub(r"[^a-z0-9]", "_", clean_text(k).lower()).strip("_"): v for k, v in val.items()}
            for stat_key, label in wanted:
                item = normalized.get(stat_key) or normalized.get(stat_key.rstrip("s"))
                if isinstance(item, dict):
                    h = to_int(item.get("home") or item.get("home_team"), None)
                    a = to_int(item.get("away") or item.get("away_team"), None)
                    if h is not None and a is not None:
                        found[label] = (h, a)
    hscore = 0 if pd.isna(row.get("home_score")) else int(row.get("home_score"))
    ascore = 0 if pd.isna(row.get("away_score")) else int(row.get("away_score"))
    stats: List[Tuple[str, int, int]] = [("Goals", hscore, ascore)]
    stats.extend((label, *found.get(label, (0, 0))) for _, label in wanted)
    return stats


def render_stat_comparison(label: str, home_value: int, away_value: int) -> None:
    total = max(1, home_value + away_value)
    hp = int(home_value / total * 100)
    ap = int(away_value / total * 100)
    st.markdown(f'''<div class="wc-stat-row"><div><div style="text-align:right;font-weight:900;">{home_value}</div><div class="wc-stat-bar"><div class="wc-stat-fill-home" style="width:{hp}%"></div></div></div><div class="subtle" style="text-align:center;text-transform:uppercase;font-size:.72rem;font-weight:900;">{esc(label)}</div><div><div style="font-weight:900;">{away_value}</div><div class="wc-stat-bar"><div class="wc-stat-fill-away" style="width:{ap}%"></div></div></div></div>''', unsafe_allow_html=True)


def render_match_centre(row: pd.Series) -> None:
    home = clean_text(row.get("home_team", "TBD"), "TBD")
    away = clean_text(row.get("away_team", "TBD"), "TBD")
    minute = live_minute(row) or ("FT" if row.get("status") == "Finished" else clean_text(row.get("kickoff", "TBD")))
    st.markdown(f'''<div class="wc-centre-hero"><div class="wc-live-meta"><span>{status_badge(row.get('status','Scheduled'))}<span class="tag">{esc(row.get('stage_label',''))}</span></span><span class="wc-live-clock">{client_live_clock_html(row, minute)}</span></div><div class="wc-centre-score"><div>{team_chip(home)}<div class="subtle">{esc(row.get('group',''))}</div></div><strong>{esc(scoreline_label(row))}</strong><div>{team_chip(away)}<div class="subtle">{esc(row.get('venue',''))}</div></div></div></div>''', unsafe_allow_html=True)
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


def event_list_from_raw(row: pd.Series, names: Iterable[str]) -> List[Dict[str, Any]]:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    found: List[Dict[str, Any]] = []
    for key in names:
        val = raw.get(key)
        if isinstance(val, list):
            found.extend([item for item in val if isinstance(item, dict)])
        elif isinstance(val, dict):
            for item in val.values():
                if isinstance(item, dict):
                    found.append(item)
                elif isinstance(item, list):
                    found.extend([x for x in item if isinstance(x, dict)])
    return found


def cards_from_raw(row: pd.Series) -> List[Dict[str, Any]]:
    cards = []
    for item in event_list_from_raw(row, ["cards", "bookings", "events"]):
        label = clean_text(item.get("type") or item.get("event") or item.get("card"))
        if not re.search(r"card|yellow|red", label, flags=re.I):
            continue
        cards.append({
            "minute": clean_text(item.get("minute") or item.get("time") or item.get("elapsed"), "—"),
            "team": clean_text(item.get("team") or item.get("team_name") or item.get("country")),
            "player": clean_text(item.get("player") or item.get("player_name") or item.get("name"), "Unknown player"),
            "card": label.title() if label else "Card",
        })
    return cards


def substitutions_from_raw(row: pd.Series) -> List[Dict[str, Any]]:
    subs = []
    for item in event_list_from_raw(row, ["substitutions", "subs", "events"]):
        label = clean_text(item.get("type") or item.get("event"))
        if label and not re.search(r"sub", label, flags=re.I):
            continue
        player_in = clean_text(item.get("player_in") or item.get("in") or item.get("playerIn") or item.get("player"))
        player_out = clean_text(item.get("player_out") or item.get("out") or item.get("playerOut") or item.get("assist"))
        if not player_in and not player_out:
            continue
        subs.append({
            "minute": clean_text(item.get("minute") or item.get("time") or item.get("elapsed"), "—"),
            "team": clean_text(item.get("team") or item.get("team_name")),
            "in": player_in or "Player in",
            "out": player_out or "Player out",
        })
    return subs


def lineups_from_raw(row: pd.Series) -> Dict[str, List[str]]:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    lineups = raw.get("lineups") or raw.get("lineup") or {}
    result = {"home": [], "away": []}
    if isinstance(lineups, dict):
        for side in ["home", "away"]:
            val = lineups.get(side) or lineups.get(f"{side}_team") or []
            if isinstance(val, dict):
                val = val.get("starting") or val.get("players") or val.get("xi") or []
            if isinstance(val, list):
                result[side] = [clean_text(x.get("name") or x.get("player") if isinstance(x, dict) else x) for x in val][:11]
    return result


def render_live_detail_expander(row: pd.Series, expanded: bool = False) -> None:
    home = clean_text(row.get("home_team", "Home"), "Home")
    away = clean_text(row.get("away_team", "Away"), "Away")
    minute = live_minute(row) or ("FT" if row.get("status") == "Finished" else clean_text(row.get("kickoff", "TBD")))
    with st.expander(f"Match details: {home} vs {away} • {minute}", expanded=expanded):
        st.markdown(f"**Running time:** {minute} &nbsp;&nbsp; **Score:** {scoreline_label(row)} &nbsp;&nbsp; **Stage:** {clean_text(row.get('stage_label'))}")
        home_prob, away_prob = matchup_probabilities(home, away, row)
        st.markdown(probability_row_html(home, away, home_prob, away_prob), unsafe_allow_html=True)
        st.markdown(event_timeline_html(row), unsafe_allow_html=True)
        goals = scorer_events(row)
        cards = cards_from_raw(row)
        subs = substitutions_from_raw(row)
        assists = [name for x in event_list_from_raw(row, ["events", "goals", "assists"]) if (name := clean_player_name(x.get("assist") or x.get("assist_name"), teams=[row.get("home_team"), row.get("away_team")]))]
        lineups = lineups_from_raw(row)
        c1, c2 = st.columns(2)
        with c1:
            st.write("##### Scorers")
            if goals:
                for ev in goals:
                    st.write(f"⚽ {ev.get('label')} — {ev.get('player')} ({ev.get('team')})")
            else:
                st.caption("No scorer details are available from the current feed yet.")
            st.write("##### Assists")
            if assists:
                for name in assists:
                    st.write(f"🅰️ {name}")
            else:
                st.caption("No assist feed is available yet.")
            st.write("##### Cards")
            if cards:
                for ev in cards:
                    st.write(f"🟨 {ev['minute']} — {ev['player']} ({ev['team']}) • {ev['card']}")
            else:
                st.caption("No card feed is available yet.")
        with c2:
            st.write("##### Substitutions")
            if subs:
                for ev in subs:
                    st.write(f"🔁 {ev['minute']} — {ev['in']} for {ev['out']} ({ev['team']})")
            else:
                st.caption("No substitution feed is available yet.")
            st.write("##### Lineups")
            if lineups.get("home") or lineups.get("away"):
                st.markdown(f"**{home}:** " + (", ".join(lineups.get("home", [])) or "Unavailable"))
                st.markdown(f"**{away}:** " + (", ".join(lineups.get("away", [])) or "Unavailable"))
            else:
                st.caption("Lineups are not supplied by the current data source.")
        st.write("##### Match statistics")
        for label, hv, av in match_stat_rows(row):
            render_stat_comparison(label, hv, av)
        with st.expander("Raw source data", expanded=False):
            st.json(row.get("raw") if isinstance(row.get("raw"), dict) else {})


def player_worldcup_rows(player: str, matches_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, m in matches_df.iterrows():
        for ev in scorer_events(m):
            if clean_text(ev.get("player")).lower() == clean_text(player).lower():
                rows.append({"Match": f"{m.get('home_team')} {scoreline_label(m)} {m.get('away_team')}", "Team": ev.get("team"), "Minute": ev.get("label"), "Stage": m.get("stage_label"), "Date": m.get("kickoff")})
    return pd.DataFrame(rows)


def render_player_popup(player: str, matches_df: pd.DataFrame) -> None:
    stats = extract_player_stats(matches_df)
    row = stats[stats["Player"].str.lower() == clean_text(player).lower()].head(1) if not stats.empty else pd.DataFrame()
    title = f"{player} World Cup stats"

    def body() -> None:
        if row.empty:
            st.info("No player statistics are available from the current match feed yet.")
            return
        r = row.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Goals", int(r["G"]))
        c2.metric("Assists in feed", int(r["A"]))
        c3.metric("Open-play goals", int(r["Open"]))
        c4.metric("Penalties", int(r["Pen"]))
        st.markdown(f"**Country:** {team_chip(r['Country'])}", unsafe_allow_html=True)
        goal_rows = player_worldcup_rows(player, matches_df)
        if not goal_rows.empty:
            st.dataframe(goal_rows, use_container_width=True, hide_index=True)
        st.caption("Assists, cards, lineups and advanced stats appear only when the selected data source provides them.")

    if hasattr(st, "dialog"):
        @st.dialog(title, width="large")
        def _dlg():
            body()
        _dlg()
    else:
        st.write(f"### {title}")
        body()


def team_worldcup_stats(team: str, matches_df: pd.DataFrame, standings_df: pd.DataFrame) -> Dict[str, Any]:
    tmatches = filter_matches(matches_df, team=team)
    finished = tmatches[tmatches["status"] == "Finished"] if not tmatches.empty else pd.DataFrame()
    gf = ga = wins = draws = losses = 0
    for _, r in finished.iterrows():
        hs = 0 if pd.isna(r.get("home_score")) else int(r.get("home_score"))
        aw = 0 if pd.isna(r.get("away_score")) else int(r.get("away_score"))
        if r.get("home_team") == team:
            gf += hs; ga += aw
        else:
            gf += aw; ga += hs
        winner = clean_text(r.get("winner"))
        if winner == team:
            wins += 1
        elif winner == "Draw / penalties":
            draws += 1
        else:
            losses += 1
    form = team_profile(team, tmatches).get("form", [])
    next_match = tmatches[tmatches["status"] == "Scheduled"].sort_values("date_time", na_position="last").head(1) if not tmatches.empty else pd.DataFrame()
    standing = standings_df[standings_df["team"] == team].head(1) if not standings_df.empty and "team" in standings_df.columns else pd.DataFrame()
    return {"matches": len(tmatches), "played": len(finished), "wins": wins, "draws": draws, "losses": losses, "gf": gf, "ga": ga, "gd": gf-ga, "form": form, "next": next_match, "standing": standing}


def render_team_popup(team: str, matches_df: pd.DataFrame, standings_df: pd.DataFrame) -> None:
    stats = team_worldcup_stats(team, matches_df, standings_df)
    title = f"{team} World Cup stats"

    def body() -> None:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Played", stats["played"])
        c2.metric("W-D-L", f"{stats['wins']}-{stats['draws']}-{stats['losses']}")
        c3.metric("Goals", f"{stats['gf']}:{stats['ga']}")
        c4.metric("Goal diff", stats["gd"])
        form_html = "".join(f'<span class="wc-form-badge {"win" if x=="W" else "draw" if x=="D" else "loss" if x=="L" else ""}">{esc(x)}</span>' for x in stats["form"])
        st.markdown(f"<div class='wc-team-profile'><b>Recent form</b><br>{form_html}<div class='subtle'>W = win, D = draw, L = loss. Most recent completed matches are shown first.</div></div>", unsafe_allow_html=True)
        if not stats["standing"].empty:
            st.write("##### Group standing")
            cols = [c for c in ["group", "rank", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"] if c in stats["standing"].columns]
            st.dataframe(stats["standing"][cols], use_container_width=True, hide_index=True)
        if not stats["next"].empty:
            st.write("##### Next match")
            render_match_card(stats["next"].iloc[0], compact=True, standings_df=standings_df)
        st.caption("Team stats are calculated from loaded World Cup matches and standings data.")

    if hasattr(st, "dialog"):
        @st.dialog(title, width="large")
        def _dlg():
            body()
        _dlg()
    else:
        st.write(f"### {title}")
        body()


def matchup_probabilities(home: str, away: str, row: pd.Series) -> Tuple[int, int]:
    """Return API win probability or fallback model probability for the match card."""
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    for key in ["probabilities", "win_probability", "odds"]:
        prob = raw.get(key)
        if isinstance(prob, dict):
            hp = to_int(prob.get("home") or prob.get("home_win") or prob.get("homeWinPercentage"), None)
            ap = to_int(prob.get("away") or prob.get("away_win") or prob.get("awayWinPercentage"), None)
            if hp is not None and ap is not None and hp + ap > 0:
                total = hp + ap
                return round(hp / total * 100), round(ap / total * 100)
    home_score = 0 if pd.isna(row.get("home_score")) else int(row.get("home_score"))
    away_score = 0 if pd.isna(row.get("away_score")) else int(row.get("away_score"))
    minute = to_int(live_minute(row).replace("'", "") if live_minute(row) else row.get("elapsed"), 0) or 0
    stage_weight = {"group": 1.0, "r32": 1.08, "r16": 1.12, "qf": 1.16, "sf": 1.2, "third": 1.1, "final": 1.25}.get(clean_text(row.get("stage")), 1.0)
    rank_home = TEAM_PROFILE_MAP.get(home, {}).get("ranking", 45)
    rank_away = TEAM_PROFILE_MAP.get(away, {}).get("ranking", 45)
    strength = max(-18, min(18, (rank_away - rank_home) * 0.7))
    stat_map = {label.lower(): (hv, av) for label, hv, av in match_stat_rows(row)}
    shots = stat_map.get("shots", stat_map.get("total shots", (0, 0)))
    sot = stat_map.get("shots on target", (0, 0))
    poss = stat_map.get("possession", (50, 50))
    reds = stat_map.get("red cards", (0, 0))
    xg = stat_map.get("expected goals", stat_map.get("xg", (0, 0)))
    time_factor = 0.55 + min(45, minute) / 100 if row.get("status") == "Live" else 1.0
    score_component = (home_score - away_score) * 18 * time_factor * stage_weight
    stat_component = (shots[0] - shots[1]) * 0.7 + (sot[0] - sot[1]) * 1.7 + (poss[0] - poss[1]) * 0.12 + (xg[0] - xg[1]) * 4 - (reds[0] - reds[1]) * 8
    home_prob = int(round(max(4, min(96, 50 + strength + score_component + stat_component))))
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
    match_key = clean_text(row.get("match_id")) or str(abs(hash(str(row.to_dict()))))
    detail_key = f"{key_prefix}_{match_key}_details_open"
    if detail_key not in st.session_state:
        st.session_state[detail_key] = row.get("status") == "Live"

    st.markdown(f'''<div class="wc-live-card"><div class="wc-live-meta"><span>{status_badge(row.get('status', 'Scheduled'))}<span class="tag">{esc(row.get('stage_label',''))}</span></span><span class="wc-live-clock">{client_live_clock_html(row, minute)}</span></div><div class="wc-live-teams"><div class="wc-live-team">{team_chip(home)}<div class="subtle">{esc(team_context_line(home, standings_df))}</div></div><div class="wc-live-score">{esc(score)}</div><div class="wc-live-team">{team_chip(away)}<div class="subtle">{esc(team_context_line(away, standings_df))}</div></div></div><div class="subtle" style="text-align:center;margin-top:8px;">{esc(row.get('kickoff','TBD'))}{' • ' + esc(clean_text(row.get('venue'))) if clean_text(row.get('venue')) else ''}</div><div class="wc-timeline"><div class="wc-timeline-fill" style="width:{progress}%;"></div></div>{prob_html}{events_html}<div class="wc-click-hint">Use the match tile control below to expand/collapse timeline, stats and source data</div></div>''', unsafe_allow_html=True)
    if st.button(f"{'Hide' if st.session_state[detail_key] else 'Show'} details: {home} vs {away}", key=f"{key_prefix}_{match_key}_tile_toggle", use_container_width=True):
        st.session_state[detail_key] = not st.session_state[detail_key]
    if standings_df is not None:
        st.markdown('<div class="wc-inline-actions">', unsafe_allow_html=True)
        team_cols = st.columns(2)
        with team_cols[0]:
            if st.button(f"{home} stats", key=f"{key_prefix}_{match_key}_home_team"):
                render_team_popup(home, pd.DataFrame([row]), standings_df)
        with team_cols[1]:
            if st.button(f"{away} stats", key=f"{key_prefix}_{match_key}_away_team"):
                render_team_popup(away, pd.DataFrame([row]), standings_df)
        st.markdown('</div>', unsafe_allow_html=True)
    if st.session_state[detail_key]:
        render_live_detail_expander(row, expanded=True)


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
    route_chips = "".join([
        "<span class='wc-route-chip'>R32 → R16</span>",
        "<span class='wc-route-chip'>R16 → QF</span>",
        "<span class='wc-route-chip'>QF → SF</span>",
        "<span class='wc-route-chip'>SF → Final</span>",
    ])
    html_out = f'''<div class="wc-bracket-shell compact">
      <div class="wc-bracket-board">
        <div class="wc-bracket-side left">
          <div><div class="wc-bracket-round-title">Round of 32</div>{_stack(left['r32'],8)}</div>
          <div><div class="wc-bracket-round-title">Round of 16</div>{_stack(left['r16'],4,'r16')}</div>
          <div><div class="wc-bracket-round-title">Quarterfinals</div>{_stack(left['qf'],2,'qf')}</div>
          <div><div class="wc-bracket-round-title">Semifinal</div>{_stack(left['sf'],1,'sf')}</div>
        </div>
        <div><div class="wc-cup-final">
            <div class="wc-cup-icon">{trophy_image_html("wc-cup-trophy-img")}</div><div class="wc-world-champ">World Champion</div>
            <div style="width:100%; margin-top:10px;">{final_html}</div>
            <div class="subtle" style="margin:8px 0 4px;">Third-place match</div><div style="width:100%;">{third_html}</div>
        </div></div>
        <div class="wc-bracket-side right">
          <div><div class="wc-bracket-round-title">Semifinal</div>{_stack(right['sf'],1,'sf')}</div>
          <div><div class="wc-bracket-round-title">Quarterfinals</div>{_stack(right['qf'],2,'qf')}</div>
          <div><div class="wc-bracket-round-title">Round of 16</div>{_stack(right['r16'],4,'r16')}</div>
          <div><div class="wc-bracket-round-title">Round of 32</div>{_stack(right['r32'],8)}</div>
        </div>
      </div>
      <div class="wc-route-legend">{route_chips}<br>Each lane is ordered by source match date/slot so winners transition left-to-center or right-to-center toward the Final.</div>
    </div>'''
    st.markdown(html_out, unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_openfootball_data(fallback_to_demo: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """Load the GitHub-hosted OpenFootball World Cup 2026 JSON feed."""
    def team_name(value: Any) -> str:
        if isinstance(value, dict):
            return clean_text(value.get("name") or value.get("country") or value.get("code"), "TBD")
        return clean_text(value, "TBD")

    def team_code_from(value: Any) -> str:
        if isinstance(value, dict):
            return clean_text(value.get("code") or value.get("key"))
        return ""

    def score_value(match: Dict[str, Any], side: str) -> Any:
        direct = match.get(f"score{side}")
        if direct is not None:
            return direct
        score = match.get("score") or match.get("result") or {}
        idx = 0 if side == "1" else 1
        if isinstance(score, dict):
            ft = score.get("ft") or score.get("fulltime") or score.get("full_time")
            if isinstance(ft, list) and len(ft) > idx:
                return ft[idx]
            if isinstance(ft, dict):
                for key in (["team1", "home", "score1", "ft1"] if side == "1" else ["team2", "away", "score2", "ft2"]):
                    if key in ft and ft.get(key) is not None:
                        return ft.get(key)
            if side == "1":
                for key in ["ft1", "score1", "team1", "home"]:
                    if key in score and score.get(key) is not None:
                        return score.get(key)
            for key in ["ft2", "score2", "team2", "away"]:
                if key in score and score.get(key) is not None:
                    return score.get(key)
        if isinstance(score, list) and len(score) > idx:
            return score[idx]
        return None

    def detect_schema(raw: Any) -> Tuple[str, List[Dict[str, Any]]]:
        if isinstance(raw, dict) and isinstance(raw.get("rounds"), list):
            return "old rounds schema", raw["rounds"]
        if isinstance(raw, dict) and isinstance(raw.get("matches"), list):
            return "new matches schema", [{"name": "OpenFootball matches", "matches": raw["matches"]}]
        if isinstance(raw, list):
            return "new matches schema", [{"name": "OpenFootball matches", "matches": raw}]
        raise ValueError("OpenFootball JSON did not include a supported rounds or matches collection.")

    def stage_from_match(match: Dict[str, Any], round_name: str) -> Tuple[str, str]:
        raw_stage = clean_text(match.get("stage") or match.get("phase") or match.get("round") or round_name, "Group Stage")
        group = clean_text(match.get("group"))
        if group:
            return "Group Stage", group.replace("Group ", "").strip()
        lowered = raw_stage.lower()
        if raw_stage.startswith("Group "):
            return raw_stage, raw_stage.replace("Group ", "").strip()
        if "matchday" in lowered:
            return "Group Stage", ""
        return raw_stage, ""

    try:
        resp = requests.get(
            OPENFOOTBALL_WORLD_CUP_URL,
            headers={"Accept": "application/json", "User-Agent": "worldcup-dashboard/1.0"},
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json()
        schema_name, rounds = detect_schema(raw)
        logger.info("Detected OpenFootball %s", schema_name)
        try:
            st.session_state["openfootball_schema"] = schema_name
        except Exception:
            pass

        games = []
        team_groups: Dict[str, str] = {}
        team_codes: Dict[str, str] = {}
        stadium_rows: Dict[str, Dict[str, Any]] = {}
        for rnd in rounds:
            if not isinstance(rnd, dict):
                continue
            round_name = clean_text(rnd.get("name") or rnd.get("round"), "Group Stage")
            matches = rnd.get("matches") or []
            if not isinstance(matches, list):
                continue
            for m in matches:
                if not isinstance(m, dict):
                    continue
                team1_raw = m.get("team1") or m.get("home") or m.get("home_team") or {}
                team2_raw = m.get("team2") or m.get("away") or m.get("away_team") or {}
                home = team_name(team1_raw)
                away = team_name(team2_raw)
                home_code = team_code_from(team1_raw)
                away_code = team_code_from(team2_raw)
                if home != "TBD" and home_code:
                    team_codes[home] = home_code
                if away != "TBD" and away_code:
                    team_codes[away] = away_code
                round_stage, group = stage_from_match(m, round_name)
                if group in GROUPS:
                    if home != "TBD":
                        team_groups[home] = group
                    if away != "TBD":
                        team_groups[away] = group
                venue = m.get("stadium") or m.get("venue") or m.get("ground") or {}
                if isinstance(venue, dict):
                    venue_name = clean_text(venue.get("name") or venue.get("stadium"))
                    city = clean_text(venue.get("city"))
                else:
                    venue_name = clean_text(venue)
                    city = ""
                if venue_name:
                    stadium_rows[venue_name] = {"stadium_id": venue_name, "stadium": venue_name, "city": city, "country": "", "capacity": None}
                games.append({
                    "id": clean_text(m.get("num") or m.get("id") or f"of-{len(games)+1}"),
                    "date": clean_text(m.get("date") or m.get("datetime") or m.get("kickoff")) + (" " + clean_text(m.get("time")) if clean_text(m.get("time")) else ""),
                    "home_team": home,
                    "away_team": away,
                    "home_score": score_value(m, "1"),
                    "away_score": score_value(m, "2"),
                    "home_scorers": m.get("goals1", ""),
                    "away_scorers": m.get("goals2", ""),
                    "group": group,
                    "stage": round_stage,
                    "status": "Finished" if score_value(m, "1") is not None and score_value(m, "2") is not None else "Scheduled",
                    "stadium_id": venue_name,
                    "raw": m,
                })
        matches = normalize_matches(games)
        team_names = sorted({t for t in (set(matches.get("home_team", [])) | set(matches.get("away_team", []))) if clean_text(t) and clean_text(t) != "TBD"}) if not matches.empty else []
        teams = pd.DataFrame([{"team": t, "code": team_codes.get(t, ""), "group": team_groups.get(t, ""), "flag": FALLBACK_FLAGS.get(t, "⚽")} for t in team_names])
        stadiums = pd.DataFrame(stadium_rows.values())
        groups = calculate_standings_from_matches(matches, teams)
        return matches, teams, groups, stadiums, f"OpenFootball GitHub JSON ({schema_name})"
    except Exception as exc:
        if not fallback_to_demo:
            raise RuntimeError(str(exc)) from exc
        matches, teams, groups, stadiums, source = load_fallback()
        return matches, teams, groups, stadiums, source




def canonical_team_name(value: Any) -> str:
    text = clean_text(value)
    aliases = {
        "us": "United States", "usa": "United States", "united states of america": "United States",
        "cote d'ivoire": "Ivory Coast", "côte d’ivoire": "Ivory Coast", "côte d'ivoire": "Ivory Coast",
        "korea republic": "South Korea", "republic of korea": "South Korea",
        "ir iran": "Iran", "turkiye": "Turkey", "cabo verde": "Cape Verde",
    }
    return aliases.get(text.lower(), text)


def team_match_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", canonical_team_name(value).lower())


@st.cache_data(ttl=30, show_spinner=False)
def fetch_public_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    resp = requests.get(
        url,
        params=params,
        headers={"Accept": "application/json", "User-Agent": "worldcup-dashboard/1.0"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def source_labels_text(statuses: Dict[str, str]) -> str:
    """Render the data-provider chain without promoting demo data as primary."""
    labels = ["Live API", "ESPN", "TheSportsDB", "API-Football", "OpenFootball fallback"]
    rendered = []
    for label in labels:
        status = statuses.get(label, "")
        icon = "✓" if status == "ok" else "↳" if status == "fallback" else "⚠"
        rendered.append(f"{icon} {label}")
    return " • ".join(rendered)


def load_default_data(api_base: str, token: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """Experimental enrichment mode: start with Live API, then overlay only safe ESPN/TheSportsDB fields."""
    statuses = {"Live API": "", "ESPN": "", "TheSportsDB": "", "API-Football": "", "OpenFootball fallback": ""}
    try:
        matches, teams, groups, stadiums, _source = load_live_data(api_base, token, fallback_to_demo=False)
        statuses["Live API"] = "ok"
    except Exception as api_exc:
        statuses["Live API"] = f"unavailable: {api_exc}"
        try:
            matches, teams, groups, stadiums, _source = load_openfootball_data(fallback_to_demo=False)
            statuses["OpenFootball fallback"] = "fallback"
        except Exception as of_exc:
            matches, teams, groups, stadiums, _source = load_fallback()
            statuses["OpenFootball fallback"] = f"demo fallback: {of_exc}"

    matches, espn_source = apply_espn_overlay(matches)
    statuses["ESPN"] = "ok" if "unavailable" not in espn_source.lower() else espn_source
    matches, api_football_source = apply_api_football_overlay(matches)
    statuses["API-Football"] = "ok" if "unavailable" not in api_football_source.lower() and "not configured" not in api_football_source.lower() else api_football_source
    matches, teams, tdb_source = apply_thesportsdb_enrichment(matches, teams)
    statuses["TheSportsDB"] = "ok" if "unavailable" not in tdb_source.lower() else tdb_source
    return matches, teams, groups, stadiums, "Experimental enrichment • " + source_labels_text(statuses)



def data_quality_label(source: str) -> str:
    source_lower = clean_text(source).lower()
    if "demo" in source_lower:
        return "Demo fallback"
    if "experimental" in source_lower or ("openfootball" in source_lower and ("espn" in source_lower or "thesportsdb" in source_lower)):
        return "Experimental enrichment"
    if "espn" in source_lower or "thesportsdb" in source_lower:
        return "Enriched"
    if "live api" in source_lower:
        return "Clean Live API"
    return "Enriched"

def normalize_espn_status(competition: Dict[str, Any], status: Dict[str, Any]) -> str:
    state = clean_text(status.get("type", {}).get("state") or status.get("type", {}).get("name") or status.get("type", {}).get("description")).lower()
    completed = status.get("type", {}).get("completed") or competition.get("status", {}).get("type", {}).get("completed")
    if completed or state in {"post", "final", "full time"}:
        return "Finished"
    if state in {"in", "pre-halftime", "in progress"}:
        return "Live"
    return "Scheduled"


def espn_competitor_map(competition: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out = {"home": {}, "away": {}}
    for comp in competition.get("competitors", []) or []:
        side = clean_text(comp.get("homeAway"))
        team = comp.get("team") or {}
        if side in out:
            out[side] = {"name": canonical_team_name(team.get("displayName") or team.get("shortDisplayName") or team.get("name")), "score": to_int(comp.get("score"), None), "raw": comp}
    return out


def espn_events_from_summary(summary: Dict[str, Any], home: str, away: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for item in summary.get("scoringPlays", []) or []:
        team_name = canonical_team_name((item.get("team") or {}).get("displayName") or item.get("team"))
        player = player_name_from_event(item, teams=[home, away])
        if player:
            events.append({"type": "Goal", "event": "Goal", "minute": clean_text(item.get("clock", {}).get("displayValue") or item.get("minute")), "team": team_name, "player": player, "source": "ESPN"})
    for item in summary.get("keyEvents", []) or summary.get("events", []) or []:
        typ = clean_text(item.get("type", {}).get("text") or item.get("type") or item.get("playType") or item.get("text"))
        team_name = canonical_team_name((item.get("team") or {}).get("displayName") or item.get("team"))
        player = player_name_from_event(item, teams=[home, away])
        if re.search(r"goal|scor", typ, flags=re.I) and not player:
            continue
        if player:
            events.append({"type": typ, "event": typ, "minute": clean_text(item.get("clock", {}).get("displayValue") or item.get("minute")), "team": team_name, "player": player, "source": "ESPN"})
    return events


def espn_stats_from_summary(summary: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    stats: Dict[str, Dict[str, int]] = {}
    box = summary.get("boxscore") or {}
    for team_block in box.get("teams", []) or []:
        side = clean_text(team_block.get("homeAway"))
        for stat in team_block.get("statistics", []) or []:
            label = clean_text(stat.get("name") or stat.get("label") or stat.get("displayName")).lower().replace(" ", "_")
            val = to_int(str(stat.get("displayValue") or stat.get("value") or "").replace("%", ""), None)
            if label and val is not None:
                stats.setdefault(label, {})[side] = val
    return stats


def lineups_from_espn_summary(summary: Dict[str, Any]) -> Dict[str, List[str]]:
    result = {"home": [], "away": []}
    for team_block in (summary.get("boxscore") or {}).get("players", []) or []:
        side = clean_text(team_block.get("homeAway"))
        athletes = []
        for group in team_block.get("statistics", []) or []:
            athletes.extend(group.get("athletes", []) or [])
        names = [clean_text((a.get("athlete") or {}).get("displayName") or a.get("displayName")) for a in athletes]
        if side in result:
            result[side] = [n for n in names if n][:11]
    return result


def apply_espn_overlay(matches: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    if matches.empty:
        return matches, "ESPN unavailable"
    try:
        board = fetch_public_json(ESPN_SCOREBOARD_URL)
    except Exception as exc:
        return matches, f"ESPN unavailable ({exc})"
    df = matches.copy()
    event_count = 0
    for event in board.get("events", []) or []:
        comp = (event.get("competitions") or [{}])[0]
        teams = espn_competitor_map(comp)
        home, away = teams.get("home", {}).get("name"), teams.get("away", {}).get("name")
        if not home or not away:
            continue
        mask = ((df["home_team"].map(team_match_key) == team_match_key(home)) & (df["away_team"].map(team_match_key) == team_match_key(away))) | ((df["home_team"].map(team_match_key) == team_match_key(away)) & (df["away_team"].map(team_match_key) == team_match_key(home)))
        if not mask.any():
            continue
        idx = df[mask].index[0]
        event_id = clean_text(event.get("id"))
        status = event.get("status") or comp.get("status") or {}
        df.at[idx, "status"] = normalize_espn_status(comp, status)
        df.at[idx, "elapsed"] = clean_text(status.get("displayClock") or status.get("type", {}).get("shortDetail") or status.get("type", {}).get("detail"))
        if teams["home"].get("score") is not None:
            df.at[idx, "home_score"] = teams["home"].get("score") if team_match_key(df.at[idx, "home_team"]) == team_match_key(home) else teams["away"].get("score")
            df.at[idx, "away_score"] = teams["away"].get("score") if team_match_key(df.at[idx, "away_team"]) == team_match_key(away) else teams["home"].get("score")
        raw = df.at[idx, "raw"] if isinstance(df.at[idx, "raw"], dict) else {}
        raw.setdefault("sources", {})["live_overlay"] = "ESPN"
        raw["espn_event_id"] = event_id
        raw["espn_scoreboard"] = event
        try:
            summary = fetch_public_json(ESPN_SUMMARY_URL, {"event": event_id}) if event_id else {}
            raw["espn_summary"] = summary
            raw.setdefault("events", []).extend(espn_events_from_summary(summary, home, away))
            raw["stats"] = {**raw.get("stats", {}), **espn_stats_from_summary(summary)}
            raw["lineups"] = lineups_from_espn_summary(summary) or raw.get("lineups", {})
        except Exception as exc:
            raw["espn_summary_error"] = str(exc)
        df.at[idx, "raw"] = raw
        event_count += 1
    df["score"] = df.apply(lambda r: "TBD" if pd.isna(r.get("home_score")) or pd.isna(r.get("away_score")) else f"{int(r['home_score'])}-{int(r['away_score'])}", axis=1)
    df["winner"] = df.apply(match_winner, axis=1)
    return df, f"ESPN scoreboard/summary ({event_count} matched)"


def fetch_api_football_json(path: str, key: str, params: Optional[Dict[str, Any]] = None) -> Any:
    resp = requests.get(
        f"{API_FOOTBALL_BASE.rstrip('/')}/{path.lstrip('/')}",
        params=params,
        headers={"Accept": "application/json", "x-apisports-key": key},
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if errors:
        raise RuntimeError(f"API-Football error: {errors}")
    return payload


def api_football_status(short_status: Any, elapsed: Any) -> str:
    status = clean_text(short_status).upper()
    if status in {"FT", "AET", "PEN"}:
        return "Finished"
    if status in {"1H", "2H", "HT", "ET", "BT", "P", "LIVE"} or to_int(elapsed, None):
        return "Live"
    return "Scheduled"


def apply_api_football_overlay(matches: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """Overlay API-Football when configured, using it for live score/status/events/stats."""
    key = secret("API_FOOTBALL_KEY") or secret("APIFOOTBALL_KEY")
    if not key:
        return matches, "API-Football not configured"
    if matches.empty:
        return matches, "API-Football unavailable"
    try:
        payload = fetch_api_football_json(
            "/fixtures",
            key,
            {"league": API_FOOTBALL_WORLD_CUP_LEAGUE, "season": API_FOOTBALL_SEASON},
        )
    except Exception as exc:
        return matches, f"API-Football unavailable ({exc})"
    fixtures = payload.get("response", []) if isinstance(payload, dict) else []
    df = matches.copy()
    matched = 0
    for fixture in fixtures:
        teams = fixture.get("teams") or {}
        home = canonical_team_name((teams.get("home") or {}).get("name"))
        away = canonical_team_name((teams.get("away") or {}).get("name"))
        if not home or not away:
            continue
        mask = ((df["home_team"].map(team_match_key) == team_match_key(home)) & (df["away_team"].map(team_match_key) == team_match_key(away))) | ((df["home_team"].map(team_match_key) == team_match_key(away)) & (df["away_team"].map(team_match_key) == team_match_key(home)))
        if not mask.any():
            continue
        idx = df[mask].index[0]
        goals = fixture.get("goals") or {}
        status = (fixture.get("fixture") or {}).get("status") or {}
        api_home_first = team_match_key(df.at[idx, "home_team"]) == team_match_key(home)
        if goals.get("home") is not None and goals.get("away") is not None:
            df.at[idx, "home_score"] = goals.get("home") if api_home_first else goals.get("away")
            df.at[idx, "away_score"] = goals.get("away") if api_home_first else goals.get("home")
        df.at[idx, "status"] = api_football_status(status.get("short"), status.get("elapsed"))
        df.at[idx, "elapsed"] = clean_text(status.get("elapsed") or status.get("long") or status.get("short"))
        raw = df.at[idx, "raw"] if isinstance(df.at[idx, "raw"], dict) else {}
        raw.setdefault("sources", {})["live_overlay"] = "API-Football"
        raw["api_football_fixture"] = fixture
        fixture_id = clean_text((fixture.get("fixture") or {}).get("id"))
        try:
            if fixture_id:
                events_payload = fetch_api_football_json("/fixtures/events", key, {"fixture": fixture_id})
                fixture["events"] = events_payload.get("response", []) if isinstance(events_payload, dict) else []
        except Exception as exc:
            raw["api_football_events_error"] = str(exc)
        try:
            if fixture_id:
                stats_payload = fetch_api_football_json("/fixtures/statistics", key, {"fixture": fixture_id})
                fixture["statistics"] = stats_payload.get("response", []) if isinstance(stats_payload, dict) else []
        except Exception as exc:
            raw["api_football_statistics_error"] = str(exc)
        event_rows = []
        for ev in fixture.get("events", []) or []:
            team_name = canonical_team_name((ev.get("team") or {}).get("name"))
            player = player_name_from_event({"player": ev.get("player"), "assist": ev.get("assist")}, teams=[home, away])
            assist = player_name_from_event({"player": ev.get("assist")}, teams=[home, away])
            event_rows.append({
                "type": clean_text(ev.get("type") or ev.get("detail")),
                "event": clean_text(ev.get("detail") or ev.get("type")),
                "minute": clean_text((ev.get("time") or {}).get("elapsed")),
                "team": team_name,
                "player": player,
                "assist": assist,
                "source": "API-Football",
            })
        if event_rows:
            raw.setdefault("events", []).extend([e for e in event_rows if e.get("player") or e.get("assist")])
        stats = {}
        for team_stats in fixture.get("statistics", []) or []:
            side_name = canonical_team_name((team_stats.get("team") or {}).get("name"))
            side = "home" if team_match_key(side_name) == team_match_key(df.at[idx, "home_team"]) else "away"
            for stat in team_stats.get("statistics", []) or []:
                key_name = re.sub(r"[^a-z0-9]", "_", clean_text(stat.get("type")).lower()).strip("_")
                if key_name:
                    stats.setdefault(key_name, {})[side] = to_int(str(stat.get("value")).replace("%", ""), 0)
        if stats:
            raw["stats"] = {**raw.get("stats", {}), **stats}
        df.at[idx, "raw"] = raw
        matched += 1
    df["score"] = df.apply(lambda r: "TBD" if pd.isna(r.get("home_score")) or pd.isna(r.get("away_score")) else f"{int(r['home_score'])}-{int(r['away_score'])}", axis=1)
    df["winner"] = df.apply(match_winner, axis=1)
    return df, f"API-Football fixtures ({matched} matched)"


def apply_thesportsdb_enrichment(matches: pd.DataFrame, teams: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    try:
        season = fetch_public_json(f"{THESPORTSDB_API_BASE}/eventsseason.php", {"id": THESPORTSDB_LEAGUE_ID, "s": THESPORTSDB_SEASON})
        today = fetch_public_json(f"{THESPORTSDB_API_BASE}/eventsday.php", {"d": date.today().isoformat(), "l": "FIFA World Cup"})
    except Exception as exc:
        return matches, teams, f"TheSportsDB unavailable ({exc})"
    events = (season.get("events") or []) + (today.get("events") or [])
    df = matches.copy()
    tdf = teams.copy()
    matched = 0
    for ev in events:
        home = canonical_team_name(ev.get("strHomeTeam")); away = canonical_team_name(ev.get("strAwayTeam"))
        if not home or not away:
            continue
        mask = ((df["home_team"].map(team_match_key) == team_match_key(home)) & (df["away_team"].map(team_match_key) == team_match_key(away)))
        if not mask.any():
            continue
        idx = df[mask].index[0]
        raw = df.at[idx, "raw"] if isinstance(df.at[idx, "raw"], dict) else {}
        raw.setdefault("sources", {})["enrichment"] = "TheSportsDB"
        raw["thesportsdb_event"] = ev
        for side, key in [("home", "strHomeGoalDetails"), ("away", "strAwayGoalDetails")]:
            incoming = clean_text(ev.get(key)).replace(";", ", ")
            existing = clean_text(df.at[idx, f"{side}_scorers"])
            if incoming and not existing and valid_scorer_string(incoming, teams=[df.at[idx, "home_team"], df.at[idx, "away_team"]]):
                df.at[idx, f"{side}_scorers"] = incoming
            elif incoming and existing:
                logger.info("Keeping primary scorer data for %s; TheSportsDB scorer enrichment skipped", df.at[idx, "match_id"])
        if clean_text(ev.get("idEvent")):
            try:
                timeline = fetch_public_json(f"{THESPORTSDB_API_BASE}/lookuptimeline.php", {"id": ev.get("idEvent")})
                raw.setdefault("events", []).extend([{**x, "source": "TheSportsDB"} for x in (timeline.get("timeline") or []) if isinstance(x, dict)])
            except Exception as exc:
                raw["thesportsdb_timeline_error"] = str(exc)
        df.at[idx, "raw"] = raw
        matched += 1
        for team_name, badge_key in [(home, "strHomeTeamBadge"), (away, "strAwayTeamBadge")]:
            if not tdf.empty and team_match_key(team_name) in set(tdf["team"].map(team_match_key)) and clean_text(ev.get(badge_key)):
                tdf.loc[tdf["team"].map(team_match_key) == team_match_key(team_name), "flag"] = ev.get(badge_key)
    return df, tdf, f"TheSportsDB eventsday/lookuptimeline/eventsseason ({matched} enriched)"


def build_normalized_secondary_frames(matches: pd.DataFrame, teams: pd.DataFrame, standings: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    players_df = extract_player_stats(matches)
    event_rows, stat_rows, prob_rows = [], [], []
    for _, row in matches.iterrows():
        home, away = clean_text(row.get("home_team")), clean_text(row.get("away_team"))
        hp, ap = matchup_probabilities(home, away, row)
        prob_rows.append({"match_id": row.get("match_id"), "home_team": home, "away_team": away, "home_win_probability": hp, "away_win_probability": ap, "source": "API or fallback model"})
        for ev in scorer_events(row) + cards_from_raw(row) + substitutions_from_raw(row):
            event_rows.append({"match_id": row.get("match_id"), "home_team": home, "away_team": away, **ev})
        for label, hv, av in match_stat_rows(row):
            stat_rows.append({"match_id": row.get("match_id"), "stat": label, "home": hv, "away": av, "source": "ESPN/TheSportsDB/local"})
    return players_df, pd.DataFrame(event_rows), pd.DataFrame(stat_rows), pd.DataFrame(prob_rows)


def clean_player_name(name: Any, teams: Optional[Iterable[Any]] = None) -> str:
    name = clean_text(name)
    name = re.sub(r"[{}\[\]\"`]+", "", name)
    name = re.sub(r"\b(goal|penalty|own goal|og|assist|card)\b", "", name, flags=re.I)
    name = re.sub(r"\d+['’]?(\+\d+)?", "", name)
    name = re.sub(r"\s+", " ", name).strip(" -•,:;")
    return name if valid_player_name(name, teams=teams) else ""


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
                name = clean_player_name(raw, teams=[team, m.get("home_team"), m.get("away_team")])
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


def player_card_html(r: pd.Series) -> str:
    player = clean_text(r["Player"])
    meta = PLAYER_PROFILE_MAP.get(player, {})
    club = meta.get("club", "Club unavailable")
    position = meta.get("position", "Player")
    age = meta.get("age", "—")
    return f'''<div class="wc-player-card"><div class="wc-player-card-top">{player_photo_html(player)}
        <div><b>{player_link(player, esc(player))}</b><div class="wc-player-meta">{team_chip(r['Country'])} • {esc(position)} • {esc(club)} • Age {esc(age)}</div></div>
      </div><div class="wc-player-statline">
        <div class="wc-player-stat"><b>{int(r['G'])}</b><span>Goals</span></div>
        <div class="wc-player-stat"><b>{int(r['A'])}</b><span>Assists</span></div>
        <div class="wc-player-stat"><b>{int(r['Open'])}</b><span>Open</span></div>
        <div class="wc-player-stat"><b>{int(r['Pen'])}</b><span>Pens</span></div>
      </div></div>'''


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
        requested_player = clean_text(st.query_params.get("player", ""))
        search = st.text_input("Search player", value=requested_player, placeholder="e.g. Messi, Mbappé, Kane")
    with f3:
        sort_by = st.selectbox("Sort by", ["G", "G+A", "Open", "Pen", "A"])
    out = players.copy()
    if country != "All countries":
        out = out[out["Country"] == country]
    if search:
        out = out[out["Player"].str.contains(re.escape(search), case=False, na=False)]
    out = out.sort_values([sort_by, "G", "Player"], ascending=[False, False, True]).reset_index(drop=True)
    st.write("#### Featured player cards")
    st.markdown('<div class="wc-player-grid">' + "".join(player_card_html(r) for _, r in out.head(6).iterrows()) + "</div>", unsafe_allow_html=True)
    detail_cols = st.columns(3)
    for i, r in enumerate(out.head(6).itertuples()):
        with detail_cols[i % 3]:
            if st.button(f"{r.Player} stats", key=f"player_popup_card_{i}_{r.Player}"):
                render_player_popup(r.Player, matches_df)
    st.write("#### Full player table")
    rows = []
    for idx, r in out.iterrows():
        player = clean_text(r["Player"])
        rows.append(f'''<tr style="border-top:1px solid rgba(148,163,184,.18);">
            <td style="padding:12px; color:#94a3b8;">{idx+1}</td>
            <td style="padding:12px;"><span class="wc-player-name">{player_photo_html(player)}{player_link(player, esc(player))}</span></td>
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
    if not out.empty:
        st.write("#### Player quick links")
        quick_cols = st.columns(3)
        for i, player in enumerate(out["Player"].head(12).tolist()):
            with quick_cols[i % 3]:
                if st.button(f"{player} stats", key=f"player_popup_table_{i}_{player}"):
                    render_player_popup(player, matches_df)


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
                html += f'<div class="wc-rank-row"><div class="wc-rank-num">{i}</div><div><b>{player_link(r.Player, esc(r.Player))}</b><br><span class="wc-small">{team_flag(r.Country)} {r.Country}</span></div><div class="wc-bar"><div class="wc-bar-fill" style="width:{width}%;"></div></div><b>{int(r.G)}</b></div>'
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
    current_stage, _current_stage_detail = get_current_stage_metric(matches_df)

    cache_note = "30 seconds" if "Live API" in source else "1 hour"
    quality = data_quality_label(source)
    st.caption(f"Data source: {source} • Cache: {cache_note} • Data quality: {quality}")
    st.markdown(f"<span class='tag'>Data quality: {esc(quality)}</span>", unsafe_allow_html=True)

    st.markdown("### Tournament Dashboard")
    st.markdown(f"<div class='explain'><b>Overview shows:</b> current tournament status, live or next match, completed-match progress, goal pace, and headline summary cards. {explain_current_stage(matches_df)} New to football? Start with the <a class='wc-basics-link' href='?tab=Football%20101' target='_self'>Football 101</a> tab for quick rules and tournament basics.</div><div class='wc-overview-spacer'></div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_stat_card("✅", f"{len(finished)} / {total_matches}", "Matches completed")
    with c2:
        render_stat_card("🔴", len(live), "Live now")
    with c3:
        render_stat_card("⚽", total_goals, f"Goals • {avg_goals:.2f}/match")
    with c4:
        render_stat_card("🏁", current_stage, "Current stage")

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
        "Every live match is pinned at the top. Click a match tile control for the live clock, timeline, scorers, comparison bars and source stats."
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
    st.markdown('<div class="wc-route-legend">Solid gold connector rails trace each stage from the Round of 32 toward the FIFA World Cup Final.</div>', unsafe_allow_html=True)
    st.write("#### Round-by-round details")
    tabs = st.tabs([STAGE_LABELS[s] for s in STAGE_ORDER if s != "group" and s in set(knockout["stage"])])
    for tab, stage_code in zip(tabs, [s for s in STAGE_ORDER if s != "group" and s in set(knockout["stage"])]):
        with tab:
            sdf = knockout[knockout["stage"] == stage_code].sort_values("date_time", na_position="last")
            cols = st.columns(2)
            for idx, (_, row) in enumerate(sdf.iterrows()):
                with cols[idx % 2]:
                    render_match_card(row, standings_df=standings_df)


def team_tournament_status(team: str, matches_df: pd.DataFrame) -> Tuple[str, str]:
    """Return ('still-in'|'eliminated', friendly status) for team cards."""
    name = clean_text(team)
    if not name or matches_df.empty:
        return "still-in", "Still in it"
    tmatches = filter_matches(matches_df, team=name).copy()
    if tmatches.empty:
        return "still-in", "Still in it"
    finished_ko = tmatches[(tmatches.get("stage", "") != "group") & (tmatches.get("status", "") == "Finished")].copy()
    if not finished_ko.empty:
        latest = finished_ko.sort_values("date_time", ascending=False, na_position="last").iloc[0]
        if clean_text(latest.get("winner")) != name:
            return "eliminated", f"Out — {clean_text(latest.get('stage_label'), 'Knockout')}"
    if not tmatches[tmatches.get("status", "") != "Finished"].empty:
        return "still-in", "Still in it"
    finished = tmatches[tmatches.get("status", "") == "Finished"]
    if not finished.empty and clean_text(finished.sort_values("date_time", ascending=False, na_position="last").iloc[0].get("stage")) == "group":
        return "eliminated", "Out — group stage"
    return "still-in", "Still in it"


def team_card_html(team: str, matches_df: pd.DataFrame, teams_df: pd.DataFrame, standings_df: pd.DataFrame) -> str:
    row = teams_df[teams_df["team"] == team].iloc[0] if not teams_df.empty and not teams_df[teams_df["team"] == team].empty else None
    group = clean_text(row.get("group") if row is not None else "")
    code = clean_text(row.get("code") if row is not None else "") or team_code(team)
    status_key, status_label = team_tournament_status(team, matches_df)
    recent = filter_matches(matches_df, team=team)
    form = []
    for _, m in recent[recent["status"] == "Finished"].sort_values("date_time", ascending=False, na_position="last").head(3).iterrows():
        winner = clean_text(m.get("winner"))
        form.append(("W", "win") if winner == team else (("D", "draw") if winner in {"", "Draw / penalties"} else ("L", "loss")))
    if not form:
        form = [("—", "draw")]
    form_html = "".join(f'<span class="wc-mini-form {cls}">{label}</span>' for label, cls in form)
    group_html = f"Group {esc(group)}" if group else "Group TBD"
    href = app_link("Teams", team=team)
    return f'''<a class="wc-team-card" data-status="{status_key}" href="{href}" target="_self">
      <div class="wc-team-card-top"><span class="wc-team-card-flag">{flag_img(team)}</span><span class="wc-team-card-name">{esc(team)}</span><span class="team-code">{esc(code)}</span></div>
      <div class="wc-team-card-group">{group_html}</div>
      <div class="wc-team-card-bottom"><span class="wc-team-status {status_key}">{esc(status_label)}</span><span class="wc-team-form">{form_html}</span></div>
    </a>'''


def render_teams_tab(matches_df: pd.DataFrame, teams_df: pd.DataFrame, standings_df: pd.DataFrame) -> None:
    st.markdown('<div class="wc-section-title">Teams</div>', unsafe_allow_html=True)
    st.markdown("Click any team for a full profile: every match, goals for & against, current form, scorers, and how far they got.")
    all_teams = sorted(set(teams_df["team"].dropna()) if not teams_df.empty else (set(matches_df["home_team"]) | set(matches_df["away_team"])))
    if not all_teams:
        st.info("No teams loaded.")
        return
    requested_team = clean_text(st.query_params.get("team", ""))
    requested_filter = clean_text(st.query_params.get("team_filter", "All"), "All")
    filter_options = ["All", "Still in it", "Eliminated"]
    if requested_filter not in filter_options:
        requested_filter = "All"
    filter_links = []
    for option in filter_options:
        cls = "wc-team-filter-pill active" if option == requested_filter else "wc-team-filter-pill"
        filter_links.append(f'<a class="{cls}" href="{app_link("Teams", team_filter=option)}" target="_self">{esc(option)}</a>')
    st.markdown('<div class="wc-team-filter-row">' + ''.join(filter_links) + '</div>', unsafe_allow_html=True)
    visible_teams = []
    for team in all_teams:
        status_key, _ = team_tournament_status(team, matches_df)
        if requested_filter == "Still in it" and status_key != "still-in":
            continue
        if requested_filter == "Eliminated" and status_key != "eliminated":
            continue
        visible_teams.append(team)
    cards = [team_card_html(team, matches_df, teams_df, standings_df) for team in visible_teams]
    st.markdown(f'<div class="wc-team-card-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
    favorite = requested_team if requested_team in all_teams else (visible_teams[0] if visible_teams else all_teams[0])
    st.markdown("---")
    st.write(f"#### {favorite} profile")
    team_rows = teams_df[teams_df["team"] == favorite] if not teams_df.empty else pd.DataFrame()
    group = clean_text(team_rows.iloc[0].get("group") if not team_rows.empty else "")
    code = clean_text(team_rows.iloc[0].get("code") if not team_rows.empty else "")
    tmatches = filter_matches(matches_df, team=favorite)
    render_team_profile_card(favorite, tmatches, group, code)
    if st.button(f"Open {favorite} World Cup stats", key=f"team_popup_{favorite}"):
        render_team_popup(favorite, matches_df, standings_df)
    finished = tmatches[tmatches["status"] == "Finished"]
    wins = int((finished["winner"] == favorite).sum()) if not finished.empty else 0
    goals_for = goals_against = 0
    for _, r in finished.iterrows():
        if r["home_team"] == favorite:
            goals_for += int(r["home_score"]) if not pd.isna(r["home_score"]) else 0
            goals_against += int(r["away_score"]) if not pd.isna(r["away_score"]) else 0
        elif r["away_team"] == favorite:
            goals_for += int(r["away_score"]) if not pd.isna(r["away_score"]) else 0
            goals_against += int(r["home_score"]) if not pd.isna(r["home_score"]) else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Matches", len(tmatches)); c2.metric("Wins", wins); c3.metric("Goals for", goals_for); c4.metric("Goal diff", goals_for - goals_against)
    if group and not standings_df.empty:
        st.write(f"#### Group {group} table")
        gdf = standings_df[standings_df["group"].astype(str).str.upper() == group.upper()].copy()
        if not gdf.empty:
            gdf = gdf.sort_values(["Pts", "GD", "GF"], ascending=[False, False, False], na_position="last")
            gdf["Rank"] = range(1, len(gdf) + 1)
            gdf["Team"] = gdf["team"].map(lambda t: f"{team_flag(t)} {t} {team_code(t)}")
            st.dataframe(gdf[["Rank", "Team", "Pts", "GD", "GF", "GA"]], use_container_width=True, hide_index=True)
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
        - Start with **Overview** for the current tournament situation, next match, live match, goals and headline story cards.
        - Use **Upcoming & Live** for live running time, score, scorers, cards, lineups, substitutions and the match centre.
        - Use **Groups & Standings** to see who is leading and who needs points.
        - Use **Knockout Bracket** to follow the route from Round of 32 → Round of 16 → Quarterfinals → Semifinals → Final.
        - Use **Teams** and click a team detail button to see World Cup record, goals, next match and form.
        - Use **Players** and click a player detail button to see goals, penalty goals and match-by-match scoring rows.

        #### Form, standings and app terms
        - **Form** is recent results. **W** means win, **D** means draw, and **L** means loss.
        - A form line like `W W D L W` means the team won, won, drew, lost and won across recent completed matches.
        - **P** = played, **W** = wins, **D** = draws, **L** = losses.
        - **GF** = goals for, **GA** = goals against, **GD** = goal difference, **Pts** = points.
        - **Scheduled** means the match has not started. **Live** means it is being played now. **Finished** means it is complete.
        - **TBD** means the data source has not confirmed that team, score or time yet.
        - Player assists, cards, lineups and substitutions appear only when the selected source provides them.
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
    source_mode = st.sidebar.radio("Data mode", ["Experimental: OpenFootball + ESPN + TheSportsDB + API-Football", "Live API", "OpenFootball", "Demo fallback"], help="Experimental enrichment combines Live API/OpenFootball with ESPN, TheSportsDB, and API-Football when configured; provider overlays prioritize live score, status, goals, assists, scorers, then statistics while preserving trusted player names.")
    if st.sidebar.button("Refresh now", help="Fetch fresh data with a Streamlit rerun."):
        st.cache_data.clear()
        st.rerun()

    if source_mode == "Experimental: OpenFootball + ESPN + TheSportsDB + API-Football":
        matches, teams, groups, stadiums, source = load_default_data(api_base, token)
    elif source_mode == "OpenFootball":
        matches, teams, groups, stadiums, source = load_openfootball_data()
        source = "✓ OpenFootball"
    elif source_mode == "Live API":
        matches, teams, groups, stadiums, source = load_live_data(api_base, token)
        source = "Live API" if source == "Live API" else source
    else:
        matches, teams, groups, stadiums, source = load_fallback()

    matches = enrich_matches(matches, stadiums)
    global TEAM_FLAG_MAP
    TEAM_FLAG_MAP = build_flag_map(teams)
    calc_table = calculate_standings_from_matches(matches, teams)
    standings = calc_table if not calc_table.empty else groups
    matches_df = matches
    teams_df = teams
    standings_df = standings
    knockout_df = matches_df[matches_df["stage"] != "group"].copy() if not matches_df.empty else pd.DataFrame()
    players_df, events_df, match_stats_df, probabilities_df = build_normalized_secondary_frames(matches_df, teams_df, standings_df)
    st.session_state["normalized_dataframes"] = {
        "matches_df": matches_df, "teams_df": teams_df, "standings_df": standings_df, "knockout_df": knockout_df,
        "players_df": players_df, "events_df": events_df,
        "match_stats_df": match_stats_df, "probabilities_df": probabilities_df,
    }
    html_payload = component_payload(matches_df, teams_df, standings_df)

    all_teams = sorted(set(matches["home_team"].dropna()) | set(matches["away_team"].dropna())) if not matches.empty else []
    if all_teams:
        favorite = st.sidebar.selectbox("Favorite team quick filter", ["None"] + all_teams)
        if favorite != "None":
            st.sidebar.write("Next/route")
            fdf = filter_matches(matches, team=favorite).sort_values("date_time", na_position="last")
            for _, row in fdf.head(3).iterrows():
                st.sidebar.caption(f"{row['kickoff']} — {row['home_team']} {row['score']} {row['away_team']}")


    # Global tournament banner: keep identity above the navigation tabs on every page.
    render_hero(matches_df, source)
    inject_live_clock_script()
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
    if requested_tab in tab_names and st.session_state.get("dashboard_section") not in tab_names:
        st.session_state["dashboard_section"] = requested_tab
    default_index = tab_names.index(st.session_state.get("dashboard_section", requested_tab if requested_tab in tab_names else "Overview"))
    st.markdown('<div class="wc-tab-nav">', unsafe_allow_html=True)
    active_tab = st.radio("Dashboard section selector", tab_names, index=default_index, horizontal=True, label_visibility="collapsed", key="dashboard_section")
    st.markdown('</div>', unsafe_allow_html=True)

    if active_tab == "Overview":
        render_overview(matches, standings, source)
    elif active_tab == "Upcoming & Live":
        render_interactive_component(html_payload, "matches", height=820)
    elif active_tab == "Knockout Bracket":
        render_interactive_component(html_payload, "knockout", height=820)
    elif active_tab == "Stats & Insights":
        render_insights_tab(matches)
    elif active_tab == "Groups & Standings":
        st.header("Groups & Standings")
        st.markdown("Top teams advance from each group; third-place teams can also qualify depending on the tournament format and table ranking.")
        render_interactive_component(html_payload, "standings", height=900)
    elif active_tab == "Teams":
        render_interactive_component(html_payload, "teams", height=900)
    elif active_tab == "Players":
        render_players_tab(matches)
    elif active_tab == "Football 101":
        render_fan_guide()


if __name__ == "__main__":
    main()
