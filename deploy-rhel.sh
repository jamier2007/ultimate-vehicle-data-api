#!/bin/bash

# Exit on error
set -e

# Update system and install dependencies
echo "Updating system and installing dependencies..."
dnf update -y
dnf install -y docker docker-compose git nginx

# Start and enable Docker
echo "Starting Docker service..."
systemctl start docker
systemctl enable docker

# Create app directory
echo "Creating application directory..."
mkdir -p /opt/vehicle-api
cd /opt/vehicle-api

# Clone repository (if not already present)
if [ ! -d ".git" ]; then
    echo "Cloning repository..."
    git clone https://github.com/jamier2007/ultimate-vehicle-data-api.git .
fi

# Build and start the container
echo "Building and starting the container..."
docker-compose up -d --build

# Set up Nginx as reverse proxy
echo "Setting up Nginx..."

# Create Nginx configuration
cat > /etc/nginx/conf.d/vehicle-api.conf << 'EOL'
server {
    listen 80;
    server_name 176.32.225.93;

    location / {
        proxy_pass http://localhost:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
EOL

# Test Nginx configuration
nginx -t

# Start and enable Nginx
systemctl start nginx
systemctl enable nginx

# Configure firewall
echo "Configuring firewall..."
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --reload

echo "Deployment complete! The service should be accessible at http://176.32.225.93" 