# Migration Inventory

This document tracks what should move from the original project into the new public deployment workspace.

## 1. Source app overview

Main Streamlit app:

- `app.py`

Primary view functions in the current app:

- `init_agent_system`
- `build_sidebar`
- `main`
- `render_overview`
- `render_regional`
- `render_generation`
- `render_intraday`
- `render_agent_chat`
- `render_weather_correlation`

Core utility modules:

- `utils/data_loader.py`
- `utils/charts.py`
- `utils/insights.py`
- `utils/kpi_cards.py`
- `utils/ai_insights.py`

Agent package:

- `scada_summary_agent/`

Current tests:

- `tests/test_scada_agent.py`

## 2. Safe to consider for migration

These are candidates to copy into the public workspace after review:

- `app.py`
- `utils/`
- `scada_summary_agent/`
- `sample_scada.csv`
- selected assets from `Images/`
- `.streamlit/config.toml`
- `README.md` content, after cleanup

## 3. Must not go into the public repo

Secrets and credentials:

- `.env`
- `id_ed25519_personal`
- `id_ed25519_personal.pub`
- `%USERPROFILE%/`

Local runtime state:

- `scada_session.db`
- `scada_streamlit_session.db`
- `debug_log.txt`
- `error.log`
- `test_out.txt`

Environment and generated artifacts:

- `.venv/`
- `__pycache__/`
- notebook outputs

Large or private data artifacts:

- `admin.All_India_IBM_Weather_96_RTM.json` about 1.2 GB
- `admin.MP_Scada_Demand_new.json`
- `mp_scada_data.electricity_readings_old_bkp.json`
- any private operational SCADA or weather dump

## 4. Deployment blockers found in the code

### 4.1 Local SQLite session persistence

The Streamlit app currently uses a local SQLite-backed session service. This is not a good public cloud deployment default and should be removed or redesigned for Streamlit Cloud.

### 4.2 Fixed session identity

The code uses fixed identifiers such as `streamlit_user` and `streamlit_demo_session`. In a public deployment, that risks cross-session mixing and poor isolation.

### 4.3 `.env`-centric secret loading

The current config assumes local `.env` loading. Public cloud deployment should use Streamlit secrets, with local env only as a development fallback.

### 4.4 MongoDB localhost fallbacks

The data layer defaults to `mongodb://localhost:27017`. That will not exist on Streamlit Cloud.

### 4.5 Incomplete dependency manifest

The current `requirements.txt` does not fully reflect runtime imports used by the app.

## 5. Recommended Phase 1 public deployment scope

Ship first:

- Overview
- Regional Analysis
- Generation Mix
- Intraday Profile

Feature-flag or temporarily disable:

- Agent Chat
- Weather Correlation if it depends on private MongoDB data

## 6. Questions to answer during migration

- Should weather correlation stay in Phase 1 if only sample local data is available?
- Should agent chat be hidden entirely or shown as "coming soon" in the public app?
- Do we want one sample dataset or a tiny curated sample pack?
