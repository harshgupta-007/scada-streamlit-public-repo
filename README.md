# SCADA Demand Dashboard

A public, Streamlit-based dashboard for exploring SCADA demand patterns using a safe sample dataset.

This repository is being prepared for deployment on Streamlit Cloud with a security-first, public-repo-friendly setup.

## Phase 1 Scope

This first public release includes:

- Overview dashboard
- Regional analysis
- Generation mix analysis
- Intraday profile analysis
- Weather correlation with public sample weather data
- Agent chat using public sample data
- sample-data-only operation

Deferred for a later secure phase:

- external database integrations
- advanced observability outside agent workflows

## Why this repo is structured this way

This project is being prepared for a public GitHub repository, so the deployment version must:

- contain no secrets or credentials
- avoid private or oversized datasets
- stay comfortably below GitHub's 100 MB file limit
- run cleanly on Streamlit Cloud

## Project structure

- `app.py`: Streamlit app entrypoint
- `utils/`: charting, data loading, KPI, and insight helpers
- `data/`: approved public sample dataset
- `evals/`: standard Agent Chat evaluation prompts
- `assets/`: approved static assets used by the UI
- `.streamlit/`: Streamlit configuration
- `docs/`: migration, deployment, and review notes

## Local run

Create a virtual environment, install dependencies, and run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit secrets

For deployment, keep all secrets in Streamlit Cloud and never commit them to Git.

Current optional secrets:

- `GOOGLE_API_KEY`: enables Agent Chat
- `LANGSMITH_API_KEY`: enables LangSmith tracing for Agent Chat
- `LANGSMITH_PROJECT`: optional LangSmith project name
- `LANGSMITH_TRACING`: optional, defaults to `true`
- `LANGSMITH_ENDPOINT`: optional custom LangSmith endpoint

Phase 1 observability traces only the Agent Chat workflow so dashboard browsing remains lightweight.
Phase 2 adds lightweight user feedback on the latest Agent Chat response, which is submitted back to LangSmith for trace review.

## Deployment approach

The deployment flow for this project is:

1. Review all files in this clean public workspace.
2. Push only this reviewed workspace to a new public GitHub repository.
3. Connect that repository to Streamlit Cloud.
4. Configure any future secrets only in Streamlit Cloud settings.
5. Deploy and validate the app.

Detailed deployment notes are available in:

- `docs/STREAMLIT_CLOUD_DEPLOYMENT.md`
- `docs/DEPLOYMENT_WALKTHROUGH.md`
- `docs/REVIEW_CHECKLIST.md`
- `docs/LANGSMITH_EVALUATION_WORKFLOW.md`

## Security rules for this repo

- Never commit `.env` or secrets.
- Never commit private keys.
- Never commit local DB files.
- Never commit raw private operational datasets.
- Keep optional backend features disabled until they are ready for secure cloud deployment.

## Current dataset

The current app uses:

- `data/sample_scada.csv`
- `data/mp_weather_96_blocks_nov_2025.csv`

This is intentional for the first public deployment and keeps the app portable and safe for GitHub + Streamlit Cloud.
