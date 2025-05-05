#!/bin/bash

echo "Stopping and removing existing container if it exists..."
docker stop vehicle-api 2>/dev/null || true
docker rm vehicle-api 2>/dev/null || true

echo "Building new image..."
docker build -t vehicle-service .

echo "Starting new container..."
docker run -d -p 5001:5001 --name vehicle-api vehicle-service

echo "Container started! Web interface available at: http://localhost:5001"
echo "API documentation available at: http://localhost:5001/docs" 