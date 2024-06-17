#!/bin/bash

# Start Redis server in the background
redis-server --daemonize yes

# Wait until Redis server is available
until redis-cli ping | grep -q PONG; do
  echo "Waiting for Redis to start..."
  sleep 1
done

# Start RQ worker with scheduler in the background
rq worker --with-scheduler &

# Start the main application
python main.py
