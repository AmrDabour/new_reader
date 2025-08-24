#!/bin/bash

# ========================================
# Virtual Environment Fix Script
# Use this if auto_deploy.sh fails with venv removal issues
# ========================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

print_header "Virtual Environment Fix Script"

# Stop all Python processes
print_status "Stopping all Python processes..."
sudo pkill -f "python" || true
sudo pkill -f "uvicorn" || true
sudo pkill -f "venv" || true
sleep 3

# Force cleanup NVIDIA and CUDA processes
print_status "Cleaning up GPU processes..."
sudo pkill -f "nvidia" || true
sudo pkill -f "cuda" || true
sudo pkill -f "cudnn" || true
sleep 2

# Try to unmount GPU drivers
print_status "Unmounting GPU drivers..."
sudo umount /proc/driver/nvidia 2>/dev/null || true

# Force remove problematic directories
print_status "Removing problematic directories..."

# Remove NVIDIA directories specifically
if [ -d "venv" ]; then
    print_warning "Found existing venv directory, cleaning up..."
    
    # Remove NVIDIA-related directories first
    sudo find venv -type d -name "nvidia" -exec rm -rf {} + 2>/dev/null || true
    sudo find venv -type d -name "cudnn" -exec rm -rf {} + 2>/dev/null || true
    sudo find venv -type d -name "cuda" -exec rm -rf {} + 2>/dev/null || true
    
    # Remove other problematic directories
    sudo find venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    sudo find venv -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    
    # Try to remove the entire venv
    if sudo rm -rf venv; then
        print_status "Virtual environment removed successfully!"
    else
        print_warning "Could not remove venv, renaming it..."
        sudo mv venv "venv_old_$(date +%s)"
        print_status "Virtual environment renamed successfully!"
    fi
fi

# Clean up other common problematic directories
print_status "Cleaning up other problematic directories..."
sudo rm -rf __pycache__ 2>/dev/null || true
sudo rm -rf .pytest_cache 2>/dev/null || true
sudo rm -rf *.egg-info 2>/dev/null || true

print_header "Cleanup Complete!"
print_status "You can now run auto_deploy.sh again"
print_status "Or manually create a new virtual environment:"
echo ""
echo "python3 -m venv venv"
echo "source venv/bin/activate"
echo "pip install -r requirements.txt"
echo "" 