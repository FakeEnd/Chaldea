# Deploying to AWS EC2 (Free Tier)

This guide shows you how to run your Discord bot on an AWS EC2 instance using the Free Tier (750 hours/month).

## 1. Launch instance on AWS Console
1.  Log in to your **AWS Console**.
2.  Go to **EC2** -> **Instances** -> **Launch Instances**.
3.  **Name**: `DiscordBot-Server`.
4.  **OS Images (AMI)**: Choose **Ubuntu** (Ubuntu Server 24.04 LTS or 22.04 LTS).
5.  **Instance Type**: Choose `t2.micro` or `t3.micro` (Look for the "Free tier eligible" tag).
6.  **Key pair (Login)**:
    *   Click "Create new key pair".
    *   Name: `myserver-key`.
    *   Type: `RSA`.
    *   Format: `.pem`.
    *   **Download** the file and keep it safe!
7.  **Network settings**:
    *   Ensure "Allow SSH traffic from Anywhere" (0.0.0.0/0) is checked.
8.  Click **Launch instance**.

## 2. Connect to your Server
1.  Go to the customized **Instance summary** page.
2.  Select your new instance and click **Connect**.
3.  **Easiest way**: Use the **EC2 Instance Connect** tab and click "Connect" to open a terminal in your browser.

## 3. Setup (Install Docker & Git)
Once inside the terminal, run these commands to prepare the server.

```bash
# Update and install Docker & Git
sudo apt-get update
sudo apt-get install -y docker.io git python3-dotenv

# Start Docker
sudo systemctl start docker
sudo systemctl enable docker

# Allow your user to run Docker commands
sudo usermod -aG docker $USER
```

*Note: You might need to close and reopen the terminal for the permission change to take effect.*

## 4. Deploy the Bot
Now we clone your code and run it using Docker.

1.  **Clone your repo**:
    ```bash
    git clone https://github.com/YOUR_GITHUB_USER/YOUR_REPO_NAME.git
    cd YOUR_REPO_NAME
    ```

2.  **Add your Secrets**:
    Create the `.env` file on the server.
    ```bash
    nano .env
    ```
    Paste your token inside:
    ```
    DISCORD_TOKEN=your_actual_token_here
    ```
    (Press `Ctrl+X`, then `Y`, then `Enter` to save).

3.  **Build and Run**:
    ```bash
    # Build the Docker image (this takes a few minutes)
    docker build -t my-discord-bot .

    # Run the bot in the background
    # --restart unless-stopped means it will auto-restart if the server reboots!
    docker run -d --restart unless-stopped --env-file .env -v $(pwd)/etf_data.db:/app/etf_data.db my-discord-bot
    ```

## 5. Maintenance
*   **Check logs**: `docker logs $(docker ps -q)`
*   **Update code**:
    ```bash
    git pull
    docker build -t my-discord-bot .
    docker stop $(docker ps -q)
    docker run -d --restart unless-stopped --env-file .env -v $(pwd)/etf_data.db:/app/etf_data.db my-discord-bot
    ```
