# Deploy VadeX on a DigitalOcean GPU Droplet

The deployment runs the FastAPI app and Ollama on one Ubuntu GPU Droplet. Invoice
uploads, SQLite state, model weights and Gemma requests remain on that Droplet; invoice
data is not sent to a cloud AI provider. Ollama listens only on loopback and is not
published to the internet.

## 1. Create and prepare the Droplet

Create an Ubuntu 24.04 GPU Droplet with enough GPU memory for `gemma4`, then use an SSH
key to connect. Install Docker Engine and the Compose plugin using Docker's Ubuntu
installation guide:

<https://docs.docker.com/engine/install/ubuntu/>

For NVIDIA acceleration, install the host GPU driver and NVIDIA Container Toolkit using
the vendor instructions:

<https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html>

Configure Docker for the NVIDIA runtime and verify the host can see the GPU:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
nvidia-smi
docker run --rm --gpus all ubuntu nvidia-smi
```

The Compose file defaults to CPU inference. To enable the GPU, uncomment the NVIDIA
device reservation under the `ollama` service in `docker-compose.yml`, then confirm the
container test above works.

## 2. Configure and start the services

Clone the repository, create a strong session secret, and prepare persistent paths owned
by the non-root container user (UID 10001):

```bash
git clone https://github.com/omresenn-netizen/hf26-elazig.git
cd hf26-elazig
cat > .env <<EOF
VADEX_SECRET=$(openssl rand -hex 32)
VADEX_COOKIE_SECURE=true
EOF
touch vadesiz.db
mkdir -p uploads
sudo chown 10001:10001 vadesiz.db uploads
```

`.env` and `vadesiz.db` are excluded from Git; keep `.env` private. Uploaded files persist
in the repository's `uploads/` directory, so do not stage or publish that directory.
The Compose build excludes local uploads. The setup uses Linux host networking so the
app can reach the loopback-only Ollama service at `localhost:11434`, matching the URL
currently hard-coded in `gemma.py`. Docker Desktop's host-network behavior differs; this
deployment is intended for Linux.

Build and start the services, download the model into Ollama's persistent volume, then
restart the API:

```bash
docker compose up -d --build
docker compose exec ollama ollama pull gemma4
docker compose restart vadex
docker compose ps
```

The app listens on `127.0.0.1:8600`; its health check expects `/api/me` to return `401`
for an unauthenticated request. Check Ollama's model placement after a Gemma call with:

```bash
docker compose exec ollama ollama ps
docker compose exec vadex python scripts/hardware_check.py
```

The hardware report includes CPU/RAM, an NVIDIA GPU if visible in the app container,
Ollama version and a measured warm-call latency. Since the Ollama CLI and GPU are in
their own container, use `docker compose exec ollama ollama ps` for authoritative GPU
placement.

## 3. Put HTTPS in front of the app

Keep ports `8600` and `11434` closed to the public internet. Configure a TLS reverse proxy
such as Nginx or Caddy on the Droplet to forward HTTPS requests to
`http://127.0.0.1:8600`, and allow only SSH plus the proxy's HTTP/HTTPS ports in the
Droplet and host firewalls. The compose configuration enables secure session cookies by
default; set `VADEX_COOKIE_SECURE=false` only for local, plain-HTTP testing.

## Configuration and limitations

| Variable | Purpose |
| --- | --- |
| `VADEX_SECRET` | Required random secret for signing login-session cookies. Generate a new value per deployment and keep it out of source control. |
| `VADEX_COOKIE_SECURE` | Defaults to `true` in Compose; use `true` behind HTTPS and `false` only for local HTTP testing. |
| `OLLAMA_URL` | Compose sets `http://localhost:11434/api/chat`, but `gemma.py` currently hard-codes that same URL and does not read the environment variable. Wiring it as an override is a follow-up application change. |

The app currently uses a SQLite file and a single Ollama instance, which suits a
single-droplet demo rather than a horizontally scaled production service. Back up
`vadesiz.db`, `uploads/`, and the Compose volumes securely; do not commit or publish
invoice data, model logs, or secrets.

## Updates

```bash
git pull
docker compose build
docker compose up -d
```

The named Ollama model and Gemma log volumes persist when containers are rebuilt. Do not
use `docker compose down -v` unless you intend to delete those volumes.
