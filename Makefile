# Makefile for Insight Project
# Provides convenient commands for development and deployment

.PHONY: help install dev-setup test docker-test build run clean deploy

# Default target
help:
	@echo "Insight Project - Available Commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install     - Install dependencies"
	@echo "  make dev-setup   - Setup development environment"
	@echo ""
	@echo "Development:"
	@echo "  make run         - Run the API server"
	@echo "  make test        - Test all API endpoints"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run with Docker Compose"
	@echo "  make docker-test  - Test Docker setup"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy      - Deploy to Render (requires setup)"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean       - Clean temporary files"
	@echo "  make lint        - Run code linting (if available)"

# Installation
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "Dependencies installed"

# Development setup
dev-setup:
	@echo "Setting up development environment..."
	python scripts/dev_setup.py
	@echo "Development setup completed"

# Run the application
run:
	@echo "Starting Insight API..."
	python run.py

# Test all endpoints
test:
	@echo "Testing API endpoints..."
	python test_api.py

# Docker commands
docker-build:
	@echo "Building Docker image..."
	docker build -t insight-api .

docker-run:
	@echo "Running with Docker Compose..."
	docker-compose up --build

docker-test:
	@echo "Testing Docker setup..."
	python scripts/docker_test.py

# Deployment
deploy:
	@echo "Deploying to Render..."
	@echo "Make sure you have:"
	@echo "1. Connected your GitHub repo to Render"
	@echo "2. Set up environment variables"
	@echo "3. Push your changes to GitHub"
	git add .
	git commit -m "Deploy to Render" || true
	git push

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf uploads/* temp/* logs/* 2>/dev/null || true
	rm -f .env.test 2>/dev/null || true
	@echo "Cleanup completed"

# Linting (optional)
lint:
	@echo "Running code linting..."
	@if command -v flake8 >/dev/null 2>&1; then \
		flake8 app/ --max-line-length=100 --ignore=E203,W503; \
	else \
		echo "flake8 not installed. Install with: pip install flake8"; \
	fi

# Quick start for new developers
quickstart: install dev-setup
	@echo ""
	@echo "Quick start completed!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Edit .env file and add your Google AI API Key"
	@echo "2. Run: make run"
	@echo "3. Visit: http://localhost:10000/docs"
	@echo "4. Test: make test" 