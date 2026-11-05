# ExportSight — Deployment Guide (Streamlit)

## Option A — Streamlit Community Cloud (recommended, free)

1. Push this folder to a GitHub repository.
2. Go to https://share.streamlit.io → **New app** → select the repo,
   branch and `app.py` as the main file.
3. It installs `requirements.txt` automatically. No secrets are required
   (the app uses a local SQLite file; no credentials exist).
4. First launch creates `exportsight.db` and loads the fictional demo
   dataset — clear or replace it in **Settings → Data management**.

> Note: Community Cloud uses an ephemeral filesystem. The SQLite file
> resets on redeploys/app sleep. For persistent data, either re-import
> your CSVs after a restart or attach external storage (see Option C).

## Option B — Any VPS / server

```bash
# 1. system packages
sudo apt update && sudo apt install -y python3 python3-pip

# 2. app
git clone <your-repo> && cd exportsight
pip install -r requirements.txt
python -m db.init_db --seed   # or without --seed for an empty database

# 3. run behind a process manager (example: systemd)
# /etc/systemd/system/exportsight.service
#   ExecStart=/usr/bin/python3 -m streamlit run app.py \
#     --server.port 8501 --server.address 0.0.0.0 --server.headless true
sudo systemctl enable --now exportsight
```

Put nginx/Caddy in front for HTTPS and map your domain to port 8501.

## Option C — Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m db.init_db --seed
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.headless=true", \
     "--server.address=0.0.0.0", "--server.port=8501"]
```

```bash
docker build -t exportsight .
docker run -p 8501:8501 -v exportsight-data:/app/exportsight.db exportsight
```

The named volume keeps `exportsight.db` persistent across restarts.

## Configuration

- Port/address: `--server.port`, `--server.address` flags.
- Theme: `.streamlit/config.toml` (navy / white / teal).
- No environment variables or secrets are needed.

## Health check

After deploy, open `/healthz` on the Streamlit server (returns `ok`)
and confirm the sidebar shows all six sections.
