# Streamlit Cloud Deployment Process

This is the deployment process we will follow for the new public repository.

## 1. Prepare the public repository

Before GitHub:

- create a clean deployment folder
- copy only approved code and safe data
- add a strict `.gitignore`
- remove all secrets and local databases
- verify no tracked file exceeds 100 MB

Why this matters:

- your GitHub repository is public
- Streamlit Cloud deploys directly from GitHub
- anything pushed to the repo should be treated as public by default

## 2. Make the app cloud-ready

We will update the app so that it:

- runs from a clean entrypoint
- loads secrets from Streamlit Cloud securely
- avoids local-only assumptions such as localhost and local SQLite persistence
- fails gracefully when optional backends are not configured

## 3. Push to GitHub

Recommended sequence:

1. Create a new GitHub repository for the public app.
2. Initialize Git in the clean deployment folder, or connect it to the new remote.
3. Commit only the reviewed files.
4. Push to the default branch.

Before pushing, we will verify:

- no secrets are present
- no file is oversized
- the repo contains only deployable content

## 4. Connect GitHub to Streamlit Cloud

In Streamlit Cloud:

1. Sign in with GitHub.
2. Choose "New app".
3. Select the public repository.
4. Select the branch.
5. Set the main file path, usually `app.py` or another chosen entrypoint.
6. Add secrets in the Streamlit app settings, not in GitHub.
7. Deploy.

## 5. Configure secrets

Secrets should be added in Streamlit Cloud's secrets manager.

Examples:

- `GOOGLE_API_KEY`
- `MONGODB_URI`
- feature flags if needed

These secrets are injected at runtime and must never be committed to Git.

## 6. Validate the deployment

After deployment, we will check:

- app startup logs
- missing package errors
- missing file errors
- secret loading behavior
- page rendering
- optional features hidden or disabled correctly

## 7. Ongoing update process

For future updates:

1. Make changes locally in the clean deployment workspace.
2. Review the diff.
3. Commit.
4. Push to GitHub.
5. Streamlit Cloud auto-redeploys from the connected branch.

## 8. Professional operating rules

- Never commit `.env` or credentials.
- Never commit local DB files.
- Never commit raw private operational datasets.
- Use sample or approved public data only.
- Keep optional cloud features behind configuration flags.
- Review every new dependency before adding it.
