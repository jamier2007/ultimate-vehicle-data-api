#!/bin/bash

# Exit on error
set -e

# Update system and install dependencies
echo "Updating system and installing dependencies..."
apt-get update
apt-get install -y docker.io docker-compose git

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
apt-get install -y nginx

# Create Nginx configuration
cat > /etc/nginx/sites-available/vehicle-api << 'EOL'
server {
    listen 80;
    server_name 176.32.225.93;

    location / {
        proxy_pass http://localhost:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
EOL

# Enable the site
ln -sf /etc/nginx/sites-available/vehicle-api /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t

# Restart Nginx
systemctl restart nginx

echo "Deployment complete! The service should be accessible at http://176.32.225.93" 