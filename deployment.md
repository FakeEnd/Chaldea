# Deployment Guide

This guide explains how to deploy the ETF Scraper Discord Bot. The recommended approach is using a **PaaS provider (Railway/Render)** with Docker, as it handles the complex browser dependencies (Playwright) automatically.

## Prerequisites

1.  **Discord Bot Token**: You need a token from the [Discord Developer Portal](https://discord.com/developers/applications).
2.  **GitHub Account**: The project should be pushed to a GitHub repository.

---

## Option 1: PaaS Deployment (Recommended)

Services like **Railway**, **Render**, or **Fly.io** are easiest. They link to your GitHub and auto-deploy.

### Why Docker?
This bot uses **Playwright** to control a browser. Standard Python environments on these platforms often lack the necessary system libraries for browsers (Chromium). We use a `Dockerfile` to ensure everything is installed correctly.

### Steps (General)

1.  **Push to GitHub**: Ensure your project is in a GitHub repository.
2.  **Connect Provider**: Go to Railway/Render and create a new "Web Service" or "Background Worker" from your GitHub repo.
3.  **Environment Variables**:
    In the provider's dashboard, look for "Variables" or "Environment". Add:
    *   `DISCORD_TOKEN`: Your bot token (e.g., `MTI3ND...`)
4.  **Deploy**: The provider will detect the `Dockerfile` and build the image.

### Platform Specifics

#### Railway (Best for Persistence)
1.  **New Project** -> **Deploy from GitHub repo**.
2.  **Variables**: Add `DISCORD_TOKEN`.
3.  **Watch out**: By default, the database (`etf_data.db`) wraps reset on every deploy.
    *   *Fix*: Add a "Volume" in Railway settings and mount it to `/app/etf_data.db` if you want to keep history.

#### Render
1.  **New** -> **Web Service** (or Private Service).
2.  **Runtime**: Select "Docker".
3.  **Environment**: Add `DISCORD_TOKEN`.
4.  *Note*: Render's free tier spins down after inactivity. Since this is a bot, you might need a paid plan or a service like "UptimeRobot" to keep it awake, or use a "Background Worker" (paid).

---

## Option 2: Linux VPS (DigitalOcean, AWS, etc.)

If you have a Linux server (Ubuntu), you can run it manually.

### 1. Setup
```bash
# Update and install Python/Git
sudo apt update && sudo apt install python3-pip python3-venv git -y

# Clone your repo
git clone https://github.com/YOUR_USER/YOUR_REPO.git
cd fundingUpdate
```

### 2. Install Dependencies
```bash
# Create venv
python3 -m venv venv
source venv/bin/activate

# Install libs
pip install -r requirements.txt
playwright install chromium
playwright install-deps  # Installs system libraries for browsers
```

### 3. Configure
Create a `.env` file:
```bash
nano .env
```
Paste your token:
```
DISCORD_TOKEN=your_token_here
```

### 4. Run with PM2 (Process Manager)
PM2 keeps your bot running and restarts it if it crashes.

```bash
# Install Node/PM2 (if not installed)
sudo apt install nodejs npm -y
sudo npm install pm2 -g

# Start the bot
pm2 start start.sh --name "etf-bot"

# Save list so it correctly respawns on reboot
pm2 save
pm2 startup
```

---

## Troubleshooting

### "Playwright Host missing dependencies"
If not using Docker, you probably didn't run `playwright install-deps`.

### "Database wiped after deploy"
On PaaS (Render/Railway), the file system is ephemeral. Every deploy creates a fresh copy. To save history, you must use a **Volume** (Railway/Fly.io) or an external database (PostgreSQL).
