# Review Checklist

Use this checklist before the first GitHub push.

## Repository safety

- No `.env` file
- No SSH keys
- No DB files
- No logs
- No notebooks that expose private data
- No private datasets
- No file above 100 MB

## App readiness

- Entry file is correct
- `requirements.txt` is complete
- App runs locally
- Optional features fail gracefully
- Streamlit theme/config is correct

## Streamlit Cloud readiness

- Secrets are read from Streamlit config
- No localhost-only dependencies in the default path
- No hardcoded user/session IDs shared across all users
- No writes required to unsafe local paths

## Deployment readiness

- Public README is clean and accurate
- Deployment instructions are documented
- Sample data is approved for public use
- Final Git diff has been reviewed
