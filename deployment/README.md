# ANNA EC2 preparation (Amazon Linux 2023)

These files are **preparation only**. Do not launch EC2 or open public ports until FSU confirms the VPC, network, authentication, and approved secrets approach.

## Add to the aws-deployment branch now

Copy `anna.service`, `anna.env.example`, and this README into a new `deployment/` folder in your GitHub repository. Commit and push via GitHub Desktop. The example contains placeholders, not working credentials. Never commit real keys or tester codes.

## Intended server layout

- `/opt/anna/`: checkout of the `aws-deployment` branch, including `app.py`, `session_storage.py`, `requirements.txt`, and `course/`.
- `/opt/anna/.venv/`: Python virtual environment with `pip install -r requirements.txt`.
- `/etc/anna/anna.env`: environment settings readable only by root and the service as needed. Prefer FSU-approved secret delivery instead of a persistent environment file if required.
- `/etc/systemd/system/anna.service`: copy of `deployment/anna.service`.

The service runs as a dedicated unprivileged Linux user `anna` and binds Streamlit to `127.0.0.1:8501`. It **will not be reachable from students' browsers** until FSU-approved HTTPS reverse proxy/load balancer and SSO are configured. Do not open TCP 8501 publicly. Do not open SSH to the world.

## When the network is approved

We will create the service user and directories, clone the repository, install Python dependencies, configure approved secrets, install the service, then run `sudo systemctl enable --now anna` and inspect `sudo systemctl status anna`. GitHub authentication for a private repository must be configured securely; avoid putting personal access tokens into shell commands or repository files.

## Updating the app later

After committing/pushing on GitHub, connect to the server, update the checkout of `aws-deployment`, install any changed requirements, and restart the service. A restart clears in-memory student conversations, so schedule updates outside class usage.

## Remaining checks

- Verify model name, pricing, provider spending limits, and API permissions.
- Confirm that no transcripts are written to disk; operational logs can still contain metadata/errors.
- Configure FSU SSO before real student use; beta codes are only for testing.
- Configure HTTPS and the FSU-approved VPC/security group architecture.
- This service file does not itself create authentication, TLS, DNS, or a deployment pipeline.
