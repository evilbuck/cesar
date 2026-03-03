#!/bin/bash
set -e

echo "Cesar VPS Deployment Script"
echo "============================"

# Configuration
APP_DIR="/var/www/cesar"
DOMAIN="${1:-}"

if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <your-domain.com>"
    echo "Example: $0 transcribe.example.com"
    exit 1
fi

echo ""
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-full ffmpeg nginx curl

echo ""
echo "Setting up application directory..."
sudo mkdir -p "$APP_DIR"
sudo chown -R $USER:$USER "$APP_DIR"

# Copy files
echo "Copying application files..."
cp -r cesar pyproject.toml requirements.txt "$APP_DIR/"

echo ""
echo "Creating Python virtual environment..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .

echo ""
echo "Pre-downloading Whisper models..."
python3 << 'EOF'
from faster_whisper import WhisperModel
import sys
models = ['tiny', 'base']
for model in models:
    print(f"Downloading {model} model...")
    try:
        WhisperModel(model, device='cpu')
        print(f"  ✓ {model} downloaded")
    except Exception as e:
        print(f"  ✗ {model} failed: {e}", file=sys.stderr)
EOF

echo ""
echo "Setting up data directory..."
mkdir -p "$APP_DIR/data"

# Setup systemd service
echo ""
echo "Configuring systemd service..."
sudo cp deployment/cesar.service /etc/systemd/system/
sudo sed -i "s|User=www-data|User=$USER|g" /etc/systemd/system/cesar.service
sudo sed -i "s|Group=www-data|Group=$USER|g" /etc/systemd/system/cesar.service
sudo systemctl daemon-reload
sudo systemctl enable cesar

# Setup nginx
echo ""
echo "Configuring Nginx..."
sudo cp deployment/nginx.conf /etc/nginx/sites-available/cesar
sudo sed -i "s/server_name _;/server_name $DOMAIN;/g" /etc/nginx/sites-available/cesar
sudo ln -sf /etc/nginx/sites-available/cesar /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "Starting Cesar service..."
sudo systemctl start cesar

echo ""
echo "======================================"
echo "Deployment complete!"
echo ""
echo "Your app should be available at:"
echo "  http://$DOMAIN"
echo ""
echo "API documentation:"
echo "  http://$DOMAIN/docs"
echo ""
echo "Health check:"
echo "  curl http://$DOMAIN/health"
echo ""
echo "To check service status:"
echo "  sudo systemctl status cesar"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u cesar -f"
echo ""
echo "======================================"
