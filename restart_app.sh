#!/bin/bash
cd ~/new_reader

# Stop existing process
if [ -f app.pid ]; then
    PID=$(cat app.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Stopping existing application (PID: $PID)..."
        kill $PID
        sleep 3
    fi
    rm -f app.pid
fi

# Kill any remaining process on port 10000
sudo pkill -f "uvicorn.*10000" || true
sleep 2

# Activate virtual environment
source venv/bin/activate

# Export environment variables
export $(cat .env | xargs)

echo "Starting application in background..."
nohup venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 10000 > app.log 2>&1 &

# Get the PID
APP_PID=$!
echo $APP_PID > app.pid

echo "Application started with PID: $APP_PID"
echo "Logs: tail -f app.log"
echo "Stop: kill \$(cat app.pid)"
