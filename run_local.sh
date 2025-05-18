#!/bin/bash
# Kill any process using port 5001
PID=$(lsof -ti tcp:5001)
if [ ! -z "$PID" ]; then
  echo "Killing process on port 5001 (PID: $PID)"
  kill -9 $PID
fi

# Stop and remove any docker container using port 5001
CONTAINER=$(docker ps -q --filter "publish=5001")
if [ ! -z "$CONTAINER" ]; then
  echo "Stopping and removing Docker container using port 5001"
  docker stop $CONTAINER
  docker rm $CONTAINER
fi

# Start the container
docker-compose up --build 