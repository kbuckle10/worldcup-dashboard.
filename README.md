# World Cup 2026 Dashboard & Explorer

A Streamlit web app for World Cup fans and non-football fans:

- Dashboard overview with live/next matches, progress, stage status, and headline metrics
- Matches tab with scores, fixtures, filters, and match cards
- Standings tab with group tables and simple explanations
- Knockout tab showing each knockout round and route to the final
- Teams tab for team-by-team route and quick stats
- Insights tab with goals-per-match, over 1.5, both-teams-scored, top attacks, and scoreline trends
- Football 101 tab explaining the tournament in plain English

## Data source

Default data mode: GitHub-hosted OpenFootball public-domain JSON.

Optional live API base: `https://worldcup26.ir`

When Live API mode is selected, the app uses these endpoints:

- `/get/games`
- `/get/groups`
- `/get/teams`
- `/get/stadiums`

A demo fallback snapshot is included so the app still opens if the GitHub feed or live API is unavailable.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy free on Streamlit Community Cloud

1. Create a GitHub repository, for example `worldcup-dashboard`.
2. Upload all files in this folder.
3. Go to Streamlit Community Cloud: https://share.streamlit.io
4. Sign in with GitHub.
5. Choose your repo, branch, and `app.py`.
6. Click **Deploy**.

## Optional Streamlit secrets

Only needed if your API instance requires authorization.

```toml
WORLDCUP26_BASE_URL = "https://worldcup26.ir"
WORLDCUP26_TOKEN = ""
```

On Streamlit Cloud, add these under **App settings → Secrets**.

## Notes

- Cache TTL is 60 seconds for API calls.
- Free hosting is suitable for public/light-to-moderate traffic. For heavy traffic or guaranteed uptime, move to a paid host or self-host behind a cache.
- The app is intentionally lightweight so it stays within free-host resource limits.
