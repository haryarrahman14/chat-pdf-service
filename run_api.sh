#!/bin/bash

# Chat PDF API Server Startup Script

echo "Starting Chat PDF API Server..."

# Activate virtual environment
source venv/bin/activate

# Run the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
