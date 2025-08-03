#!/bin/bash

echo "🚀 Indra LLM Platform - Quick Start"
echo "=================================="

# Check system requirements
echo "Checking system requirements..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

echo "✅ System requirements met"

# Ask user for setup type
echo ""
echo "Choose setup type:"
echo "1) Development (recommended for testing)"
echo "2) Production (for deployment)"
echo "3) Vercel Frontend Only"

read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo "Setting up development environment..."
        ./scripts/dev-setup.sh
        ./scripts/start-dev.sh
        ;;
    2)
        echo "Setting up production environment..."
        ./scripts/prod-setup.sh
        echo "Please edit .env.prod with your settings, then run:"
        echo "./scripts/deploy-prod.sh"
        ;;
    3)
        echo "Setting up Vercel deployment..."
        ./scripts/deploy-vercel.sh
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "🎉 Setup completed!"
echo "Check the README.md for detailed usage instructions."
