# ANNA: session-only AWS preparation

This package intentionally excludes all conversation databases, database schema, instructor exports, and feedback collection. Conversations and approximate usage accounting are held in Streamlit session state, not saved to disk. A student can download a Markdown transcript during the session. Streamlit session state may be lost on browser reload/reconnection, app restart, or session expiration.

## Local test

Create a virtual environment, run `pip install -r requirements.txt`, then set `OPENAI_API_KEY` and `BETA_TESTER_CODES` in environment variables and run `streamlit run app.py`. The original `~/.config/topology-peer/.env` loading remains for local development; do not copy that file to AWS.

## Before exposing to students

- Replace tester-code access with FSU-approved SSO; beta codes are not robust production authentication.
- Configure HTTPS, security groups, and FSU-approved VPC/networking.
- Put API secrets in an approved secrets service, not source files.
- Configure provider-side API spending caps and AWS billing alerts: session-only cost counters are NOT global limits and can be reset.
- Confirm logging/retention behavior of EC2, Streamlit, reverse proxy, AWS services and OpenAI. `store=False` does not imply zero retention.
- Check approved model name, availability and rates; defaults in this archived project may be stale.
- Do not deploy the original ZIP: it contains a real SQLite conversation database.
