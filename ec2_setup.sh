#!/bin/bash

# Detect OS and install dependencies
if command -v apt-get &> /dev/null; then
    echo "Detected Debian/Ubuntu..."
    sudo apt-get update -y
    sudo apt-get install -y docker.io git python3-dotenv
    
    # Start Docker
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # Add user to group
    sudo usermod -aG docker $USER

elif command -v yum &> /dev/null; then
    echo "Detected Amazon Linux/RHEL..."
    sudo yum update -y
    sudo yum install -y docker git
    
    # Start Docker (Amazon Linux 2/2023)
    sudo service docker start
    sudo systemctl enable docker
    
    # Add user to group
    sudo usermod -aG docker $USER
    sudo usermod -aG docker ec2-user
else
    echo "Unsupported OS. Please install Docker and Git manually."
    exit 1
fi

echo "Setup complete! Please logout and login again for group changes to take effect."
