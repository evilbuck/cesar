# Deploying with Kamal 2

## Prerequisites

1. **Install Kamal 2:**
   ```bash
   gem install kamal
   ```

2. **Setup your VPS:**
   - Ubuntu 22.04+ recommended
   - Docker pre-installed (Kamal will install if missing)
   - SSH access with your SSH key

3. **Docker Registry:**
   - Account on Docker Hub, DigitalOcean Registry, or GitHub Container Registry
   - Access token (not password) for pushing images

## Configuration

1. **Update `config/deploy.yml`:**
   - Replace `YOUR_VPS_IP_HERE` with your Hostinger VPS IP
   - Replace `transcribe.yourdomain.com` with your domain
   - Update `registry` section if not using DigitalOcean

2. **Setup environment:**
   ```bash
   export KAMAL_REGISTRY_PASSWORD=your_registry_token
   ```

## Deploy Commands

```bash
# Initial setup (first time only)
kamal setup

# Deploy updates
kamal deploy

# View logs
kamal logs

# Tail logs
kamal logs -f

# Access server shell
kamal shell

# Run Python interactive
kamal python

# Restart app
kamal restart

# Check status
kamal details
```

## SSL/TLS

Kamal automatically handles SSL certificates via Let's Encrypt. Make sure:
- Your domain DNS points to your VPS IP
- Port 80 and 443 are open in your firewall

## Troubleshooting

```bash
# Check container status
kamal app exec "ps aux"

# View container logs
kamal app logs

# Check health endpoint
kamal app exec "curl http://localhost:8000/health"
```
