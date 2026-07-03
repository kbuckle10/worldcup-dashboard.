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

st.set_page_config(
    page_title="World Cup 2026 Dashboard",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .main-title {font-size: 2.4rem; font-weight: 800; margin-bottom: 0.2rem;}
      .subtle {color: #667085; font-size: 0.95rem;}
      .metric-card {border: 1px solid #e5e7eb; border-radius: 16px; padding: 16px; background: #fff; box-shadow: 0 1px 2px rgba(16,24,40,.04);}
      .match-card {border: 1px solid #e5e7eb; border-radius: 14px; padding: 14px; margin-bottom: 10px; background: #ffffff;}
      .tag {display:inline-block; padding: 2px 8px; border-radius: 999px; background:#eef2ff; color:#3730a3; font-size:.78rem; font-weight:600; margin-right:4px;}
      .live {background:#fee2e2; color:#991b1b;}
      .finished {background:#dcfce7; color:#166534;}
      .scheduled {background:#f3f4f6; color:#374151;}
      .explain {background:#f8fafc; border-left: 4px solid #94a3b8; padding: 12px 14px; border-radius: 8px;}
      div[data-testid="stMetricValue"] {font-size: 1.65rem;}
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
    elapsed = clean_text(row.get("elapsed"))
    elapsed_html = f"<span class='tag'>{elapsed}</span>" if elapsed and row.get("status") == "Live" else ""
    venue = clean_text(row.get("venue"))
    winner = clean_text(row.get("winner"))
    winner_line = f"<div class='subtle'>Winner: <b>{winner}</b></div>" if winner and winner != "Draw / penalties" else ""
    st.markdown(
        f"""
        <div class="match-card">
          <div>{status}{elapsed_html}<span class="tag">{row.get('stage_label','')}</span></div>
          <h4 style="margin:8px 0 2px 0;">{row.get('home_team','TBD')} <b>{score}</b> {row.get('away_team','TBD')}</h4>
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


def render_dashboard(matches_df: pd.DataFrame, standings_df: pd.DataFrame, source: str) -> None:
    st.markdown('<div class="main-title">⚽ World Cup 2026 Dashboard & Explorer</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtle">Built for serious football fans, but simple enough for anyone to understand what is happening.</div>', unsafe_allow_html=True)
    st.caption(f"Data source: {source} • Auto-refresh cache: 60 seconds for live API data")

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

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Matches loaded", total_matches)
    c2.metric("Finished", len(finished))
    c3.metric("Live now", len(live))
    c4.metric("Goals", total_goals, f"{avg_goals:.2f} per match")
    c5.metric("Top attack", top_team, top_value)

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
            render_match_card(row)
    with col_b:
        st.write("#### Stage status")
        stage_counts = matches_df.groupby(["stage_label", "status"]).size().reset_index(name="matches")
        fig = px.bar(stage_counts, x="stage_label", y="matches", color="status", title="Matches by stage/status")
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
