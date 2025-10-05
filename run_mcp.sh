#!/bin/bash

# Chat PDF MCP Server Startup Script

echo "Starting Chat PDF MCP Server..."

# Activate virtual environment
source venv/bin/activate

# Run the MCP server
python mcp_server/server.py
