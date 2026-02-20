#!/bin/bash

# Update package list
echo "Updating apt..."
sudo apt-get update -y

# Install Docker and Git
echo "Installing Docker and Git..."
sudo apt-get install -y docker.io git

# Start and enable Docker service
echo "Starting Docker..."
sudo systemctl start docker
sudo systemctl enable docker

# Add current user to docker group (avoids sudo for docker commands)
sudo usermod -aG docker ubuntu

echo "Setup complete! Please logout and login again for group changes to take effect."
