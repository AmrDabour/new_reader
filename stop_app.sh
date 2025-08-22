#!/bin/bash
cd ~/new_reader

if [ -f app.pid ]; then
    PID=$(cat app.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Stopping application (PID: $PID)..."
        kill $PID
        sleep 2
        if ps -p $PID > /dev/null 2>&1; then
            echo "Force killing application..."
            kill -9 $PID
        fi
        echo "Application stopped."
    else
        echo "Application is not running."
    fi
    rm -f app.pid
else
    echo "No PID file found. Checking for any uvicorn processes..."
    sudo pkill -f "uvicorn.*10000" || echo "No uvicorn processes found."
fi
