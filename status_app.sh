#!/bin/bash
cd ~/new_reader

echo "=== Application Status ==="

if [ -f app.pid ]; then
    PID=$(cat app.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Application is running (PID: $PID)"
        echo "📊 Process info:"
        ps -p $PID -o pid,ppid,cmd,start
    else
        echo "❌ Application is not running (stale PID file)"
    fi
else
    echo "❌ No PID file found"
fi

echo ""
echo "📡 Port 10000 status:"
ss -tuln | grep :10000 || echo "Port 10000 not in use"

echo ""
echo "📝 Recent logs (last 10 lines):"
if [ -f app.log ]; then
    tail -10 app.log
else
    echo "No log file found"
fi
