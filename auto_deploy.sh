#!/bin/bash

# ========================================
# New Reader Auto-Deployment Script
# Handles virtual environment and deployment
# ========================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Function to get API key
get_api_key() {
    if [ -z "$GOOGLE_AI_API_KEY" ]; then
        echo ""
        print_warning "Google AI API Key is required!"
        echo "Please visit: https://aistudio.google.com/app/apikey"
        echo "Create an API key and paste it here."
        echo ""
        read -p "Enter your Google AI API Key: " GOOGLE_AI_API_KEY

        if [ -z "$GOOGLE_AI_API_KEY" ]; then
            print_error "API key is required. Exiting."
            exit 1
        fi
    fi
}

# Function to install system dependencies
install_system_deps() {
    print_header "Installing System Dependencies"

    # Update package manager
    print_status "Updating package manager..."
    sudo apt update -y

    # Install essential tools
    print_status "Installing essential tools..."
    sudo apt install -y git curl wget build-essential

    # Install Python development tools
    print_status "Installing Python development tools..."
    sudo apt install -y python3-full python3-venv python3-pip python3-dev

    # Install Tesseract OCR
    print_status "Installing Tesseract OCR..."
    sudo apt install -y tesseract-ocr tesseract-ocr-eng

    # Install OpenGL libraries for OpenCV
    print_status "Installing OpenGL libraries..."
    sudo apt install -y libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1

    # Install additional dependencies for OpenCV
    print_status "Installing additional OpenCV dependencies..."
    sudo apt install -y libgstreamer1.0-0 libgstreamer-plugins-base1.0-0

    print_status "System dependencies installed successfully!"
}

# Function to setup repository
setup_repository() {
    print_header "Setting Up Repository"

    if [ -d "new_reader" ]; then
        print_warning "Repository already exists. Updating..."
        cd new_reader
        git pull origin main || git pull origin master
    else
        print_status "Cloning repository..."
        git clone https://github.com/AmrDabour/new_reader.git
        cd new_reader
    fi

    print_status "Repository setup complete!"
}

# Function to setup virtual environment
setup_virtual_env() {
    print_header "Setting Up Virtual Environment"

    # Remove existing virtual environment if it exists
    if [ -d "venv" ]; then
        print_warning "Removing existing virtual environment..."
        rm -rf venv
    fi

    # Create new virtual environment
    print_status "Creating virtual environment..."
    python3 -m venv venv

    # Activate virtual environment
    print_status "Activating virtual environment..."
    source venv/bin/activate

    # Upgrade pip
    print_status "Upgrading pip..."
    venv/bin/pip install --upgrade pip

    # Install requirements
    print_status "Installing Python requirements (this may take a few minutes)..."
    venv/bin/pip install --no-cache-dir -r requirements.txt

    print_status "Virtual environment setup complete!"
}

# Function to setup environment
setup_environment() {
    print_header "Setting Up Environment"

    # Get API key from user
    get_api_key

    # Create environment file
    print_status "Creating environment file..."
    cat > .env << EOF
GOOGLE_AI_API_KEY=$GOOGLE_AI_API_KEY
TESSERACT_CMD=/usr/bin/tesseract
PORT=10000
GEMINI_MODEL=gemini-2.5-flash
MAX_FILE_SIZE_MB=50
IMAGE_QUALITY=2
MAX_IMAGE_SIZE=1920
BASE_URL=http://localhost:10000
EOF

    # Create uploads directory
    print_status "Creating uploads directory..."
    mkdir -p uploads

    print_status "Environment setup complete!"
}

# Function to start the application
start_application() {
    print_header "Starting Application"

    # Stop any existing processes
    print_status "Stopping any existing processes..."
    sudo pkill -f "uvicorn.*10000" || true
    sleep 2

    # Remove old PID file
    rm -f app.pid

    # Export environment variables
    print_status "Loading environment variables..."
    export $(cat .env | xargs)

    # Get external IP for GCP
    print_status "Getting external IP..."
    EXTERNAL_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google" 2>/dev/null || echo "localhost")

    print_status "Starting the application in background..."

    # Start the application in background using virtual environment
    nohup venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 10000 > app.log 2>&1 &

    # Get the PID
    APP_PID=$!
    echo $APP_PID > app.pid

    # Wait a moment and check if the process is still running
    sleep 3
    if ps -p $APP_PID > /dev/null 2>&1; then
        print_status "Application started successfully!"
        print_status "Application running with PID: $APP_PID"
    else
        print_error "Application failed to start. Check logs with: tail -f app.log"
        exit 1
    fi

    print_header "DEPLOYMENT COMPLETE!"
    echo ""
    print_status "🎉 Your New Reader application is now running!"
    echo ""
    print_status "Access URLs:"
    echo "  📚 API Documentation: http://${EXTERNAL_IP}:10000/docs"
    echo "  📖 Alternative Docs: http://${EXTERNAL_IP}:10000/redoc"
    echo "  🏠 Main Application: http://${EXTERNAL_IP}:10000/"
    echo ""
    print_status "Management commands:"
    echo "  📝 View logs: tail -f ~/new_reader/app.log"
    echo "  🛑 Stop app: kill \$(cat ~/new_reader/app.pid)"
    echo "  🔄 Restart: cd ~/new_reader && ./restart_app.sh"
    echo ""
}

# Function to create management scripts
create_management_scripts() {
    print_header "Creating Management Scripts"

    # Create restart script
    cat > restart_app.sh << 'EOF'
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
EOF

    chmod +x restart_app.sh

    # Create stop script
    cat > stop_app.sh << 'EOF'
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
EOF

    chmod +x stop_app.sh

    # Create status script
    cat > status_app.sh << 'EOF'
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
EOF

    chmod +x status_app.sh

    print_status "Management scripts created:"
    print_status "  - restart_app.sh: Restart the application"
    print_status "  - stop_app.sh: Stop the application"
    print_status "  - status_app.sh: Check application status"
}

# Main deployment function
main() {
    print_header "New Reader Auto-Deployment"
    echo "This script will automatically deploy the New Reader application"       
    echo "with proper virtual environment setup."
    echo ""

    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        print_error "Please don't run this script as root."
        exit 1
    fi

    # Navigate to home directory
    cd ~

    # Run deployment steps
    install_system_deps
    setup_repository
    setup_virtual_env
    setup_environment
    create_management_scripts
    start_application
}

# Handle script interruption
trap 'echo -e "\n${YELLOW}[INFO]${NC} Deployment interrupted."; exit 1' INT       

# Run main function
main "$@"
