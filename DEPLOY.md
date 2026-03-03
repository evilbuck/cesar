# Cesar VPS Deployment Guide

Deploy Cesar Transcription Service on a VPS (Hostinger, DigitalOcean, etc.)

**Recommended: Use Kamal 2 for deployment** - see [KAMAL.md](KAMAL.md)

## Quick Deploy (with Kamal)

```bash
# 1. Install Kamal
gem install kamal

# 2. Set registry password
export KAMAL_REGISTRY_PASSWORD=your_token

# 3. Update config/deploy.yml with your VPS IP and domain

# 4. Deploy
kamal setup
kamal deploy
```

**Full Kamal docs:** [KAMAL.md](KAMAL.md)

---

## Alternative: Manual Deploy

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8 GB |
| Storage | 20 GB | 50 GB (for models) |
| GPU | None (CPU works!) | Optional CUDA GPU |

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/evilbuck/transcribely.git
cd transcribely
pip install -e .

# 2. Install FFmpeg
sudo apt update && sudo apt install -y ffmpeg

# 3. Download models (while online)
python -c "from faster_whisper import WhisperModel; WhisperModel('base')"

# 4. Start server
./start-server.sh
```

## Docker Deployment (Recommended)

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f
```

## Production Deployment

### 1. Install Dependencies

```bash
# System packages
sudo apt update
sudo apt install -y python3-pip python3-venv ffmpeg nginx

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### 2. Download Whisper Models

Models are cached in `~/.cache/huggingface/hub/`:

```bash
# Pre-download common models
python3 << 'EOF'
from faster_whisper import WhisperModel
for model in ['tiny', 'base', 'small']:
    print(f"Downloading {model}...")
    WhisperModel(model, device='cpu')
EOF
```

### 3. Configure Nginx

```bash
sudo cp deployment/nginx.conf /etc/nginx/sites-available/cesar
sudo ln -sf /etc/nginx/sites-available/cesar /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 4. Setup Systemd Service

```bash
sudo cp deployment/cesar.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cesar
sudo systemctl start cesar
```

### 5. Verify Deployment

```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs  # API documentation
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CESAR_PORT` | 8000 | API server port |
| `CESAR_HOST` | 0.0.0.0 | Bind address |
| `CESAR_WORKERS` | 1 | Number of uvicorn workers |
| `CESAR_DB_PATH` | ~/.local/share/cesar/jobs.db | Job database location |
| `WEB_DIR` | ./cesar/web | Static frontend directory |

## CPU Performance Expectations

| Model | CPU Speed | Real-time Factor |
|-------|-----------|------------------|
| tiny | ~0.3x | 3 min audio → 10 min processing |
| base | ~0.5x | 3 min audio → 6 min processing |
| small | ~0.2x | 3 min audio → 15 min processing |
| medium | ~0.1x | 3 min audio → 30 min processing |

**Recommendation:** Use `base` model for best speed/accuracy balance on CPU.

## Troubleshooting

### FFmpeg not found
```bash
which ffmpeg  # Should return path
sudo apt install ffmpeg
```

### Out of memory
- Use smaller model (tiny/base)
- Add swap space
- Upgrade VPS RAM

### Slow transcription
- Normal on CPU - consider upgrading to GPU instance
- Use `base` or `tiny` model
- Enable parallel processing (automatic for files >30 min)

## SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```
