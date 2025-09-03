#!/bin/bash

# Cleanup script for local testing environment

echo "🧹 Cleaning up local testing environment..."

# Kill function app if running
if [ -f "func.pid" ]; then
    PID=$(cat func.pid)
    if kill -0 $PID 2>/dev/null; then
        echo "Stopping function app (PID: $PID)..."
        kill $PID
        sleep 2
        # Force kill if still running
        if kill -0 $PID 2>/dev/null; then
            kill -9 $PID
        fi
        echo "✅ Function app stopped"
    else
        echo "Function app not running"
    fi
    rm func.pid
fi

# Kill any remaining func processes
pkill -f "func start" || true

# Clean up log files
if [ -f "func.log" ]; then
    rm func.log
    echo "✅ Removed log file"
fi

echo "✅ Cleanup complete!"
